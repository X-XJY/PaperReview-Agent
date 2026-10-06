"""Evidence-grounded theory extraction and deterministic prerequisite paths."""
from hashlib import sha256
import re
from .schemas import TheoryNode, TheoryEdge, TheoryDraft, DependencyDraft, Theory, TheoryConditionsDraft
from .llm import call


def numbered_key(node):
    match = re.match(r'^(?:Definition|Assumption|Lemma|Theorem|Proposition|Corollary|定义|假设|引理|定理|命题|推论)\s*((?:[A-Za-z]\.?)?\d+(?:\.\d+)*)(?![\w]|\.\d)', node.label.strip(), re.I)
    return (node.kind, match.group(1).lower()) if match else None


def reconcile_nodes(nodes, evidence, job_id, caller):
    groups = {}
    for node in nodes:
        key = numbered_key(node) or ('unlabelled', node.id)
        groups.setdefault(key, []).append(node)
    result = []
    for key, variants in groups.items():
        if len(variants) == 1:
            result.extend(variants)
            continue
        refs = {ref for node in variants for ref in node.evidence_ids}
        anchors = set(refs)
        # Include adjacent proof blocks to recover qualifications in the appendix.
        for index, block in enumerate(evidence):
            if block.id in anchors:
                refs.update(e.id for e in evidence[max(0,index-1):index+2])
        draft = caller('theory_reconcile', {'variants':[n.model_dump() for n in variants],
                       'evidence':[e.model_dump() for e in evidence if e.id in refs]}, TheoryDraft, job_id)
        if len(draft.nodes) != 1:
            continue
        node = draft.nodes[0]
        if numbered_key(node) != key or not node.statement.strip() or not node.evidence_ids or not set(node.evidence_ids) <= refs:
            continue
        node.id = variants[0].id
        result.append(node)
    return result


def complete_conditions(nodes, evidence, job_id, chunker, caller):
    if not nodes:
        return
    lookup = {n.id:n for n in nodes}
    for group in context_groups(evidence, chunker):
        draft = caller('theory_conditions', {'nodes':[n.model_dump() for n in nodes],
                       'evidence':[e.model_dump() for e in group]}, TheoryConditionsDraft, job_id)
        group_ids = {e.id for e in group}
        for addition in draft.additions:
            if addition.node_id not in lookup or not addition.conditions or not addition.evidence_ids or not set(addition.evidence_ids) <= group_ids:
                continue
            node = lookup[addition.node_id]
            node.conditions = list(dict.fromkeys(node.conditions + addition.conditions))
            node.evidence_ids = list(dict.fromkeys(node.evidence_ids + addition.evidence_ids))


def context_groups(evidence, chunker):
    previous = []
    for group in chunker(evidence):
        # Carry boundary context so statement headers and following formulas stay together.
        yield previous[-2:] + group
        previous = group


def proof_groups(evidence, chunker):
    section, group = None, []
    for block in evidence:
        formal_header = re.match(r'^(?:Definition|Assumption|Lemma|Theorem|Proposition|Corollary)\s+(?:[A-Za-z]\.?)?\d+(?:\.\d+)*(?![\w]|\.\d)', block.text.strip(), re.I)
        if group and (block.section != section or formal_header):
            yield from context_groups(group, chunker)
            group = []
        section = block.section
        group.append(block)
    if group:
        yield from context_groups(group, chunker)


def learning_paths(nodes, edges):
    parents = {node.id: set() for node in nodes}
    for edge in edges:
        parents[edge.target].add(edge.source)
    paths = {}
    for target in parents:
        visiting, visited, order = set(), set(), []

        def visit(key):
            if key in visiting:
                raise ValueError('证明依赖存在循环，不能生成学习路径。')
            if key in visited:
                return
            visiting.add(key)
            for parent in sorted(parents[key]):
                visit(parent)
            visiting.remove(key)
            visited.add(key)
            order.append(key)

        visit(target)
        paths[target] = order
    return paths


