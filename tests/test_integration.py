"""End-to-end local pipeline contract with mocked external services, no paid API calls."""
import io
import json
import pytest
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from backend import db,pipeline
from backend.main import app
from backend.schemas import Metadata,Extraction,Classification,Claim,Evidence,Verification,CheckItem,Synthesis

@pytest.mark.parametrize('count',[5,8])
def test_full_batch_correction_recompute_and_cache(tmp_path,monkeypatch,count):
    monkeypatch.setattr(db,'DATA',tmp_path)
    monkeypatch.setattr('backend.main.DATA',tmp_path)
    monkeypatch.setattr('backend.main.configured',lambda:True)
    parsed=[]
    def parse(path,paper_id,job_id):
        parsed.append(paper_id)
        return [Evidence(id=paper_id+'-e1',paper_id=paper_id,text='Method retrieves documents. Limitation: single domain.',page=1)]
    monkeypatch.setattr(pipeline,'parse',parse)
    def call(stage,data,schema,job_id):
        if stage=='metadata':
            return Metadata(title='Test '+data['evidence'][0]['paper_id'][:8],authors=['A'],year=2020,venue=None,task='QA',evidence_ids=[data['evidence'][0]['id']])
        if stage=='extract':
            return Extraction(method_name='Dense retrieval',methods=[Claim(id='m',text='Retrieve documents',evidence_ids=[data['evidence'][0]['id']])],advantages=[],limitations=[Claim(id='l',text='Single domain',evidence_ids=[data['evidence'][0]['id']])],future_work=[],evaluations=[])
        if stage=='classify':
            return Classification(task_ids=['task.qa.open'],method_ids=['method.retrieval.dense'],rationale='Dense retrieval',evidence_ids=[data['evidence'][0]['id']])
        if stage=='verify':
            return Verification(checks=[CheckItem(id=i['id'],status='supported',reason='Mocked test verifier') for i in data['items']])
        if stage=='synthesize':
            return Synthesis(summary=[Claim(id='s',text='Compare '+str(len(data['papers']))+' papers',evidence_ids=[data['evidence'][0]['id']],kind='inference')],relations=[],directions=[],common_gaps=[])
        raise AssertionError(stage)
    monkeypatch.setattr(pipeline,'call',call)
    headers={'X-Requested-With':'PaperMethodAgent'}
    with TestClient(app) as client:
        client.get('/api/session')
        files=[]
        for i in range(count):
            stream=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=100+i,height=100);writer.write(stream)
            files.append(('files',(f'paper-{i}.pdf',stream.getvalue(),'application/pdf')))
        response=client.post('/api/jobs',headers=headers,files=files)
        assert response.status_code==200
        job_id=response.json()['id']
        pipeline.run(db.get(job_id))
        job=client.get('/api/jobs/'+job_id).json()
        assert job['status']=='completed' and len(job['result']['papers'])==count
        paper=job['result']['papers'][0]
        claim=paper['extraction']['limitations'][0]
        edited=client.patch(f"/api/jobs/{job_id}/papers/{paper['id']}",headers=headers,json={'revision':1,'field':'limitations','claim_id':claim['id'],'text':'Only one domain was evaluated','kind':'author_statement','evidence_ids':claim['evidence_ids']})
        assert edited.json()['stale']==1
        assert client.post(f'/api/jobs/{job_id}/regenerate',headers=headers).status_code==200
        pipeline.run(db.get(job_id))
        refreshed=client.get('/api/jobs/'+job_id).json()
        assert refreshed['status']=='completed' and refreshed['stale']==0
        assert refreshed['result']['papers'][0]['revision']==2
        assert refreshed['result']['papers'][0]['extraction']['limitations'][0]['status']=='supported'
        assert len(parsed)==count, 'Human correction must not reparse PDFs'
        duplicate=client.post('/api/jobs',headers=headers,files=files)
        assert duplicate.json()['reused'] and duplicate.json()['id']==job_id
        assert f'Compare {count} papers' in client.get(f'/api/jobs/{job_id}/report').text
