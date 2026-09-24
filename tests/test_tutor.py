import json
import time
import pytest
from fastapi.testclient import TestClient
from backend import db, tutor, llm
from backend.main import app
from backend.schemas import Paper
from backend.tutor_schemas import TutorAnswer, TutorChecks, TutorQuery
from backend.tutor_retrieval import retrieve

HEADERS={'X-Requested-With':'PaperMethodAgent'}

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    monkeypatch.setattr('backend.main.DATA',tmp_path)
    monkeypatch.setattr(tutor,'configured',lambda:True)
    monkeypatch.setenv('TUTOR_GLOBAL_DAILY_TURNS','200')
    monkeypatch.setenv('TUTOR_DAILY_TOKENS','1000000')
    with TestClient(app) as c:
        c.get('/api/session')
        yield c

def setup(c, count=2):
    job=c.post('/api/jobs/demo',headers=HEADERS).json()['id']
    papers=c.get('/api/jobs/'+job).json()['result']['papers'][:count]
    thread=c.post(f'/api/tutor/jobs/{job}/threads',headers=HEADERS,json={'paper_ids':[p['id'] for p in papers]}).json()['id']
    return job,papers,thread

def send(c,thread,**values):
    return c.post(f'/api/tutor/threads/{thread}/messages',headers=HEADERS,
                  json={'question':'retrieval method','request_id':db.uid(),**values})

def message(c,thread):
    return c.get('/api/tutor/threads/'+thread).json()['messages'][-1]

def fake_model(monkeypatch,seen):
    def call(stage,data,schema,**kwargs):
        seen.append((stage,data))
        if stage=='tutor_query':
            return TutorQuery(keywords=['retrieval','query'])
        if stage=='tutor_answer':
            return TutorAnswer(blocks=[{'kind':'paper_fact','text':'检索候选文档。','evidence_ids':[data['evidence'][0]['evidence_id']]}],question='候选文档有什么作用？',suggestions=[])
        if stage=='tutor_verify':
            return TutorChecks(checks=[{'index':0,'status':'supported','reason':'原文支持'}])
        raise AssertionError(stage)
    monkeypatch.setattr(tutor.llm,'call',call)

def test_tutor_auth_scope_and_idempotency(client):
    job,papers,thread=setup(client)
    assert send(client,thread,evidence_ids=['foreign-id']).status_code==422
    assert client.post(f'/api/tutor/jobs/{job}/threads',headers=HEADERS,json={'paper_ids':['foreign']}).status_code==422
    key=db.uid()
    first=send(client,thread,request_id=key)
    assert first.status_code==200
    assert send(client,thread,request_id=key).json()=={'id':first.json()['id'],'reused':True}
    assert send(client,thread,request_id=key,question='changed').status_code==409
    assert send(client,thread).status_code==409
    client.cookies.clear();client.get('/api/session')
    assert client.get('/api/tutor/threads/'+thread).status_code==404
    assert send(client,thread).status_code==404
    assert client.get(f'/api/tutor/jobs/{job}/threads').status_code==404

def test_compare_needs_multiple_papers(client):
    _,_,thread=setup(client,1)
    assert send(client,thread,activity='compare').status_code==422

def test_full_tutor_grounding_history_and_revision(client,monkeypatch):
    job,papers,thread=setup(client)
    seen=[];fake_model(monkeypatch,seen)
    task=send(client,thread,question='解释检索方法').json()['id']
    tutor.run(task)
    m=message(client,thread)
    assert m['status']=='completed' and not m['stale']
    citation=m['answer']['blocks'][0]['citations'][0]
    assert any(citation['text'] in e['text'] for p in papers for e in p['evidence'])
    assert citation['title'] in [p['metadata']['title'] for p in papers]
    follow=send(client,thread,question='请给一个提示',mode='guided',activity='quiz').json()['id']
    tutor.run(follow)
    follow_data=[d for stage,d in seen if stage=='tutor_answer'][-1]
    assert follow_data['history'][0]['assistant']['question']=='候选文档有什么作用？'
    assert 'citations' not in json.dumps(follow_data['history'])
    j=db.get(job);j['result']['papers'][0]['revision']+=1
    db.update(job,result=json.dumps(j['result']))
    assert all(m['stale'] for m in client.get('/api/tutor/threads/'+thread).json()['messages'])
    next_task=send(client,thread,question='修订之后呢').json()['id']
    with db.connection() as conn:
        row=conn.execute('SELECT history FROM tutor_tasks WHERE id=?',(next_task,)).fetchone()
        assert json.loads(row[0])==[]

