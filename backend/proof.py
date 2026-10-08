"""Durable, evidence-checked proof explanations; no claim of formal verification."""
import json
import os
import re
import time
from typing import Literal
from fastapi import APIRouter, Request, HTTPException
from pydantic import Field
from . import db, llm
from .schemas import Strict, Paper
from .prompts import BASE, PROMPTS

VERSION = 'proof-1'
router = APIRouter(prefix='/api/jobs', tags=['proof'])

class Quote(Strict):
    evidence_id: str
    quote: str = Field(min_length=1)

class Step(Strict):
    id: str
    title: str
    explanation: str
    formula: str
    rule: str
    prerequisites: list[str]
    jump_explanation: str
    kind: Literal['source', 'teaching_addition']
    citations: list[Quote]

class Explanation(Strict):
    target_id: str
    steps: list[Step]
    missing: list[str]

class Check(Strict):
    id: str
    status: Literal['supported', 'partial', 'unsupported', 'unverified']
    reason: str

class Checks(Strict):
    checks: list[Check]
    complete: bool
    completeness_reason: str

PROMPTS['proof_explain'] = BASE + '''对给定目标的证明进行完整中文教学拆解。按原文推导顺序输出 steps，每步给出推导公式 formula、所用规则 rule、前提节点 id prerequisites、说明 explanation、关键跳步解释 jump_explanation。引用 citations 必须逐字复制原文的连续片段，并绑定 evidence_id；每步都须引用。原文明示的步骤 kind=source；为解释数学规则而补充的中间推导 kind=teaching_addition，不得伪称作者原文。不补编缺失证明，不扩展条件或结论，不因存在依赖边就假定证明完整。目标不匹配、证明省略、外部结果缺失均在 missing 指出。禁止用相关定理的证明代替目标的证明，禁止凭记忆补论文内容。'''
PROMPTS['proof_check'] = BASE + '''独立逐项检查讲解是否忠实于目标及其证明原文。每个步骤 id 恰好返回一个 checks。检查公式、使用规则、前提、解释、跳步补充是否有依据且数学推导有效；教学补充必须是从给定前提能推出的说明，不能冒充原文。supported 仅为自动语义核验通过，不是形式化证明。complete 只有原文证明存在且讲解覆盖其全部实质步骤、目标与适用条件一致、没有未解决跳步时才可 true。缺少证据、错误目标、外部结果未给出、作者省略证明时 complete=false。不得因讲解自己声称完整就判完整。'''

def normalize(text):
    return re.sub(r'\s+', '', text)

def context(paper, target):
    node = next((n for n in paper.theory.nodes if n.id == target), None) if paper.theory else None
    if not node or paper.theory.status != 'ready':
        raise HTTPException(409, '请先完成理论核验并选择有效目标。')
    if node.kind not in ('lemma','theorem','proposition','corollary'):
        raise HTTPException(400, '定义和假设不是需要证明的结论。')
    edges = [e for e in paper.theory.edges if e.target == target]
    refs = set(node.evidence_ids + [r for e in edges for r in e.evidence_ids])
    # Recover standalone proofs even when no intra-paper dependency edge exists.
    number = re.match(r'^(\w+|引理|定理|命题|推论)\s*((?:[A-Za-z]\.?)?\d+(?:\.\d+)*)',node.label)
    active = False
    for block in paper.evidence:
        header = re.match(r'^(?:#+\s*)?(Lemma|Theorem|Proposition|Corollary|引理|定理|命题|推论)\s*((?:[A-Za-z]\.?)?\d+(?:\.\d+)*)(?![\w]|\.\d)',block.text.strip(),re.I)
        explicit = number and re.search(r'(?:Proof\s+(?:of|for)|证明)\s*'+re.escape(number.group(1))+r'\s*'+re.escape(number.group(2))+r'(?![\w]|\.\d)',block.section+' '+block.text,re.I)
        if header:
            active = bool(number and header.group(1).lower()==number.group(1).lower() and header.group(2)==number.group(2))
        if explicit: active = True
        if active: refs.add(block.id)
    for index, block in enumerate(paper.evidence):
        if block.id in set(node.evidence_ids):
            refs.update(e.id for e in paper.evidence[max(0,index-1):index+2])
    evidence=[e for e in paper.evidence if e.id in refs and e.paper_id==paper.id]
    return {'target':node.model_dump(), 'prerequisites':[n.model_dump() for n in paper.theory.nodes if any(e.source==n.id for e in edges)], 'evidence':[e.model_dump() for e in evidence]}

