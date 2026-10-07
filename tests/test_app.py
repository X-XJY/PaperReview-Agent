import io
import json
import time
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from backend import db
from backend.main import app
from backend.schemas import Paper, Synthesis

HEADERS={'X-Requested-With':'PaperMethodAgent'}

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    import backend.main as main
    monkeypatch.setattr(main,'DATA',tmp_path)
    with TestClient(app) as client:
        client.get('/api/session')
        yield client

def demo(client):
    response=client.post('/api/jobs/demo',headers=HEADERS)
    assert response.status_code==200
    return client.get('/api/jobs/'+response.json()['id']).json()

def test_demo_contract_and_export(client):
    job=demo(client)
    assert len(job['result']['papers'])==5
    for paper in job['result']['papers']:
        Paper.model_validate(paper)
        theory=paper['theory']
        assert len(theory['nodes']) >= 3, paper['id']
        assert theory['edges'], paper['id']
        evidence={e['id']:e for e in paper['evidence']}
        ids={n['id'] for n in theory['nodes']}
        for node in theory['nodes']:
            assert node['evidence_ids']
            for ref in node['evidence_ids']:
                assert evidence[ref]['paper_id']==paper['id']
                assert '非真实论文' in evidence[ref]['section']
        for edge in theory['edges']:
            assert edge['source'] in ids and edge['target'] in ids
            assert all(ref in evidence for ref in edge['evidence_ids'])
            source=next(n for n in theory['nodes'] if n['id']==edge['source'])
            citation=source['label'].split(' · ')[0]
            assert any(citation in evidence[ref]['text'] for ref in edge['evidence_ids'])
        for target,path in theory['learning_paths'].items():
            assert path[-1]==target
            assert set(path)<=ids
            for edge in theory['edges']:
                if edge['target'] in path:
                    assert path.index(edge['source']) < path.index(edge['target'])
    Synthesis.model_validate(job['result']['synthesis'])
    report=client.get('/api/jobs/'+job['id']+'/report')
    assert '非真实论文事实' in report.text
    assert 'demo-atlas-e2' in report.text
    assert '可能' in report.text

def test_demo_has_distinct_proof_topologies_and_branch_specific_paths(client):
    papers=demo(client)['result']['papers']
    assert [len(p['theory']['nodes']) for p in papers]==[3,5,4,5,6]
    assert [len(p['theory']['edges']) for p in papers]==[2,4,3,4,7]
    reflection=papers[3]['theory']
    nodes=reflection['nodes']
    branch=reflection['learning_paths'][nodes[3]['id']]
    assert nodes[1]['id'] in branch
    assert nodes[2]['id'] not in branch
    verification=papers[4]['theory']
    nodes=verification['nodes']
    merged=verification['learning_paths'][nodes[5]['id']]
    assert nodes[1]['id'] in merged and nodes[3]['id'] in merged
    assert nodes[2]['id'] not in merged


def test_demo_refreshes_old_version_without_overwriting_history(client):
    original=demo(client)
    assert demo(client)['id']==original['id']
    with db.connection() as conn:
        conn.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps({'files':[]}),original['id']))
    updated=demo(client)
    assert updated['id']!=original['id']
    assert demo(client)['id']==updated['id']
    assert client.get('/api/jobs/'+original['id']).json()['result']==original['result']
    assert len(updated['result']['papers'][0]['theory']['nodes'])==3


def test_business_pipeline_version_invalidates_whole_job_reuse(monkeypatch):
    from backend import main, prompts
    before=main.pipeline_signature()
    prompt_version=prompts.VERSION
    monkeypatch.setattr(main,'PIPELINE_VERSION','new-business-processing')
    assert main.pipeline_signature()!=before
    assert prompts.VERSION==prompt_version

def test_session_isolation_and_csrf(client):
    job=demo(client)
    with TestClient(app) as other:
        other.get('/api/session')
        assert other.get('/api/jobs/'+job['id']).status_code==404
        assert other.get('/api/jobs/'+job['id']+'/report').status_code==404
    assert client.post('/api/jobs/demo').status_code==403
    assert client.post('/api/jobs/demo',headers={**HEADERS,'Origin':'https://evil.invalid'}).status_code==403

def test_edit_revision_and_invalid_evidence(client):
    job=demo(client)
    paper=job['result']['papers'][0]
    claim=paper['extraction']['limitations'][0]
    path=f"/api/jobs/{job['id']}/papers/{paper['id']}"
    payload={'revision':1,'field':'limitations','claim_id':claim['id'],'text':'修订后的作者局限','kind':'author_statement','evidence_ids':['fake']}
    assert client.patch(path,headers=HEADERS,json=payload).status_code==422
    payload['evidence_ids']=claim['evidence_ids']
    response=client.patch(path,headers=HEADERS,json=payload)
    assert response.status_code==200
    edited=response.json()
    assert edited['stale']==1
    assert edited['result']['papers'][0]['revision']==2
    assert edited['result']['papers'][0]['extraction']['limitations'][0]['status']=='unverified'
    assert client.patch(path,headers=HEADERS,json=payload).status_code==409
    revisions=client.get('/api/jobs/'+job['id']+'/revisions').json()
    assert len(revisions)==1 and revisions[0]['before']['revision']==1
    assert client.post('/api/jobs/'+job['id']+'/regenerate',headers=HEADERS).status_code==409
    assert '待重新推导' in client.get('/api/jobs/'+job['id']+'/report').text

