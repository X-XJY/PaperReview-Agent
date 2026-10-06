"""Evidence-grounded theory extraction and deterministic prerequisite paths."""
from hashlib import sha256
from .schemas import TheoryNode, TheoryEdge, TheoryDraft, DependencyDraft, Theory
from .llm import call


def context_groups(evidence, chunker):
    previous = []
    for group in chunker(evidence):
        # Carry boundary context so statement headers and following formulas stay together.
        yield previous[-2:] + group
        previous = group


def proof_groups(evidence, chunker):
    section, group = None, []
    for block in evidence:
        if group and block.section != section:
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


def extract_theory(evidence, job_id, chunker, verifier, caller=None, supplied_nodes=None):
    caller = caller or call
    nodes, seen = list(supplied_nodes or []), set()
    for group in ([] if supplied_nodes is not None else context_groups(evidence, chunker)):
        draft = caller('theory', {'evidence': [e.model_dump() for e in group]}, TheoryDraft, job_id)
        group_ids = {e.id for e in group}
        for node in draft.nodes:
            marker = (node.kind, node.label.strip(), node.statement.strip())
            if marker in seen or not node.statement.strip() or not node.evidence_ids or not set(node.evidence_ids) <= group_ids:
                continue
            seen.add(marker)
            node.id = 'theory-' + sha256((group[0].paper_id + repr(marker)).encode()).hexdigest()[:20]
            nodes.append(node)
    items = [{'id': n.id, 'text': n.model_dump(), 'evidence_ids': n.evidence_ids} for n in nodes]
    checked = verifier(items, evidence, job_id)
    rejected_nodes = sum(checked.get(n.id, ('unverified', ''))[0] != 'supported' for n in nodes)
    nodes = [n for n in nodes if checked.get(n.id, ('unverified', ''))[0] == 'supported']
    if not nodes:
        return Theory(warnings=[f'{rejected_nodes} 条候选理论陈述未通过原文核验，未纳入图谱。'] if rejected_nodes else [])
    ids = {n.id for n in nodes}
    edges, edge_keys = [], {}
    # Proof text may be distant from a statement; examine every source block.
    for group in proof_groups(evidence, chunker):
        draft = caller('theory_dependencies', {
            'nodes': [n.model_dump() for n in nodes],
            'evidence': [e.model_dump() for e in group],
        }, DependencyDraft, job_id)
        group_ids = {e.id for e in group}
        for edge in draft.edges:
            key = (edge.source, edge.target)
            if edge.source == edge.target or not {edge.source, edge.target} <= ids:
                continue
            if not edge.evidence_ids or not set(edge.evidence_ids) <= group_ids:
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