def validate_steps(draft, data):
    available={e['id']:e['text'] for e in data['evidence']}
    known={n['id'] for n in data['prerequisites']} | {data['target']['id']}
    counts={s.id:sum(t.id==s.id for t in draft.steps) for s in draft.steps}
    rejected=[]; valid=[]
    for step in draft.steps:
        ok=counts[step.id]==1 and bool(step.citations) and set(step.prerequisites)<=known
        ok=ok and all(c.evidence_id in available and normalize(c.quote) in normalize(available[c.evidence_id]) for c in step.citations)
        (valid if ok else rejected).append(step)
    return valid,rejected

def generate(data, job_id, caller=None):
    caller = caller or llm.call
    if not any(re.search(r'\bProof\b|证明',e['text']+' '+e['section'],re.I) for e in data['evidence']):
        return {'target_id':data['target']['id'],'steps':[],'missing':['未找到绑定到目标的证明原文；不能根据结论补造完整证明。'],'complete':False,'completeness_reason':'原文证明依据缺失。','notice':'自动检查不等于数学形式化验证。'}
    draft=caller('proof_explain',data,Explanation,job_id)
    if draft.target_id != data['target']['id']:
        raise RuntimeError('讲解目标不匹配，未保存错误结果。请重试。')
    valid,rejected=validate_steps(draft,data)
    checks=caller('proof_check',{'context':data,'explanation':{**draft.model_dump(),'steps':[s.model_dump() for s in valid]}},Checks,job_id) if valid else Checks(checks=[],complete=False,completeness_reason='没有通过引用检查的步骤。')
    result=[]
    for step in valid:
        matches=[c for c in checks.checks if c.id==step.id]
        check=matches[0] if len(matches)==1 else Check(id=step.id,status='unverified',reason='自动核验结果缺失或重复。')
        result.append({**step.model_dump(),'status':check.status,'reason':check.reason})
    complete=bool(result) and checks.complete and not rejected and not draft.missing and all(s['status']=='supported' for s in result)
    return {'target_id':draft.target_id,'steps':result,'missing':draft.missing+[f'{len(rejected)} 个步骤未通过引用或前提检查，已排除。'] if rejected else draft.missing,'complete':complete,'completeness_reason':checks.completeness_reason,'notice':'自动检查包含引用匹配与模型语义核验，不等于数学形式化验证。'}

def present(row):
    r=dict(row)
    return {'id':r['id'],'status':r['status'],'error':r['error'],'result':json.loads(r['result']) if r['result'] else None}

def get_paper(job_id,paper_id,request):
    from .main import owned
    job=owned(job_id,request)
    if job['status']!='completed' or not job['result']: raise HTTPException(409,'请等待论文分析完成。')
    paper=next((Paper.model_validate(p) for p in job['result']['papers'] if p['id']==paper_id),None)
    if not paper: raise HTTPException(404,'未找到论文。')
    return job,paper

@router.api_route('/{job_id}/papers/{paper_id}/proof/{target}',methods=['GET','POST'])
def proof_task(job_id:str,paper_id:str,target:str,request:Request):
    job,paper=get_paper(job_id,paper_id,request)
    data=context(paper,target)
    fingerprint=db.digest({'version':VERSION,'paper':paper.model_dump(),'target':target,'model':os.getenv('LLM_MODEL'),'base':os.getenv('LLM_BASE_URL')})
    with db.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM proof_tasks WHERE job=? AND fingerprint=?',(job_id,fingerprint)).fetchone()
        if request.method=='POST' and (not row or row['status']=='failed'):
            task_id=row['id'] if row else db.uid()
            c.execute('INSERT OR REPLACE INTO proof_tasks(id,job,paper,target,fingerprint,context,status,result,error,created) VALUES(?,?,?,?,?,?,?,NULL,NULL,?)',(task_id,job_id,paper_id,target,fingerprint,json.dumps(data,ensure_ascii=False),'queued',time.time()))
            row=c.execute('SELECT * FROM proof_tasks WHERE id=?',(task_id,)).fetchone()
    return present(row) if row else {'status':'idle','result':None,'error':None}

def run_next():
    with db.connection() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT * FROM proof_tasks WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row: return False
        c.execute("UPDATE proof_tasks SET status='running' WHERE id=?",(row['id'],))
    try:
        result=generate(json.loads(row['context']),row['job'])
        status,error='completed',None
    except Exception as exc:
        result=None;status='failed';error=str(exc) if isinstance(exc,RuntimeError) else '证明讲解失败，可重试。'
    with db.connection() as c:
        c.execute('UPDATE proof_tasks SET status=?,result=?,error=? WHERE id=?',(status,json.dumps(result,ensure_ascii=False) if result else None,error,row['id']))
    return True
