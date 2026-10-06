import pytest
from backend import theory
from backend.schemas import Evidence, TheoryNode, TheoryEdge, TheoryDraft, DependencyDraft, TheoryConditionsDraft, TheoryConditionAddition


def node(key):
    return TheoryNode(id=key, kind='lemma', label=key, statement='结论', conditions=[], evidence_ids=['e'])


def edge(source, target):
    return TheoryEdge(source=source, target=target, explanation='证明使用此前结果', evidence_ids=['e'])


def test_learning_path_diamond_and_disconnected():
    paths = theory.learning_paths([node(k) for k in 'abcde'], [edge('a','b'),edge('a','c'),edge('b','d'),edge('c','d')])
    assert paths['d'] == ['a','b','c','d']
    assert paths['e'] == ['e']


def test_cycle_refuses_fake_order():
    with pytest.raises(ValueError):
        theory.learning_paths([node('a'),node('b')], [edge('a','b'),edge('b','a')])


def test_statement_header_survives_chunk_boundary():
    evidence=[Evidence(id=str(i),paper_id='p',text=str(i)) for i in range(8)]
    groups=list(theory.context_groups(evidence,lambda e:[e[:4],e[4:]]))
    assert [e.id for e in groups[1]]==['2','3','4','5','6','7']
    assert {e.id for group in groups for e in group}=={e.id for e in evidence}


def test_proof_sections_stay_separate_and_keep_every_block():
    evidence=[Evidence(id=str(i),paper_id='p',text=str(i),section='Main' if i<2 else 'Proof of Corollary 6') for i in range(4)]
    groups=list(theory.proof_groups(evidence,lambda e:[e]))
    assert [[e.id for e in group] for group in groups]==[['0','1'],['2','3']]


def test_evaluation_does_not_hide_duplicate_labels_or_missing_conditions():
    from scripts.evaluate_theory import reference_checks,reference_passed
    from backend.schemas import Theory
    checks=reference_checks(Theory(nodes=[node('a'),node('a')]),{'labels':['a'],'edges':[],'condition_checks':{}})
    assert checks['duplicate_labels']==['a']
    assert not reference_passed(checks)
    checks=reference_checks(Theory(nodes=[node('a')]),{'labels':['a'],'edges':[],'condition_checks':{'a':['条件']}})
    assert not reference_passed(checks)


def test_invalid_evidence_and_unverified_nodes_are_not_published(monkeypatch):
    good, missing, rejected = node('a'),node('b'),node('c')
    missing.evidence_ids=['invented']
    monkeypatch.setattr(theory,'call',lambda *args: TheoryDraft(nodes=[good,missing,rejected]) if args[0]=='theory' else TheoryConditionsDraft(additions=[]) if args[0]=='theory_conditions' else DependencyDraft(edges=[]))
    def verify(items,*args):
        return {i['id']: ('unsupported' if i['text'].get('label')=='c' else 'supported','') for i in items}
    result=theory.extract_theory([Evidence(id='e',paper_id='p',text='原文')],'j',lambda e:[e],verify)
    assert [n.label for n in result.nodes] == ['a']
    assert result.learning_paths[result.nodes[0].id] == [result.nodes[0].id]


def test_empirical_paper_can_have_no_theory(monkeypatch):
    monkeypatch.setattr(theory,'call',lambda *args: TheoryDraft(nodes=[]))
    assert theory.extract_theory([], 'j', lambda e:[e], lambda *args:{}).nodes == []


def test_duplicate_statement_keeps_later_conditions_and_evidence():
    evidence=[Evidence(id=key,paper_id='p',text=key) for key in ['statement','proof']]
    def caller(stage,data,*args):
        if stage=='theory_conditions':
            return TheoryConditionsDraft(additions=[])
        if stage!='theory':
            return DependencyDraft(edges=[])
        ref=data['evidence'][-1]['id']
        item=node('Lemma 1')
        item.conditions=['容量足够' if ref=='statement' else '更新足够小']
        item.evidence_ids=[ref]
        return TheoryDraft(nodes=[item])
    def verifier(items,*args):
        assert len(items)==1
        assert items[0]['text']['conditions']==['容量足够','更新足够小']
        assert items[0]['evidence_ids']==['statement','proof']
        return {items[0]['id']:('supported','')}
    result=theory.extract_theory(evidence,'j',lambda e:[[e[0]],[e[1]]],lambda items,*args:verifier(items) if items else {},caller=caller)
    assert len(result.nodes)==1
    assert result.nodes[0].conditions==['容量足够','更新足够小']


def test_numbered_variants_reconcile_but_different_results_do_not_merge():
    variants=[node('first'),node('second'),node('other')]
    variants[0].label='Lemma 3'
    variants[1].label='Lemma 3 (Equivariance)'
    variants[2].label='Lemma 4'
    variants[1].statement='不同表述'
    evidence=[Evidence(id='e',paper_id='p',text='statement'),Evidence(id='neighbor',paper_id='p',text='proof'),Evidence(id='unrelated',paper_id='p',text='other')]
    def caller(stage,data,*args):
        assert stage=='theory_reconcile'
        assert len(data['variants'])==2
        assert [e['id'] for e in data['evidence']]==['e','neighbor']
        item=node('unified')
        item.label='Lemma 3'
        item.conditions=['sigmoid 是双射']
        return TheoryDraft(nodes=[item])
    result=theory.reconcile_nodes(variants,evidence,'j',caller)
    assert len(result)==2
    assert result[0].id=='first'
    assert result[0].conditions==['sigmoid 是双射']
    assert result[1].label=='Lemma 4'


