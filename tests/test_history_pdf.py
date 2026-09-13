import io
from pypdf import PdfReader
from backend.tutor_pdf import conversation_pdf
from tests.test_tutor import client, setup, send, message, HEADERS
from backend import db,tutor


def test_delete_conversation_ownership_and_running_guard(client):
    job,_,thread=setup(client)
    task=send(client,thread).json()['id']
    assert client.delete('/api/tutor/threads/'+thread,headers=HEADERS).status_code==409
    tutor.set_state(task,'done',status='failed')
    cookie=client.cookies.get('paper_session');client.cookies.clear();client.get('/api/session')
    assert client.delete('/api/tutor/threads/'+thread,headers=HEADERS).status_code==404
    client.cookies.clear();client.cookies.set('paper_session',cookie)
    assert client.delete('/api/tutor/threads/'+thread,headers=HEADERS).status_code==200
    assert client.get('/api/tutor/threads/'+thread).status_code==404
    assert client.get('/api/jobs/'+job).status_code==200
    with db.connection() as c:
        assert c.execute('SELECT count(*) FROM tutor_tasks WHERE thread=?',(thread,)).fetchone()[0]==0


def test_delete_analysis_cascades_only_owned_history(client):
    job,_,thread=setup(client)
    task=send(client,thread).json()['id']
    assert client.delete('/api/jobs/'+job,headers=HEADERS).status_code==409
    tutor.set_state(task,'done',status='failed')
    cookie=client.cookies.get('paper_session');client.cookies.clear();client.get('/api/session')
    other,_,_=setup(client)
    assert client.delete('/api/jobs/'+job,headers=HEADERS).status_code==404
    client.cookies.clear();client.cookies.set('paper_session',cookie)
    assert client.delete('/api/jobs/'+job,headers=HEADERS).status_code==200
    assert client.get('/api/jobs/'+job).status_code==404
    assert client.get('/api/tutor/threads/'+thread).status_code==404
    assert db.get(other) is not None


def test_pdf_exports_all_completed_turns_without_internal_details(client):
    _,_,thread=setup(client)
    assert client.get('/api/tutor/threads/'+thread+'/pdf').status_code==409
    # Export must not silently stop at the history UI's 50-message window.
    import os
    from unittest.mock import patch
    with patch.dict(os.environ,{'TUTOR_GLOBAL_DAILY_TURNS':'100'}):
        for index in range(51):
            task=send(client,thread,question=f'用户问题 {index}').json()['id']
            import json
            tutor.set_state(task,'done',status='completed',answer=json.dumps({'blocks':[{'kind':'paper_fact','status':'supported','text':f'中文回答 {index}','citations':[{'text':'PRIVATE_CITATION'}],'reason':'INTERNAL_REASON'}],'question':'继续思考？','suggestions':['SUGGESTION']}))
    response=client.get('/api/tutor/threads/'+thread+'/pdf')
    assert response.status_code==200 and response.headers['content-type']=='application/pdf'
    pdf=PdfReader(io.BytesIO(response.content));text=''.join(p.extract_text() for p in pdf.pages)
    assert '用户问题 50' in text and '中文回答 50' in text and '继续思考' in text
    assert not any(x in text for x in ['PRIVATE_CITATION','INTERNAL_REASON','SUGGESTION'])
    assert len(pdf.pages)>1
    client.cookies.clear();client.get('/api/session')
    assert client.get('/api/tutor/threads/'+thread+'/pdf').status_code==404


def test_pdf_long_answer_and_literal_markup():
    data=conversation_pdf([{'question':'解释注意力 <img src="x">','answer':{'blocks':[{'text':'长段落中文内容。'*1500}],'question':''}}])
    pages=PdfReader(io.BytesIO(data)).pages
    assert len(pages)>2
    assert '长段落中文内容' in pages[-1].extract_text()
