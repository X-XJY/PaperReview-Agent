import {useEffect,useState,useRef} from 'react';
import {api,download} from './api';
import type {Paper} from './types';
import EvidenceText from './LazyEvidenceText';
type Step={id:string;title:string;explanation:string;formula:string;rule:string;prerequisites:string[];jump_explanation:string;kind:'source'|'teaching_addition';citations:{evidence_id:string;quote:string}[];status:string;reason:string};
type Answer={steps:Step[];missing:string[];complete:boolean;completeness_reason:string;notice:string};
type Task={status:string;result:Answer|null;error:string|null};
export default function StructuredProof({paper,target,jobId,onEvidence}:{paper:Paper;target:string;jobId:string;onEvidence:(ids:string[])=>void}) {
 const [task,setTask]=useState<Task>({status:'idle',result:null,error:null});
 const disclosure=useRef<HTMLDetailsElement>(null);
 const [error,setError]=useState(''); const [busy,setBusy]=useState(false);
 const node=paper.theory!.nodes.find(n=>n.id===target)!;
 const path=`/jobs/${jobId}/papers/${paper.id}/proof/${encodeURIComponent(target)}`;
 const formal=['lemma','theorem','proposition','corollary'].includes(node.kind);
 useEffect(()=>{
   let live=true;let timer:ReturnType<typeof setTimeout>;
   setTask({status:'idle',result:null,error:null});setError('');
   async function poll(){try{const t=await api<Task>(path);if(live){setTask(t);timer=setTimeout(poll,t.status==='queued'||t.status==='running'?2000:10000);}}catch(e){if(live)setError(e instanceof Error?e.message:'读取失败');}}
   if(jobId!=='local-demo'&&formal) void poll();
   return()=>{live=false;clearTimeout(timer);};
 },[path,paper.revision,formal]);
 async function start(){setBusy(true);setError('');try{setTask(await api<Task>(path,{method:'POST'}));}catch(e){setError(e instanceof Error?e.message:'生成失败');}finally{setBusy(false);}}
 if(!formal)return null;
 const result=task.result;
 return <section className="structured-proof" aria-label="完整证明讲解">
  <details className="proof-disclosure" ref={disclosure} open><summary><h4>完整证明讲解</h4><span className="proof-collapse-hint">收起讲解 ↑</span><span className="proof-expand-hint">展开讲解 ↓</span></summary><p>自动拆解推导、公式与关键跳步，逐项检查引用和语义。结果会保存，重复打开不会重新生成。</p>
  {jobId==='local-demo'?<p>完整 AI 讲解需要连接后端；下方可直接阅读示例原文步骤。</p>:task.status!=='completed'&&<button disabled={busy||['queued','running'].includes(task.status)} onClick={start}>{busy?'提交中…':task.status==='queued'?'已排队，等待讲解':task.status==='running'?'正在生成并自动核验…':'生成完整证明讲解'}</button>}
  {(error||task.error)&&<p role="alert">{error||task.error}</p>}
  {result&&<><p role="status"><strong>{result.complete?'自动检查：证明覆盖完整':'自动检查：证明覆盖仍有缺口'}</strong> · {result.completeness_reason}</p><p className="muted">{result.notice}</p>
   <article><h5>目标</h5><EvidenceText text={node.statement}/><button onClick={()=>onEvidence(node.evidence_ids)}>查看目标依据</button></article>
   <article><h5>使用的前提</h5>{node.conditions.map((c,i)=><EvidenceText key={i} text={c}/>)}<button onClick={()=>onEvidence(node.evidence_ids)}>查看前提依据</button></article>
   {result.steps.map((s,i)=><article key={s.id} className="proof-step"><h5>步骤 {i+1} · {s.title}</h5><p>{s.kind==='source'?'原文步骤':'教学补充'} · {s.status==='supported'?'自动核验通过':'依据不足，请保留疑问'}</p><EvidenceText text={s.explanation}/><p><strong>使用规则：</strong>{s.rule}</p><p><strong>使用前提：</strong>{s.prerequisites.map(id=>paper.theory!.nodes.find(n=>n.id===id)?.label||id).join('、')||'见引用原文'}</p>{s.formula&&<details><summary>展开推导公式</summary><EvidenceText text={s.formula}/></details>}{s.jump_explanation&&<details><summary>解释关键跳步</summary><EvidenceText text={s.jump_explanation}/></details>}<p className="muted">{s.reason}</p>{s.citations.map((c,j)=><details key={j}><summary>原文依据 {j+1}</summary><EvidenceText text={c.quote}/><button onClick={()=>onEvidence([c.evidence_id])}>定位并高亮原 PDF</button></details>)}</article>)}
   <article><h5>结论</h5><EvidenceText text={node.statement}/><button onClick={()=>onEvidence(node.evidence_ids)}>查看结论依据</button></article>
   {result.missing.length>0&&<div><strong>尚未解决的证明缺口</strong>{result.missing.map((m,i)=><p key={i}>{m}</p>)}</div>}
   <button onClick={()=>download(`${node.label}-证明讲解.md`,[`# ${node.label}`,`目标：${node.statement}`,`前提：${node.conditions.join('；')}`,result.notice,...result.steps.flatMap((s,i)=>[`## 步骤 ${i+1}：${s.title}`,`${s.kind==='source'?'原文步骤':'教学补充'} · ${s.status}`,s.explanation,s.formula,`规则：${s.rule}`,`跳步：${s.jump_explanation}`,...s.citations.map(c=>`[${c.evidence_id}] ${c.quote}`)]),`结论：${node.statement}`,'## 证明缺口',...result.missing].join('\n\n'))}>导出证明讲解</button>
  </>}
  <button className="proof-finish" onClick={()=>{const panel=disclosure.current;if(!panel)return;panel.open=false;requestAnimationFrame(()=>{const next=panel.parentElement?.nextElementSibling as HTMLElement|null;if(next){next.setAttribute('tabindex','-1');next.focus({preventScroll:true});next.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}else panel.querySelector('summary')?.focus();});}}>收起讲解，继续阅读 ↓</button>
  </details>
 </section>;
}
