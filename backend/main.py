import hashlib
import io
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader
from . import db
from .config import DATA, MAX_FILES, MAX_BYTES, MAX_PAGES, configured
from .pipeline import ONTOLOGY
from .prompts import VERSION
from .report import report
from .schemas import Edit, Paper, Claim

@asynccontextmanager
async def lifespan(app):
    db.init()
    yield

app = FastAPI(title='论文方法梳理智能体',version='0.1.0',lifespan=lifespan)

@app.middleware('http')
async def security(request: Request, call_next):
    if request.method in ('POST','PATCH','DELETE','PUT') and request.url.path.startswith('/api/'):
        if request.headers.get('x-requested-with') != 'PaperMethodAgent':
            return PlainTextResponse('Missing request origin guard',status_code=403)
        origin = request.headers.get('origin')
        allowed_origins = set(os.getenv('ALLOWED_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(','))
        allowed_origins.add(str(request.base_url).rstrip('/'))
        if origin and origin.rstrip('/') not in allowed_origins:
            return PlainTextResponse('Cross-origin request rejected',status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

def session(request):
    sid = request.cookies.get('paper_session','')
    with db.connection() as conn:
        exists = conn.execute('SELECT id FROM sessions WHERE id=? AND created>?',(sid,time.time()-int(os.getenv('SESSION_TTL_DAYS','7'))*86400)).fetchone()
    if not exists:
        raise HTTPException(401,'会话已过期，请刷新页面。')
    return sid

def owned(job_id, request):
    job = db.get(job_id,session(request))
    if not job:
        raise HTTPException(404,'未找到任务。')
    return job

def public(job):
    return {k:v for k,v in job.items() if k not in ('session','payload')}

def pipeline_signature():
    return db.digest({'version':VERSION,'ontology':ONTOLOGY,'model':os.getenv('LLM_MODEL'),'base':os.getenv('LLM_BASE_URL'),'structured':os.getenv('LLM_JSON_SCHEMA'),'thinking':os.getenv('LLM_THINKING'),'max_tokens':os.getenv('LLM_MAX_OUTPUT_TOKENS','10000')})

@app.get('/api/session')
def create_session(request: Request, response: Response):
    try:
        session(request)
    except HTTPException:
        sid = db.uid()
        with db.connection() as conn:
            conn.execute('INSERT INTO sessions VALUES(?,?)',(sid,time.time()))
        response.set_cookie('paper_session',sid,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false').lower() == 'true',max_age=int(os.getenv('SESSION_TTL_DAYS','7'))*86400)
    with db.connection() as conn:
        worker = conn.execute('SELECT heartbeat FROM worker_state WHERE id=1').fetchone()
    return {'configured':configured(),'worker_online':bool(worker and time.time()-worker['heartbeat']<20),'max_files':MAX_FILES,'max_file_mb':MAX_BYTES//1024//1024,'max_pages':MAX_PAGES}

@app.get('/api/health')
def health():
    return {'status':'ok'}

@app.get('/api/ontology')
def ontology():
    return ONTOLOGY

@app.get('/api/jobs')
def list_jobs(request: Request):
    sid = session(request)
    with db.connection() as conn:
        rows = conn.execute('SELECT id,status,stage,created,stale FROM jobs WHERE session=? ORDER BY created DESC LIMIT 50',(sid,)).fetchall()
    return [dict(row) for row in rows]

@app.delete('/api/jobs/{job_id}')
def delete_job(job_id: str, request: Request):
    sid=session(request)
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT status FROM jobs WHERE id=? AND session=?',(job_id,sid)).fetchone()
        if not row:
            raise HTTPException(404,'未找到任务。')
        if row['status'] in ('queued','running') or conn.execute("SELECT 1 FROM tutor_tasks t JOIN tutor_threads h ON h.id=t.thread WHERE h.job=? AND t.status IN ('queued','running')",(job_id,)).fetchone():
            raise HTTPException(409,'任务或助教仍在处理中，请完成后再删除。')
        conn.execute('DELETE FROM tutor_tasks WHERE thread IN (SELECT id FROM tutor_threads WHERE job=?)',(job_id,))
        conn.execute('DELETE FROM tutor_threads WHERE job=?',(job_id,))
        conn.execute('DELETE FROM revisions WHERE job=?',(job_id,))
        conn.execute('DELETE FROM jobs WHERE id=?',(job_id,))
    return {'deleted':True}

@app.get('/api/jobs/{job_id}')
def get_job(job_id: str, request: Request):
    return public(owned(job_id,request))

def insert_job(conn, sid, payload, result=None, mode='live'):
    job_id,now = db.uid(),time.time()
    conn.execute('INSERT INTO jobs(id,session,status,stage,payload,result,created,updated) VALUES(?,?,?,?,?,?,?,?)',(job_id,sid,'completed' if mode=='demo' else 'queued','示例分析' if mode=='demo' else '排队中',json.dumps(payload),json.dumps(result,ensure_ascii=False) if result else None,now,now))
    return job_id

@app.post('/api/jobs/demo')
def demo(request: Request):
    sid = session(request)
    result = json.loads(Path('public/demo.json').read_text(encoding='utf-8'))
    with db.connection() as conn:
        existing = conn.execute("SELECT id FROM jobs WHERE session=? AND stage='示例分析' ORDER BY created DESC LIMIT 1",(sid,)).fetchone()
        if existing:
            return {'id':existing['id']}
        job_id = insert_job(conn,sid,{'files':[]},result,'demo')
    return {'id':job_id}

@app.post('/api/jobs')
async def upload(request: Request, files: list[UploadFile] = File(...)):
    sid = session(request)
    if not configured():
        raise HTTPException(503,'真实解析尚未配置。请在服务端 .env 设置 MinerU 和模型 API 后重启。')
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(422,f'每批支持 1—{MAX_FILES} 篇 PDF。')
    prepared,seen = [],set()
    try:
        for upload_file in files:
            content = bytearray()
            while part := await upload_file.read(1024*1024):
                content.extend(part)
                if len(content)>MAX_BYTES:
                    raise HTTPException(413,'单篇 PDF 超过大小限制。')
            name = Path((upload_file.filename or 'paper.pdf').replace('\\','/')).name
            if not name.lower().endswith('.pdf') or not content.startswith(b'%PDF-'):
                raise HTTPException(422,'仅支持有效 PDF 文件。')
            try:
                reader = PdfReader(io.BytesIO(content),strict=False)
                if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
                    raise ValueError()
            except Exception:
                raise HTTPException(422,f'{name} 无法读取、已加密或超过 {MAX_PAGES} 页限制。') from None
            file_hash = hashlib.sha256(content).hexdigest()
            if file_hash in seen:
                continue
            seen.add(file_hash)
            folder = DATA/'files'/sid
            folder.mkdir(parents=True,exist_ok=True)
            path = folder/(file_hash+'.pdf')
            if not path.exists():
                path.write_bytes(content)
            prepared.append({'hash':file_hash,'name':name,'path':str(path)})
    finally:
        for file in files:
            await file.close()
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        jobs = conn.execute('SELECT id,status,payload FROM jobs WHERE session=? ORDER BY created DESC',(sid,)).fetchall()
        hashes = sorted(seen)
        for row in jobs:
            old_payload = json.loads(row['payload'])
            if row['status'] in ('queued','running','completed') and old_payload.get('signature') == pipeline_signature() and sorted(f['hash'] for f in old_payload['files']) == hashes:
                return {'id':row['id'],'reused':True}
        # Limit globally as well as by session; opening fresh cookies cannot bypass provider budget.
        rows = conn.execute('SELECT payload FROM jobs WHERE created>?',(time.time()-86400,)).fetchall()
        if sum(len(json.loads(r['payload'])['files']) for r in rows)+len(prepared)>int(os.getenv('DAILY_PAPER_LIMIT','40')):
            raise HTTPException(429,'今天的真实分析额度已用完，请稍后再试。')
        if sum(row['status'] in ('queued','running') for row in jobs)>=2:
            raise HTTPException(429,'当前已有两个任务在处理，请等待完成。')
        job_id = insert_job(conn,sid,{'files':prepared,'signature':pipeline_signature()})
    return {'id':job_id,'reused':False}

@app.patch('/api/jobs/{job_id}/papers/{paper_id}')
def edit_paper(job_id: str, paper_id: str, edit: Edit, request: Request):
    job = owned(job_id,request)
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row['status'] in ('queued','running'):
            raise HTTPException(409,'处理过程中不能编辑，请稍后重试。')
        result = json.loads(row['result']) if row['result'] else None
        if not result:
            raise HTTPException(404,'尚无可编辑结果。')
        paper_data = next((p for p in result['papers'] if p['id']==paper_id),None)
        if not paper_data:
            raise HTTPException(404,'未找到论文。')
        paper = Paper.model_validate(paper_data)
        if paper.revision != edit.revision:
            raise HTTPException(409,'论文版本已变化，请刷新后重新编辑。')
        claim = next((c for c in getattr(paper.extraction,edit.field) if c.id==edit.claim_id),None)
        if not claim and edit.claim_id == 'new':
            claim = Claim(id=f'{paper_id[:12]}-{edit.field}-{db.uid()[:8]}',text=edit.text)
            getattr(paper.extraction,edit.field).append(claim)
        if not claim:
            raise HTTPException(404,'未找到字段。')
        evidence_ids = {e.id for e in paper.evidence}
        if any(e not in evidence_ids for e in edit.evidence_ids) or (edit.kind=='author_statement' and not edit.evidence_ids):
            raise HTTPException(422,'作者陈述必须选择本篇论文中的有效证据。')
        before = json.dumps(paper.model_dump(),ensure_ascii=False)
        claim.text,claim.evidence_ids,claim.kind = edit.text,edit.evidence_ids,edit.kind
        claim.status,claim.reason = 'unverified','人工修改后待核验。'
        paper.revision += 1
        updated = paper.model_dump()
        result['papers'] = [updated if p['id']==paper_id else p for p in result['papers']]
        payload = json.loads(row['payload'])
        payload['dirty_papers'] = sorted(set(payload.get('dirty_papers',[])+[paper_id]))
        conn.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(db.uid(),job_id,paper_id,before,json.dumps(updated,ensure_ascii=False),time.time()))
        conn.execute('UPDATE jobs SET result=?,payload=?,stale=1,updated=? WHERE id=?',(json.dumps(result,ensure_ascii=False),json.dumps(payload),time.time(),job_id))
    return public(db.get(job_id))

@app.get('/api/jobs/{job_id}/revisions')
def revisions(job_id: str, request: Request):
    owned(job_id,request)
    with db.connection() as conn:
        rows = conn.execute('SELECT paper,before_json,after_json,created FROM revisions WHERE job=? ORDER BY created DESC',(job_id,)).fetchall()
    return [{'paper':r['paper'],'before':json.loads(r['before_json']),'after':json.loads(r['after_json']),'created':r['created']} for r in rows]

@app.post('/api/jobs/{job_id}/regenerate')
def regenerate(job_id: str, request: Request):
    job = owned(job_id,request)
    if job['result'] and job['result'].get('mode')=='demo':
        raise HTTPException(409,'示例模式保留人工修改，但不模拟模型重新推导。真实模式配置后可重算。')
    if not configured():
        raise HTTPException(503,'真实解析尚未配置。')
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT status FROM jobs WHERE id=?',(job_id,)).fetchone()
        if row['status'] in ('queued','running'):
            return {'id':job_id}
        conn.execute("UPDATE jobs SET status='queued',stage='排队重算',stale=1,error=NULL,generation=generation+1,updated=? WHERE id=?",(time.time(),job_id))
    return {'id':job_id}

@app.get('/api/jobs/{job_id}/report')
def export_report(job_id: str, request: Request):
    return PlainTextResponse(report(owned(job_id,request)),media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="paper-method-report.md"'})

@app.get('/api/jobs/{job_id}/papers/{paper_id}/pdf')
def pdf(job_id: str, paper_id: str, request: Request):
    job = owned(job_id,request)
    file = next((f for f in job['payload']['files'] if f['hash']==paper_id),None)
    if not file:
        raise HTTPException(404,'示例未附带真实 PDF。')
    return FileResponse(file['path'],media_type='application/pdf',filename='paper.pdf',content_disposition_type='inline')

from .tutor import router as tutor_router
app.include_router(tutor_router)

if Path('dist').exists():
    app.mount('/',StaticFiles(directory='dist',html=True),name='frontend')
