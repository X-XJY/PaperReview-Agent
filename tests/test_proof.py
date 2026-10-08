import json
import pytest
from tests.test_tutor import client, setup, HEADERS
from backend import db, proof
from backend.schemas import Paper

def sample(client):
    job,papers,_=setup(client)
    paper=Paper.model_validate(papers[0])
    node=next(n for n in paper.theory.nodes if n.kind=='theorem')
    return job,paper,node

def fake_step(data, **overrides):
    evidence=data['evidence'][-1]
    return {'id':'s1','title':'推导','explanation':'有依据的解释','formula':'','rule':'原文规则','prerequisites':[],'jump_explanation':'','kind':'source','citations':[{'evidence_id':evidence['id'],'quote':evidence['text']}],**overrides}

def test_citation_gate_rejects_foreign_fabricated_and_duplicate_steps(client):
    _,paper,node=sample(client);data=proof.context(paper,node.id)
    for overrides in ({'citations':[{'evidence_id':'foreign','quote':'invented'}]}, {'citations':[{'evidence_id':data['evidence'][0]['id'],'quote':'invented'}]}, {'prerequisites':['unknown']}):
        draft=proof.Explanation(target_id=node.id,steps=[fake_step(data,**overrides)],missing=[])
        valid,rejected=proof.validate_steps(draft,data)
        assert not valid and len(rejected)==1
    step=fake_step(data)
    assert not proof.validate_steps(proof.Explanation(target_id=node.id,steps=[step,step],missing=[]),data)[0]

def test_independent_check_cannot_mark_partial_or_missing_proof_complete(client):
    job,paper,node=sample(client);data=proof.context(paper,node.id)
    def caller(stage,payload,schema,job_id):
        if stage=='proof_explain': return proof.Explanation(target_id=node.id,steps=[fake_step(data)],missing=[])
        return proof.Checks(checks=[{'id':'s1','status':'partial','reason':'条件不完整'}],complete=True,completeness_reason='模型声称完整')
    result=proof.generate(data,job,caller)
    assert not result['complete'] and result['steps'][0]['status']=='partial'
    def wrong(stage,*args):return proof.Explanation(target_id='wrong',steps=[],missing=[])
    with pytest.raises(RuntimeError):proof.generate(data,job,wrong)

def test_proof_queue_reuse_revision_isolation_and_deletion(client,monkeypatch):
    job,paper,node=sample(client)
    path=f'/api/jobs/{job}/papers/{paper.id}/proof/{node.id}'
    assert client.get(path).json()['status']=='idle'
    first=client.post(path,headers=HEADERS).json()
    assert first['status']=='queued'
    assert client.post(path,headers=HEADERS).json()['id']==first['id']
    assert client.delete(f'/api/jobs/{job}',headers=HEADERS).status_code==409
    monkeypatch.setattr(proof,'generate',lambda *args:{'steps':[],'complete':False,'missing':['缺少证明']})
    assert proof.run_next()
    assert client.get(path).json()['status']=='completed'
    assert client.post(path,headers=HEADERS).json()['id']==first['id']
    current=db.get(job)['result'];current['papers'][0]['revision']+=1;db.update(job,result=json.dumps(current))
    assert client.get(path).json()['status']=='idle'
    client.cookies.clear();client.get('/api/session')
    assert client.get(path).status_code==404

def test_standalone_proof_selected_without_dependency_edges(client):
    _,paper,node=sample(client)
    paper.theory.edges=[]
    data=proof.context(paper,node.id)
    assert any('Proof' in e['text'] for e in data['evidence'])
    definition=next(n for n in paper.theory.nodes if n.kind=='definition')
    with pytest.raises(Exception):proof.context(paper,definition.id)
