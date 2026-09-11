"""Session-scoped tutor API and a bounded evidence-first conversation runner."""
import json
import os
import re
import time
from fastapi import APIRouter, Request, HTTPException
from . import db, llm
from .config import configured
from .schemas import Paper
from .tutor_schemas import TutorThreadInput, TutorRequest, TutorQuery, TutorAnswer, TutorChecks
from .tutor_prompts import VERSION
from .tutor_retrieval import retrieve

router = APIRouter(prefix='/api/tutor', tags=['tutor'])

def papers_for(thread):
    job=db.get(thread['job'],thread['session'])
    if not job or not job['result']:
        raise HTTPException(404,'论文任务不存在或已过期。')
    ids=json.loads(thread['scope'])
    papers=[Paper.model_validate(p) for p in job['result']['papers'] if p['id'] in ids]
    if len(papers)!=len(ids):
        raise HTTPException(409,'论文范围已变化，请新建助教会话。')
    return job,papers

def snapshot(papers):
    return db.digest([p.model_dump() for p in sorted(papers,key=lambda p:p.id)])

def thread_owned(thread_id, request):
    from .main import session
    sid=session(request)
    with db.connection() as c:
        row=c.execute('SELECT * FROM tutor_threads WHERE id=? AND session=?',(thread_id,sid)).fetchone()
    if not row:
        raise HTTPException(404,'助教会话不存在。')
    return dict(row)

def present(row, current):
    item=dict(row)
    result={k:item[k] for k in ('id','status','stage','error','calls','input_tokens','output_tokens','cache_hits','created')}
    result.update(request=json.loads(item['request']),answer=json.loads(item['answer']) if item['answer'] else None,
                  stale=item['snapshot']!=current)
    return result

@router.get('/status')
def tutor_status(request: Request):
    from .main import session
    session(request)
    with db.connection() as c:
        row=c.execute('SELECT heartbeat FROM tutor_worker_state WHERE id=1').fetchone()
    return {'configured':configured(),'online':bool(row and time.time()-row[0]<20),
            'daily_turns':int(os.getenv('TUTOR_DAILY_TURNS','20'))}

@router.get('/jobs/{job_id}/threads')
def threads(job_id: str, request: Request):
    from .main import owned
    owned(job_id,request)
    from .main import session
    with db.connection() as c:
        return [dict(r) for r in c.execute('SELECT id,scope,created FROM tutor_threads WHERE job=? AND session=? ORDER BY created DESC LIMIT 30',(job_id,session(request))).fetchall()]

@router.post('/jobs/{job_id}/threads')
def create_thread(job_id: str, value: TutorThreadInput, request: Request):
    from .main import owned,session
    job=owned(job_id,request)
    available={p['id'] for p in (job['result'] or {}).get('papers',[])}
    if len(set(value.paper_ids))!=len(value.paper_ids) or not set(value.paper_ids)<=available:
        raise HTTPException(422,'请选择当前任务中的有效论文。')
    sid=session(request)
    with db.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT count(*) FROM tutor_threads WHERE session=?',(sid,)).fetchone()[0]>=100:
            raise HTTPException(429,'当前会话的助教对话数量已达上限。')
        ident=db.uid()
        c.execute('INSERT INTO tutor_threads VALUES(?,?,?,?,?)',(ident,sid,job_id,json.dumps(sorted(value.paper_ids)),time.time()))
    return {'id':ident}

@router.get('/threads/{thread_id}')
def history(thread_id: str, request: Request):
    thread=thread_owned(thread_id,request)
    _,papers=papers_for(thread)
    current=snapshot(papers)
    with db.connection() as c:
        rows=c.execute('SELECT * FROM tutor_tasks WHERE thread=? ORDER BY created DESC LIMIT 50',(thread_id,)).fetchall()
    return {'id':thread_id,'paper_ids':json.loads(thread['scope']),
            'messages':[present(row,current) for row in reversed(rows)]}