def cited_proof_edges(group, nodes):
    """Literal grouped citations nominate candidates; verification still decides."""
    kinds = {'definition':'definition','assumption':'assumption','lemma':'lemma','theorem':'theorem','proposition':'proposition','corollary':'corollary'}
    header = re.match(r'^(Definition|Assumption|Lemma|Theorem|Proposition|Corollary)\s+((?:[A-Za-z]\.?)?\d+(?:\.\d+)*)(?![\w]|\.\d)', group[0].text.strip(), re.I) if group else None
    lookup = {numbered_key(n):n for n in nodes if numbered_key(n)}
    target = lookup.get((kinds[header.group(1).lower()],header.group(2).lower())) if header else None
    if not target:
        return []
    proof = None
    result = []
    number = r'(?:[A-Za-z]\.?)?\d+(?:\.\d+)*'
    citation = re.compile(r'\b(Definition|Assumption|Lemma|Theorem|Proposition|Corollary)s?\s+(' + number + r'(?:\s*(?:,\s*(?:and\s+)?|and\s+)'+ number + r')*)(?![\w]|\.\d)', re.I)
    for block in group:
        if proof is None and re.search(r'\bProof\b',block.text,re.I):
            proof = block
        if proof is None:
            continue
        # Parser OCR can wrap a cited number as a LaTeX superscript.
        citation_text = re.sub(r'\$\s*\^\s*\{\s*(\d+(?:\.\d+)?)\s*,?\s*\}\s*\$', r'\1', block.text)
        for match in citation.finditer(citation_text):
            for value in re.findall(number,match.group(2)):
                source = lookup.get((kinds[match.group(1).lower()],value.lower()))
                if source and source.id != target.id:
                    result.append(TheoryEdge(source=source.id,target=target.id,
                                  explanation=f'{target.label} 的证明中引用 {match.group(0)}，作为证明前提。',
                                  evidence_ids=list(dict.fromkeys([group[0].id,proof.id,block.id]))))
    return result