def test_numbering_handles_appendices_and_terminal_punctuation():
    item=node('test')
    for label,expected in [('Lemma 3.', '3'),('Lemma A.1 (Proof)', 'a.1'),('Lemma 2.10', '2.10')]:
        item.label=label
        assert theory.numbered_key(item)==('lemma',expected)


def test_global_conditions_require_valid_node_and_local_source():
    evidence=[Evidence(id='scope',paper_id='p',text='nonparametric setting')]
    item=node('Theorem 1')
    def caller(*args):
        return TheoryConditionsDraft(additions=[
            TheoryConditionAddition(node_id=item.id,conditions=['非参数设定'],evidence_ids=['scope']),
            TheoryConditionAddition(node_id=item.id,conditions=['伪造条件'],evidence_ids=['invented']),
            TheoryConditionAddition(node_id='other',conditions=['不相关'],evidence_ids=['scope'])])
    theory.complete_conditions([item],evidence,'j',lambda e:[e],caller)
    assert item.conditions==['非参数设定']
    assert item.evidence_ids==['e','scope']


def test_later_appendix_proof_is_not_discarded_by_early_edge():
    evidence=[Evidence(id=key,paper_id='p',text=key) for key in ['e','proof']]
    def caller(stage,data,*args):
        refs=[block['id'] for block in data['evidence']]
        return DependencyDraft(edges=[TheoryEdge(source='a',target='b',explanation=refs[-1],evidence_ids=[refs[-1]])])
    def verifier(items,*args):
        for item in items:
            if 'dependency' in item['text']:
                assert item['text']['dependency']['evidence_ids']==['e','proof']
        return {item['id']:('supported','') for item in items}
    result=theory.extract_theory(evidence,'j',lambda e:[[e[0]],[e[1]]],verifier,caller=caller,supplied_nodes=[node('a'),node('b')])
    assert len(result.edges)==1
    assert result.edges[0].evidence_ids==['e','proof']


def test_selected_long_proof_preserved_without_search_quota():
    import json
    from pathlib import Path
    from backend.schemas import Paper
    from backend.tutor_retrieval import retrieve
    paper=Paper.model_validate(json.loads(Path('public/demo.json').read_text(encoding='utf-8'))['papers'][0])
    paper.evidence=[Evidence(id=f'e{i}',paper_id=paper.id,text='证明前提。'*400+f'最终结论{i}') for i in range(12)]
    pinned=[e.id for e in paper.evidence]
    excerpts=retrieve([paper],'学习路径',pinned=pinned)
    assert len(excerpts)==12
    assert {e['evidence_id']:e['text'] for e in excerpts}=={e.id:e.text for e in paper.evidence}


def test_proof_verification_keeps_joint_citation_context(monkeypatch):
    from backend import pipeline
    from backend.schemas import Verification
    evidence=[Evidence(id=key,paper_id='p',text=text,section='Proof of Theorem 7')
              for key,text in [('heading','Proof of Theorem 7'),('proof','Using Lemma 4 and 6'),('end','This proves the result.')]]
    items=[{'id':'proof-0','text':{'prerequisite':{'label':'Lemma 4'},'result':{'label':'Theorem 7'},'dependency':{'explanation':'联合使用两个引理'}},'evidence_ids':['proof']}]
    def caller(stage,data,*args):
        assert stage=='verify_proof'
        assert [e['id'] for e in data['evidence']]==['heading','proof','end']
        return Verification(checks=[{'id':'proof-0','status':'supported','reason':'证明同时使用两个引理。'}])
    monkeypatch.setattr(pipeline,'call',caller)
    assert pipeline.verify_items(items,evidence,'j')['proof-0'][0]=='supported'


def test_joint_proof_citations_include_ocr_superscripts_without_mutating_source():
    nodes=[node(label) for label in ['Lemma 4','Lemma 6','Theorem 7']]
    nodes[-1].kind='theorem'
    original='Using Lemma 4 and $^ { 6 , }$ we obtain a continuous inverse.'
    evidence=[Evidence(id=str(i),paper_id='p',text=text) for i,text in enumerate(['Theorem 7 The result.','Proof. Necessity.',original])]
    edges=theory.cited_proof_edges(evidence,nodes)
    assert {(e.source,e.target) for e in edges}=={('Lemma 4','Theorem 7'),('Lemma 6','Theorem 7')}
    assert all(e.evidence_ids==['0','1','2'] for e in edges)
    assert evidence[-1].text==original
    assert theory.cited_proof_edges(evidence[2:],nodes)==[]


def test_partial_numbered_node_repair_must_pass_fresh_verification():
    item=node('Lemma 1')
    evidence=[Evidence(id='e',paper_id='p',text='Lemma 1: conditional statement.')]
    def caller(stage,data,*args):
        if stage=='theory': return TheoryDraft(nodes=[item.model_copy(deep=True)])
        if stage=='theory_conditions': return TheoryConditionsDraft(additions=[])
        if stage=='theory_repair':
            repaired=item.model_copy(deep=True)
            repaired.conditions=['必要条件']
            return TheoryDraft(nodes=[repaired])
        return DependencyDraft(edges=[])
    def verifier(items,*args):
        return {i['id']:('supported' if i['text']['conditions'] else 'partial','缺少必要条件') for i in items}
    result=theory.extract_theory(evidence,'j',lambda e:[e],verifier,caller=caller)
    assert len(result.nodes)==1
    assert result.nodes[0].conditions==['必要条件']
    rejected=theory.extract_theory(evidence,'j',lambda e:[e],lambda items,*args:{i['id']:('partial','仍不完整') for i in items},caller=caller)
    assert rejected.nodes==[]
