from tests.test_tutor import client, setup, HEADERS
from backend import db, pipeline
from backend.schemas import Theory, Synthesis
import json
import pytest


def test_theory_edit_revisions_evidence_and_session_isolation(client):
    job,papers,_=setup(client)
    paper=papers[0]
    path=f'/api/jobs/{job}/papers/{paper["id"]}/theory'
    node={'id':'manual-1','kind':'theorem','label':'Theorem 1','statement':'测试陈述','conditions':['测试条件'],'evidence_ids':[paper['evidence'][0]['id']]}
    payload={'revision':paper['revision'],'nodes':[node]}
    invalid={**node,'evidence_ids':[papers[1]['evidence'][0]['id']]}
    assert client.patch(path,headers=HEADERS,json={**payload,'nodes':[invalid]}).status_code==422
    assert client.patch(path,headers=HEADERS,json={**payload,'nodes':[node,node]}).status_code==422
    response=client.patch(path,headers=HEADERS,json=payload)
    assert response.status_code==200
    updated=response.json()['result']['papers'][0]
    assert updated['revision']==paper['revision']+1
    assert updated['theory']['status']=='pending'
    assert updated['theory']['edges']==[] and updated['theory']['learning_paths']=={}
    assert db.get(job)['payload']['dirty_theories']==[paper['id']]
    assert client.patch(path,headers=HEADERS,json=payload).status_code==409
    assert len(client.get(f'/api/jobs/{job}/revisions').json())==1
    client.cookies.clear();client.get('/api/session')
    assert client.patch(path,headers=HEADERS,json={**payload,'revision':updated['revision']}).status_code==404


def test_theory_edit_during_processing_is_rejected(client):
    job,papers,_=setup(client)
    db.update(job,status='running')
    response=client.patch(f'/api/jobs/{job}/papers/{papers[0]["id"]}/theory',headers=HEADERS,json={'revision':1,'nodes':[]})
    assert response.status_code==409


def test_failed_theory_preserves_methods_and_resumes_without_pdf_parse(client,monkeypatch):
    job,papers,_=setup(client)
    current=db.get(job)
    result=current['result']
    result['mode']='live'
    for paper in result['papers']:
        paper['theory']=None
    db.update(job,result=json.dumps(result))
    calls=[]
    def extract(*args,**kwargs):
        calls.append(1)
        if len(calls)==1:
            raise RuntimeError('临时服务故障')
        return Theory()
    monkeypatch.setattr(pipeline,'extract_theory',extract)
    monkeypatch.setattr(pipeline,'synthesize',lambda *args:Synthesis(summary=[],relations=[],directions=[],common_gaps=[]))
    monkeypatch.setattr(pipeline,'parse',lambda *args:pytest.fail('不可重复解析成功论文'))
    pipeline.run(db.get(job))
    partial=db.get(job)
    assert partial['status']=='partial'
    assert len(partial['result']['papers'])==len(result['papers'])
    assert partial['result']['papers'][0]['extraction']==result['papers'][0]['extraction']
    assert partial['result']['papers'][0]['theory'] is None
    pipeline.run(db.get(job))
    assert db.get(job)['status']=='completed'
    assert len(calls)==len(result['papers'])+1