def pdf_bytes():
    out=io.BytesIO()
    writer=PdfWriter()
    writer.add_blank_page(width=100,height=100)
    writer.write(out)
    return out.getvalue()

def test_upload_limits_idempotency_and_file_isolation(client,monkeypatch):
    monkeypatch.setattr('backend.main.configured',lambda:True)
    bad=client.post('/api/jobs',headers=HEADERS,files={'files':('bad.pdf',b'not a pdf','application/pdf')})
    assert bad.status_code==422
    body=pdf_bytes()
    response=client.post('/api/jobs',headers=HEADERS,files=[('files',('a.pdf',body,'application/pdf')),('files',('copy.pdf',body,'application/pdf'))])
    assert response.status_code==200
    job_id=response.json()['id']
    assert len(db.get(job_id)['payload']['files'])==1
    again=client.post('/api/jobs',headers=HEADERS,files={'files':('a.pdf',body,'application/pdf')})
    assert again.json()['id']==job_id and again.json()['reused']
    nine=client.post('/api/jobs',headers=HEADERS,files=[('files',(f'{i}.pdf',body,'application/pdf')) for i in range(9)])
    assert nine.status_code==422
    paper_hash=db.get(job_id)['payload']['files'][0]['hash']
    assert client.get(f'/api/jobs/{job_id}/papers/{paper_hash}/pdf').status_code==200

def test_unconfigured_explicit(client,monkeypatch):
    monkeypatch.setattr('backend.main.configured',lambda:False)
    assert client.post('/api/jobs',headers=HEADERS,files={'files':('a.pdf',pdf_bytes(),'application/pdf')}).status_code==503

def test_missing_field_can_be_added_with_evidence(client):
    job=demo(client)
    paper=job['result']['papers'][0]
    response=client.patch(f"/api/jobs/{job['id']}/papers/{paper['id']}",headers=HEADERS,json={'revision':1,'field':'future_work','claim_id':'new','text':'人工补充的未来工作','kind':'human_note','evidence_ids':[]})
    assert response.status_code==200
    claim=response.json()['result']['papers'][0]['extraction']['future_work'][0]
    assert claim['kind']=='human_note' and claim['status']=='unverified'

def test_dev_proxy_origin_allowed(client):
    response=client.post('/api/jobs/demo',headers={**HEADERS,'Origin':'http://127.0.0.1:5173'})
    assert response.status_code==200


def test_learning_persistence_invalidation_and_delete(client):
    job=demo(client)
    paper=job['result']['papers'][0]
    node=paper['theory']['nodes'][0]
    url=f"/api/jobs/{job['id']}/papers/{paper['id']}/learning"
    initial=client.get(url).json()
    value={'node_id':node['id'],'fingerprint':initial['nodes'][node['id']]['fingerprint'],'status':'mastered'}
    assert client.patch(url,headers=HEADERS,json=value).status_code==200
    assert client.get(url).json()['nodes'][node['id']]['status']=='mastered'
    with TestClient(app) as other:
        other.get('/api/session')
        assert other.get(url).status_code==404
        assert other.patch(url,headers=HEADERS,json=value).status_code==404
    paper['theory']['nodes'][0]['statement']+=' changed'
    db.update(job['id'],result=json.dumps(job['result'],ensure_ascii=False))
    assert client.get(url).json()['nodes'][node['id']]['status']=='not_started'
    assert client.patch(url,headers=HEADERS,json=value).status_code==409
    value['node_id']='missing'
    assert client.patch(url,headers=HEADERS,json=value).status_code==404
    assert client.delete('/api/jobs/'+job['id'],headers=HEADERS).status_code==200
    with db.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM learning_progress WHERE job=?',(job['id'],)).fetchone()[0]==0


def test_teaching_pdf_matches_evidence_pages(client):
    from pypdf import PdfReader
    job=demo(client)
    for paper in job['result']['papers']:
        url=f"/api/jobs/{job['id']}/papers/{paper['id']}/pdf"
        response=client.get(url)
        assert response.status_code==200
        reader=PdfReader(io.BytesIO(response.content))
        assert len(reader.pages)==len(paper['evidence'])
        for evidence in paper['evidence']:
            text=reader.pages[evidence['page']-1].extract_text()
            normalize=lambda s: ''.join(s.split())
            assert normalize(evidence['text']) in normalize(text)
        with TestClient(app) as other:
            other.get('/api/session')
            assert other.get(url).status_code==404
    assert client.get(f"/api/jobs/{job['id']}/papers/../../private/pdf").status_code==404
