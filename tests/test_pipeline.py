import io
import json
import zipfile
from pathlib import Path
import pytest
from backend import db,pipeline,llm
from backend.mineru import unpack,checked_url
from backend.schemas import Evidence,Verification,CheckItem,Paper,Synthesis,Metadata

def test_parser_page_and_chunk_mapping():
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('paper_content_list.json',json.dumps([{'type':'text','text':'Methods','text_level':1,'page_idx':0},{'type':'text','text':'a'*6001,'page_idx':1}]))
    blocks=unpack(output.getvalue(),'p1')
    assert [b.page for b in blocks]==[1,2,2]
    assert len(blocks[1].text)+len(blocks[2].text)==6001
    assert len(set(b.id for b in blocks))==3
    with pytest.raises(RuntimeError):
        checked_url('http://127.0.0.1/private')
    with pytest.raises(RuntimeError):
        checked_url('https://mineru.net.evil.invalid/file')

def test_missing_evidence_and_missing_verifier_item(monkeypatch):
    monkeypatch.setattr(pipeline,'call',lambda *args:Verification(checks=[]))
    e=[Evidence(id='e1',paper_id='p1',text='Context')]
    result=pipeline.verify_items([{'id':'a','text':'Claim','evidence_ids':['invented']},{'id':'b','text':'Claim','evidence_ids':['e1']}],e,'job')
    assert result['a'][0]=='unsupported'
    assert result['b'][0]=='unverified'

def test_long_document_no_silent_truncation():
    evidence=[Evidence(id=str(i),paper_id='p',text='x'*4000) for i in range(40)]
    groups=list(pipeline.chunks(evidence))
    assert [e.id for g in groups for e in g]==[e.id for e in evidence]
    assert len(groups)>1

def test_synthesis_rejects_fabricated_graph_and_single_paper_gap(monkeypatch):
    result=json.loads(Path('public/demo.json').read_text(encoding='utf-8'))
    papers=[Paper.model_validate(p) for p in result['papers']]
    draft=Synthesis.model_validate(result['synthesis'])
    draft.relations[0].source='imaginary-paper'
    draft.common_gaps[0].evidence_ids=['demo-atlas-e2']
    monkeypatch.setattr(pipeline,'call',lambda *args:draft)
    monkeypatch.setattr(pipeline,'verify_items',lambda items,*args:{i['id']:('supported','ok') for i in items})
    checked=pipeline.synthesize(papers,'job')
    assert all(r.source!='imaginary-paper' for r in checked.relations)
    assert checked.common_gaps==[]

def test_model_cache_is_versioned_and_avoids_calls(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path)
    db.init()
    with db.connection() as conn:
        conn.execute("INSERT INTO jobs(id,session,status,stage,payload,created,updated) VALUES('j','s','running','test','{}',0,0)")
    count=[]
    class Response:
        status_code=200
        is_success=True
        def json(self):
            return {'choices':[{'message':{'content':json.dumps({'title':'Example','authors':[],'year':2020,'venue':None,'task':'QA','evidence_ids':['e']})}}],'usage':{'prompt_tokens':10,'completion_tokens':5}}
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,*args,**kwargs):count.append(1);return Response()
    monkeypatch.setattr(llm.httpx,'Client',Client)
    monkeypatch.setenv('LLM_MODEL','test-model')
    llm.call('metadata',{'input':'one'},Metadata,'j')
    llm.call('metadata',{'input':'one'},Metadata,'j')
    assert len(count)==1 and db.get('j')['cache_hits']==1
    monkeypatch.setenv('LLM_MODEL','other-model')
    llm.call('metadata',{'input':'one'},Metadata,'j')
    assert len(count)==2