def extract_theory(evidence, job_id, chunker, verifier, caller=None, supplied_nodes=None):
    caller = caller or call
    nodes, seen = list(supplied_nodes or []), {}
    for group in ([] if supplied_nodes is not None else context_groups(evidence, chunker)):
        draft = caller('theory', {'evidence': [e.model_dump() for e in group]}, TheoryDraft, job_id)
        group_ids = {e.id for e in group}
        for node in draft.nodes:
            marker = (node.kind, node.label.strip(), node.statement.strip())
            if re.match(r'^Property\b', node.label.strip(), re.I):
                continue
            if not node.statement.strip() or not node.evidence_ids or not set(node.evidence_ids) <= group_ids:
                continue
            if marker in seen:
                existing = seen[marker]
                existing.conditions = list(dict.fromkeys(existing.conditions + node.conditions))
                existing.evidence_ids = list(dict.fromkeys(existing.evidence_ids + node.evidence_ids))
                continue
            seen[marker] = node
            node.id = 'theory-' + sha256((group[0].paper_id + repr(marker)).encode()).hexdigest()[:20]
            nodes.append(node)
    nodes = reconcile_nodes(nodes, evidence, job_id, caller) if supplied_nodes is None else nodes
    if supplied_nodes is None:
        complete_conditions(nodes, evidence, job_id, chunker, caller)
    items = [{'id': n.id, 'text': {**n.model_dump(),
              'rule':'仅纳入本文明确标注的定义/假设/引理/定理/命题/推论。借用、引用或重述他人定理不作为本文结果；Property 不包装成 Definition。证明额外适用条件须保留。'}, 'evidence_ids': n.evidence_ids} for n in nodes]
    checked = verifier(items, evidence, job_id)
    if supplied_nodes is None:
        available = {e.id for e in evidence}
        for index, node in enumerate(nodes):
            status, reason = checked.get(node.id, ('unverified', ''))
            if status != 'partial' or not numbered_key(node):
                continue
            refs = set(node.evidence_ids)
            anchors = set(refs)
            for position, block in enumerate(evidence):
                if block.id in anchors:
                    refs.update(e.id for e in evidence[max(0,position-1):position+2])
            draft = caller('theory_repair', {'node':node.model_dump(), 'reason':reason,
                           'evidence':[e.model_dump() for e in evidence if e.id in refs]}, TheoryDraft, job_id)
            if len(draft.nodes) != 1:
                continue
            repaired = draft.nodes[0]
            if numbered_key(repaired) != numbered_key(node) or not repaired.statement.strip() or not repaired.evidence_ids or not set(repaired.evidence_ids) <= refs & available:
                continue
            repaired.id = node.id
            check_item = {**items[index], 'text':{**repaired.model_dump(), 'rule':items[index]['text']['rule']}, 'evidence_ids':repaired.evidence_ids}
            check = verifier([check_item], evidence, job_id)
            if check.get(node.id, ('unverified', ''))[0] == 'supported':
                nodes[index] = repaired
                checked[node.id] = check[node.id]
    rejected_nodes = sum(checked.get(n.id, ('unverified', ''))[0] != 'supported' for n in nodes)
    nodes = [n for n in nodes if checked.get(n.id, ('unverified', ''))[0] == 'supported']
    if not nodes:
        return Theory(warnings=[f'{rejected_nodes} 条候选理论陈述未通过原文核验，未纳入图谱。'] if rejected_nodes else [])
    ids = {n.id for n in nodes}
    node_lookup = {n.id:n for n in nodes}
    edges, edge_keys = [], {}
    # Proof text may be distant from a statement; examine every source block.
    for group in proof_groups(evidence, chunker):
        draft = caller('theory_dependencies', {
            'nodes': [n.model_dump(include={'id','kind','label','statement'}) for n in nodes],
            'evidence': [e.model_dump() for e in group],
        }, DependencyDraft, job_id)
        literal_edges = cited_proof_edges(group,nodes)
        literal_pairs = {(e.source,e.target) for e in literal_edges}
        group_ids = {e.id for e in group}
        for edge in [e for e in draft.edges if (e.source,e.target) not in literal_pairs] + literal_edges:
            key = (edge.source, edge.target)
            if edge.source == edge.target or not {edge.source, edge.target} <= ids:
                continue
            if not edge.evidence_ids or not set(edge.evidence_ids) <= group_ids:
                continue
            prerequisite = node_lookup[edge.source]
            if prerequisite.kind in ('definition', 'assumption'):
                # Shared notation alone cannot establish an explicitly cited prerequisite.
                citation = re.match(r'^(Definition|Assumption|定义|假设)\s*((?:[A-Za-z]\.?)?\d+(?:\.\d+)*)(?![\w]|\.\d)', prerequisite.label, re.I)
                proof_text = ' '.join(e.text for e in group if e.id in edge.evidence_ids)
                if not citation or not re.search(r'\b' + re.escape(citation.group(1)) + r'\s*' + re.escape(citation.group(2)) + r'(?![\w]|\.\d)', proof_text, re.I):
                    continue
            if key in edge_keys:
                existing = edge_keys[key]
                existing.evidence_ids = list(dict.fromkeys(existing.evidence_ids + edge.evidence_ids))
                if edge.explanation not in existing.explanation:
                    existing.explanation += '\n' + edge.explanation
                continue
            edge_keys[key] = edge
            edges.append(edge)
    lookup = {n.id: n.model_dump() for n in nodes}
    items = [{'id': f'proof-{i}', 'text': {
        'prerequisite': lookup[e.source], 'result': lookup[e.target],
        'dependency': e.model_dump(),
        'rule': '原文必须明确说明证明使用了此前结果；相似性和顺序不构成依赖。',
    }, 'evidence_ids': list(dict.fromkeys(e.evidence_ids + lookup[e.source]['evidence_ids'] + lookup[e.target]['evidence_ids']))}
        for i, e in enumerate(edges)]
    checked = verifier(items, evidence, job_id)
    edges = [e for i, e in enumerate(edges) if checked.get(f'proof-{i}', ('unverified', ''))[0] == 'supported']
    result = Theory(nodes=nodes, edges=edges)
    if rejected_nodes:
        result.warnings.append(f'{rejected_nodes} 条候选理论陈述未通过原文核验，未纳入图谱。')
    try:
        result.learning_paths = learning_paths(nodes, edges)
    except ValueError as error:
        result.warnings.append(str(error))
    return result