@router.post('/threads/{thread_id}/messages')
def enqueue(thread_id: str, value: TutorRequest, request: Request):
    thread=thread_owned(thread_id,request)
    job,papers=papers_for(thread)
    if not configured():
        raise HTTPException(503,'助教模型尚未配置。')
    if job['status'] in ('queued','running'):
        raise HTTPException(409,'论文正在分析，请完成后再提问。')
    if value.activity=='compare' and len(papers)<2:
        raise HTTPException(422,'比较模式需要至少选择两篇论文。')
    allowed={e.id for p in papers for e in p.evidence}
    if not set(value.evidence_ids)<=allowed:
        raise HTTPException(422,'引用不属于当前助教论文范围。')
    now=time.time()
    current=snapshot(papers)
    content=value.model_dump(exclude={'request_id'})
    with db.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM tutor_tasks WHERE thread=? AND request_id=?',(thread_id,value.request_id)).fetchone()
        if old:
            if json.loads(old['request'])!=content:
                raise HTTPException(409,'重复请求标识对应了不同的问题。')
            return {'id':old['id'],'reused':True}
        if c.execute("SELECT 1 FROM tutor_tasks WHERE thread=? AND status IN ('queued','running')",(thread_id,)).fetchone():
            raise HTTPException(409,'本轮仍在处理，请等待完成。')
        rows=c.execute("SELECT request,answer FROM tutor_tasks WHERE thread=? AND status='completed' AND snapshot=? ORDER BY created DESC LIMIT 4",(thread_id,current)).fetchall()
        context=[]
        for row in reversed(rows):
            previous=json.loads(row['answer'])
            context.append({'user':json.loads(row['request'])['question'],
                            'assistant':{'blocks':[{k:b[k] for k in ('kind','text','status')} for b in previous['blocks']],
                                         'question':previous['question']}})
        # Keep context bounded; assistant history is never promoted to source evidence.
        while len(json.dumps(context,ensure_ascii=False))>12000:
            context.pop(0)
        fingerprint=db.digest({'session':thread['session'],'job':thread['job'],'scope':thread['scope'],
             'snapshot':current,'request':content,'history':context,'version':VERSION,
             'model':os.getenv('LLM_MODEL'),'base':os.getenv('LLM_BASE_URL'),
             'thinking':os.getenv('LLM_THINKING'),'format':os.getenv('LLM_JSON_SCHEMA')})
        cached=c.execute("SELECT answer FROM tutor_tasks WHERE fingerprint=? AND status='completed' ORDER BY created DESC LIMIT 1",(fingerprint,)).fetchone()
        count=c.execute('SELECT count(*) FROM tutor_tasks t JOIN tutor_threads h ON h.id=t.thread WHERE h.session=? AND t.created>?',(thread['session'],now-86400)).fetchone()[0]
        total=c.execute('SELECT count(*) FROM tutor_tasks WHERE created>?',(now-86400,)).fetchone()[0]
        if count>=int(os.getenv('TUTOR_DAILY_TURNS','20')) or total>=int(os.getenv('TUTOR_GLOBAL_DAILY_TURNS','200')):
            raise HTTPException(429,'今天的助教轮次额度已用完。')
        active=c.execute("SELECT count(*) FROM tutor_tasks t JOIN tutor_threads h ON h.id=t.thread WHERE h.session=? AND t.status IN ('queued','running')",(thread['session'],)).fetchone()[0]
        if active>=2:
            raise HTTPException(429,'已有两个助教请求在排队，请稍后再试。')
        ident=db.uid()
        c.execute('INSERT INTO tutor_tasks(id,thread,request_id,fingerprint,snapshot,request,history,status,stage,answer,cache_hits,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (ident,thread_id,value.request_id,fingerprint,current,json.dumps(content),json.dumps(context),
                   'completed' if cached else 'queued','已复用回答' if cached else '排队中',cached['answer'] if cached else None,1 if cached else 0,now,now))
    return {'id':ident,'reused':bool(cached)}

class TutorMeter:
    def __init__(self, task, session):
        self.task=task
        self.scope='tutor:'+session
        self.usage_id=None
    def before_call(self, max_tokens, input_bytes=0):
        with db.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT calls FROM tutor_tasks WHERE id=?',(self.task,)).fetchone()
            if not row or row[0]>=5:
                raise llm.ProviderError('本轮助教已达到 5 次调用上限，请缩小问题后重试。')
            used=c.execute('SELECT COALESCE(sum(tokens),0) FROM tutor_usage WHERE created>?',(time.time()-86400,)).fetchone()[0]
            reserve=max_tokens+input_bytes
            if used+reserve>int(os.getenv('TUTOR_DAILY_TOKENS','1000000')):
                raise llm.ProviderError('今天的助教 token 额度不足，请稍后再试。')
            self.usage_id=db.uid()
            c.execute('INSERT INTO tutor_usage VALUES(?,?,?,?)',(self.usage_id,self.task,reserve,time.time()))
            c.execute('UPDATE tutor_tasks SET calls=calls+1,updated=? WHERE id=?',(time.time(),self.task))
    def record_usage(self, usage):
        if not usage:
            return # retain conservative reservation when provider usage is unavailable
        incoming=max(0,int(usage.get('prompt_tokens',0)))
        outgoing=max(0,int(usage.get('completion_tokens',0)))
        with db.connection() as c:
            c.execute('UPDATE tutor_usage SET tokens=? WHERE id=?',(incoming+outgoing,self.usage_id))
            c.execute('UPDATE tutor_tasks SET input_tokens=input_tokens+?,output_tokens=output_tokens+? WHERE id=?',(incoming,outgoing,self.task))
    def cache_hit(self):
        with db.connection() as c:
            c.execute('UPDATE tutor_tasks SET cache_hits=cache_hits+1 WHERE id=?',(self.task,))

