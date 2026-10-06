import pytest
from backend import theory
from backend.schemas import Evidence, TheoryNode, TheoryEdge, TheoryDraft, DependencyDraft


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


def test_invalid_evidence_and_unverified_nodes_are_not_published(monkeypatch):
    good, missing, rejected = node('a'),node('b'),node('c')
    missing.evidence_ids=['invented']
    monkeypatch.setattr(theory,'call',lambda *args: TheoryDraft(nodes=[good,missing,rejected]) if args[0]=='theory' else DependencyDraft(edges=[]))
    def verify(items,*args):
        return {i['id']: ('unsupported' if i['text'].get('label')=='c' else 'supported','') for i in items}
    result=theory.extract_theory([Evidence(id='e',paper_id='p',text='原文')],'j',lambda e:[e],verify)
    assert [n.label for n in result.nodes] == ['a']
    assert result.learning_paths[result.nodes[0].id] == [result.nodes[0].id]


def test_empirical_paper_can_have_no_theory(monkeypatch):
    monkeypatch.setattr(theory,'call',lambda *args: TheoryDraft(nodes=[]))
    assert theory.extract_theory([], 'j', lambda e:[e], lambda *args:{}).nodes == []


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