def test_ground_rejects_invented_citations_and_hides_unsupported():
    answer=TutorAnswer(blocks=[{'kind':'paper_fact','text':'invented fact','evidence_ids':['fake']},
                             {'kind':'background','text':'background','evidence_ids':[]}])
    checks=TutorChecks(checks=[{'index':0,'status':'supported','reason':'bad verifier'},
                             {'index':1,'status':'supported','reason':'too strong'}])
    result=tutor.ground(answer,checks,{},paper_only=True)
    assert len(result['blocks'])==1 and result['blocks'][0]['status']=='unsupported'
    assert 'invented fact' not in result['blocks'][0]['text']
    result=tutor.ground(answer,checks,{})
    assert result['blocks'][1]['status']=='unverified'

def test_missing_and_duplicate_verification_cannot_support_fact():
    answer=TutorAnswer(blocks=[{'kind':'paper_fact','text':'x','evidence_ids':['e']}])
    checks=TutorChecks(checks=[{'index':0,'status':'supported','reason':'x'}]*2)
    assert tutor.ground(answer,checks,{'e':{'text':'x'}})['blocks'][0]['status']=='unverified'


def test_partial_retrieval_cannot_prove_absence_in_full_paper():
    answer=TutorAnswer(blocks=[{'kind':'paper_fact','text':'Transformer 论文未报告该基准的准确率。','evidence_ids':['e']}])
    checks=TutorChecks(checks=[{'index':0,'status':'supported','reason':'excerpt omits it'}])
    assert tutor.ground(answer,checks,{'e':{'text':'BLEU 28.4'}})['blocks'][0]['status']=='unverified'

def test_task_snapshot_change_before_execution(client):
    job,_,thread=setup(client)
    task=send(client,thread).json()['id']
    j=db.get(job);j['result']['papers'][0]['revision']+=1
    db.update(job,result=json.dumps(j['result']))
    with pytest.raises(llm.ProviderError,match='修订'):
        tutor.run(task)

def test_tutor_quota_and_model_budget_are_separate(client,monkeypatch):
    job,_,thread=setup(client)
    task=send(client,thread).json()['id']
    meter=tutor.TutorMeter(task,'test-session')
    for _ in range(5):
        meter.before_call(100,100)
        meter.record_usage({'prompt_tokens':10,'completion_tokens':5})
    with pytest.raises(llm.ProviderError,match='5 次'):
        meter.before_call(100)
    assert db.get(job)['calls']==0
    with db.connection() as c:
        assert c.execute('SELECT sum(tokens) FROM tutor_usage').fetchone()[0]==75
    tutor.set_state(task,'done',status='failed')
    monkeypatch.setenv('TUTOR_GLOBAL_DAILY_TURNS','1')
    assert send(client,thread).status_code==429

def test_budget_reserves_failed_requests(client,monkeypatch):
    _,_,thread=setup(client)
    task=send(client,thread).json()['id']
    meter=tutor.TutorMeter(task,'session')
    monkeypatch.setenv('TUTOR_DAILY_TOKENS','500')
    meter.before_call(200,200)
    with pytest.raises(llm.ProviderError,match='token'):
        meter.before_call(200,200)

def test_same_context_cached_but_new_mode_misses(client,monkeypatch):
    _,papers,thread=setup(client)
    seen=[];fake_model(monkeypatch,seen)
    task=send(client,thread).json()['id'];tutor.run(task)
    job=db.get(client.get('/api/jobs').json()[0]['id'])
    fresh=client.post(f"/api/tutor/jobs/{job['id']}/threads",headers=HEADERS,json={'paper_ids':[p['id'] for p in papers]}).json()['id']
    cached=send(client,fresh)
    assert cached.json()['reused']
    fresh2=client.post(f"/api/tutor/jobs/{job['id']}/threads",headers=HEADERS,json={'paper_ids':[p['id'] for p in papers]}).json()['id']
    assert not send(client,fresh2,mode='guided').json()['reused']

def test_retrieval_preserves_each_paper_and_original_text():
    from pathlib import Path
    papers=[Paper.model_validate(p) for p in json.loads(Path('public/demo.json').read_text(encoding='utf-8'))['papers']]
    rows=retrieve(papers,'retrieval',keywords=['query','documents'],pinned=[p.evidence[1].id for p in papers])
    assert {r['paper_id'] for r in rows}=={p.id for p in papers}
    originals={e.id:e for p in papers for e in p.evidence}
    assert all(r['text'] in originals[r['evidence_id']].text for r in rows)
    assert retrieve(papers,'zzzz_nonexistent_zzzz')==[]


def test_session_can_exceed_twenty_daily_turns(client):
    _,_,thread=setup(client)
    for _ in range(21):
        response=send(client,thread)
        assert response.status_code==200
        tutor.set_state(response.json()['id'],'done',status='failed')
    assert 'daily_turns' not in client.get('/api/tutor/status').json()
