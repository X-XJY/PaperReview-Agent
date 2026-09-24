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
    Synthesis.model_validate(job['result']['synthesis'])
    report=client.get('/api/jobs/'+job['id']+'/report')
    assert '非真实论文事实' in report.text
    assert 'demo-atlas-e2' in report.text
    assert '可能' in report.text

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