def set_state(task, stage, **fields):
    assert fields.keys()<={'status','answer','error'}
    fields.update(stage=stage,updated=time.time())
    with db.connection() as c:
        c.execute('UPDATE tutor_tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',(*fields.values(),task))

def ground(answer, checks, evidence, paper_only=False):
    results=[]
    for i,block in enumerate(answer.blocks):
        if paper_only and block.kind=='background':
            continue
        matches=[v for v in checks.checks if v.index==i]
        status,reason=('unverified','核验结果缺失或重复。')
        if len(matches)==1:
            status,reason=matches[0].status,matches[0].reason
        refs=list(dict.fromkeys(block.evidence_ids))
        if block.kind!='background' and (not refs or any(ref not in evidence for ref in refs)):
            status,reason='unsupported','缺少属于本次检索范围的有效原文证据。'
        if block.kind=='background' and status=='supported':
            status,reason='unverified','背景讲解，不作为论文事实。'
        # Retrieved excerpts cannot establish absence across the entire paper.
        if status=='supported' and re.search(r'(?:论文|作者|研究|文中|文献)[^。！？\n]{0,180}(?:未报告|未提及|未涉及|没有出现|没有提供|并无)',block.text):
            status,reason='unverified','本次只检索了部分原文，无法据此确认全文未报告某项内容，请核对完整 PDF。'
        # Unsupported assertions are withheld, never shown as teaching facts.
        text=block.text if status!='unsupported' else '这部分回答未通过证据核验，已隐藏；请查看原文或缩小问题。'
        results.append({'kind':block.kind,'text':text,'status':status,'reason':reason,
                        'citations':[evidence[r] for r in refs if r in evidence]})
    return {'blocks':results,'question':answer.question,'suggestions':answer.suggestions}

def run(task_id):
    with db.connection() as c:
        task=dict(c.execute('SELECT * FROM tutor_tasks WHERE id=?',(task_id,)).fetchone())
        thread=dict(c.execute('SELECT * FROM tutor_threads WHERE id=?',(task['thread'],)).fetchone())
    job,papers=papers_for(thread)
    if snapshot(papers)!=task['snapshot']:
        raise llm.ProviderError('论文已修订，请依据新版本重新提问。')
    request=TutorRequest(request_id='internal-request',**json.loads(task['request']))
    meter=TutorMeter(task_id,thread['session'])
    context=json.loads(task['history'])
    keywords=[]
    set_state(task_id,'检索论文证据')
    if any('\u4e00'<=ch<='\u9fff' for ch in request.question) or context:
        query=llm.call('tutor_query',{'question':request.question,'history':context,
                    'papers':[p.metadata.title for p in papers]},TutorQuery,meter=meter,output_limit=350)
        keywords=query.keywords
    excerpts=retrieve(papers,request.question,keywords,request.evidence_ids)
    if not excerpts:
        response={'blocks':[],'question':'当前所选材料中未检索到相关证据。请指定方法名称、原文术语或选择一段证据再提问。','suggestions':[]}
    else:
        set_state(task_id,'组织讲解')
        data={'question':request.question,'activity':request.activity,'mode':request.mode,
              'depth':request.depth,'paper_only':request.paper_only,'history':context,
              'papers':[{'id':p.id,'title':p.metadata.title} for p in papers],
              'evidence':excerpts,'demo':job['result'].get('mode')=='demo'}
        answer=llm.call('tutor_answer',data,TutorAnswer,meter=meter,output_limit=2400)
        set_state(task_id,'核验引用与条件')
        checks=llm.call('tutor_verify',{'question':request.question,
                       'blocks':[dict(index=i,**b.model_dump()) for i,b in enumerate(answer.blocks)],
                       'evidence':excerpts},TutorChecks,meter=meter,output_limit=1600)
        titles={p.id:p.metadata.title for p in papers}
        sources={e['evidence_id']:{**e,'title':titles[e['paper_id']]} for e in excerpts}
        response=ground(answer,checks,sources,request.paper_only)
    response['demo']=job['result'].get('mode')=='demo'
    _,latest=papers_for(thread)
    stage='来源已更新，请重新提问' if snapshot(latest)!=task['snapshot'] else '回答完成'
    set_state(task_id,stage,status='completed',answer=json.dumps(response,ensure_ascii=False))
