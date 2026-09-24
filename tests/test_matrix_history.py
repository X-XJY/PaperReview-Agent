import io,json
from pypdf import PdfReader
from tests.test_tutor import client,setup,send,HEADERS
from backend import db,tutor
from backend.matrix_pdf import matrix_pdf


def test_history_titles_describe_existing_content(client):
    job,papers,thread=setup(client)
    assert papers[0]['metadata']['title'] in client.get('/api/jobs').json()[0]['title']
    response=send(client,thread,question='为什么使用检索增强？')
    assert response.status_code==200
    assert client.get('/api/tutor/jobs/'+job+'/threads').json()[0]['title']=='为什么使用检索增强？'
    # Retrieval must not expose other sessions' titles.
    client.cookies.clear();client.get('/api/session')
    assert client.get('/api/jobs').json()==[]
    assert client.get('/api/tutor/jobs/'+job+'/threads').status_code==404


def test_matrix_pdf_preserves_filter_and_checks_ownership(client):
    job,papers,_=setup(client)
    route='/api/jobs/'+job+'/matrix.pdf'
    assert client.post(route,headers=HEADERS,json={'paper_ids':['foreign']}).status_code==422
    assert client.post(route,headers=HEADERS,json={'paper_ids':[]}).status_code==422
    response=client.post(route,headers=HEADERS,json={'paper_ids':[papers[0]['id']]})
    assert response.status_code==200 and response.headers['content-type']=='application/pdf'
    pdf=PdfReader(io.BytesIO(response.content));text=''.join(p.extract_text() for p in pdf.pages)
    assert papers[0]['metadata']['title'] in text
    assert papers[1]['metadata']['title'] not in text
    assert '数据集 / 指标' in text
    assert '[U+000A]' not in text
    client.cookies.clear();client.get('/api/session')
    assert client.post(route,headers=HEADERS,json={'paper_ids':[papers[0]['id']]}).status_code==404


def test_matrix_splits_long_cells_without_dropping_text(client):
    _,papers,_=setup(client)
    paper=papers[0]
    paper['extraction']['methods'][0]['text']='长方法细节。'*800+'最终完整内容'
    pdf=PdfReader(io.BytesIO(matrix_pdf([paper])))
    text=''.join(p.extract_text() for p in pdf.pages)
    assert len(pdf.pages)>1 and '最终完整内容' in text
    assert '矩阵为每项前两条内容的节选' in pdf.pages[0].extract_text()
    assert '完整明细' in text
    assert '最终完整内容' not in pdf.pages[0].extract_text()
