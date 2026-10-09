import json
from tests.test_tutor import client, setup, HEADERS
from backend import db,study
from backend.schemas import Paper

def sample(client):
    job,papers,_=setup(client);paper=Paper.model_validate(papers[0]);node=paper.theory.nodes[0]
    return job,paper,node

def material(data):
    e=data['evidence'][0]
    return study.Material(questions=[{'id':'q1','question':'理解检查','options':['正确','错误'],'answer':0,'explanation':'原文解释','review_nodes':[data['target']['id']],'citations':[{'evidence_id':e['id'],'quote':e['text']}]}],formulas=[])

def test_reject_fabricated_citations_and_ambiguous_options(client):
    job,paper,node=sample(client);data=study.context(paper,node.id)
    for change in ('quote','options','nodes'):
        draft=material(data)
        if change=='quote':draft.questions[0].citations[0].quote='invented'
        elif change=='options':draft.questions[0].options=['same','same']
        else:draft.questions[0].review_nodes=['foreign']
        import pytest
        with pytest.raises(RuntimeError):study.generate(data,job,lambda *a:draft)

def test_semantic_check_filters_and_formula_source_gate(client):
    job,paper,node=sample(client);data=study.context(paper,node.id)
    def caller(stage,*args):
        return material(data) if stage=='study_material' else study.Assessment(supported_questions=[],supported_formulas=[],reason='不支持')
    import pytest
    with pytest.raises(RuntimeError):study.generate(data,job,caller)
    e=data['evidence'][0]
    f=study.Formula(id='f',formula='$invented$',source_formula='invented',explanation='解释',conditions=[],symbols=[],citations=[{'evidence_id':e['id'],'quote':e['text']}])
    assert not study.formula_ok(f,data)

def test_queue_cache_private_answer_grading_revision_and_ownership(client,monkeypatch):
    job,paper,node=sample(client);path=f'/api/jobs/{job}/papers/{paper.id}/study/{node.id}'
    first=client.post(path,headers=HEADERS).json();assert first['status']=='queued'
    assert client.post(path,headers=HEADERS).json()['id']==first['id']
    assert client.delete(f'/api/jobs/{job}',headers=HEADERS).status_code==409
    data=study.context(paper,node.id)
    monkeypatch.setattr(study,'generate',lambda *a:{**material(data).model_dump(),'notice':'检查通过'})
    assert study.run_next()
    result=client.get(path).json();assert result['status']=='completed'
    assert 'answer' not in result['result']['questions'][0] and 'explanation' not in result['result']['questions'][0]
    payload={'fingerprint':result['fingerprint'],'answers':{'q1':1}}
    graded=client.post(path+'/check',headers=HEADERS,json=payload).json();assert graded['score']==0 and graded['results'][0]['review_nodes']==[node.id]
    assert client.post(path+'/check',headers=HEADERS,json={**payload,'answers':{}}).status_code==400
    current=db.get(job)['result'];current['papers'][0]['revision']+=1;db.update(job,result=json.dumps(current))
    assert client.post(path+'/check',headers=HEADERS,json=payload).status_code==409
    client.cookies.clear();client.get('/api/session');assert client.get(path).status_code==404


def test_general_symbol_knowledge_is_allowed_and_labelled(client):
    job,paper,node=sample(client);data=study.context(paper,node.id)
    source=data['evidence'][0];source['text']+=' $S \\subseteq T$'
    formula=study.Formula(id='f1',formula='$S \\subseteq T$',source_formula='$S \\subseteq T$',explanation='集合包含关系',conditions=[],symbols=[{'symbol':'$\\subseteq$','meaning':'通常表示子集关系','origin':'general','citations':[]}],citations=[{'evidence_id':source['id'],'quote':'$S \\subseteq T$'}])
    assert study.formula_ok(formula,data)
    def caller(stage,*args):
        return study.Material(questions=[],formulas=[formula]) if stage=='study_material' else study.Assessment(supported_questions=[],supported_formulas=['f1'],reason='通用定义与上下文一致')
    result=study.generate(data,job,caller)
    assert result['formulas'][0]['symbols'][0]['origin']=='general'
