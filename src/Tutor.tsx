import { useEffect, useRef, useState } from 'react';
import { X, Send, BookOpen, GraduationCap, Plus, Loader2, Download, ChevronDown } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import './tutor.css';
import { api, download } from './api';
import type { Job, Status } from './types';

type Citation = { evidence_id:string; paper_id:string; title:string; text:string; page:number|null; section:string };
type Block = {kind:'paper_fact'|'background'|'hypothesis';text:string;status:Status;reason:string;citations:Citation[]};
type Answer = {blocks:Block[];question:string;suggestions:string[];demo?:boolean};
type Options = {question:string;activity:'ask'|'explain'|'compare'|'quiz';mode:'direct'|'guided';depth:'intuitive'|'technical';paper_only:boolean;evidence_ids:string[]};
type Message = {id:string;status:string;stage:string;error:string|null;stale:boolean;request:Options;answer:Answer|null;calls:number;cache_hits:number;input_tokens:number;output_tokens:number};
type Thread = {id:string;scope:string;created:number};
export type TutorSeed = {paperIds?:string[];evidenceIds?:string[];question?:string};
const kinds={paper_fact:'论文事实',background:'背景讲解',hypothesis:'研究假设 · 待验证'};
const states={supported:'有据支持',partial:'部分支持',unsupported:'未通过核验',unverified:'待核验'};
const activities=[['ask','问论文'],['explain','讲明白'],['compare','比较论文'],['quiz','检查理解']] as const;

function RichText({text}:{text:string}) {
  return <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[[rehypeKatex,{trust:false,strict:'warn',throwOnError:false,maxExpand:100,maxSize:10}]]}
    components={{a:({children})=><span>{children}</span>,img:()=>null}}>{text}</Markdown>;
}

export default function Tutor({job,connected,seed,onClose,onEvidence}:{job:Job;connected:boolean;seed?:TutorSeed;onClose:()=>void;onEvidence:(ids:string[])=>void}) {
  const papers=job.result?.papers||[];
  const [scope,setScope]=useState<string[]>(seed?.paperIds||papers.map(p=>p.id));
  const [threads,setThreads]=useState<Thread[]>([]);
  const [thread,setThread]=useState('');
  const [messages,setMessages]=useState<Message[]>([]);
  const [draft,setDraft]=useState(seed?.question||'');
  const [activity,setActivity]=useState<Options['activity']>('ask');
  const [mode,setMode]=useState<Options['mode']>('direct');
  const [depth,setDepth]=useState<Options['depth']>('intuitive');
  const [paperOnly,setPaperOnly]=useState(false);
  const [pinned,setPinned]=useState(seed?.evidenceIds||[]);
  const [error,setError]=useState('');
  const [sending,setSending]=useState(false);
  const [service,setService]=useState<{online:boolean;configured:boolean}|null>(null);
  const end=useRef<HTMLDivElement>(null);
  const pending=messages.some(m=>['queued','running'].includes(m.status));
  const requestRef=useRef<{key:string;id:string}|null>(null);
  const input=useRef<HTMLTextAreaElement>(null);
  const live=connected && job.id!=='local-demo';
  useEffect(()=>{input.current?.focus();},[]);
  useEffect(()=>{
    if(!live)return;
    let disposed=false;
    async function refresh(){
      try {
        const [status,list]=await Promise.all([api<typeof service>('/tutor/status'),api<Thread[]>(`/tutor/jobs/${job.id}/threads`)]);
        if(!disposed){setService(status);setThreads(list);}
      }catch(e){if(!disposed)setError((e as Error).message);}
    }
    void refresh();const timer=setInterval(refresh,10000);
    return()=>{disposed=true;clearInterval(timer);};
  },[job.id,live]);
  useEffect(()=>{
    if(!thread)return;
    let disposed=false;
    async function refresh(){
      try {
        const value=await api<{messages:Message[];paper_ids:string[]}>(`/tutor/threads/${thread}`);
        if(!disposed){setMessages(value.messages);setScope(value.paper_ids);}
      }catch(e){if(!disposed)setError((e as Error).message);}
    }
    void refresh(); const timer=setInterval(refresh,2500);
    return()=>{disposed=true;clearInterval(timer);};
  },[thread]);
  useEffect(()=>{end.current?.scrollIntoView({block:'nearest',behavior:'smooth'});},[messages.length,messages.at(-1)?.status]);
  function newThread(){setThread('');setMessages([]);setPinned([]);setError('');requestRef.current=null;}
  async function send(question=draft){
    if(!question.trim()||sending||pending)return;
    setSending(true);setError('');
    try {
      let id=thread;
      if(!id){
        const created=await api<{id:string}>(`/tutor/jobs/${job.id}/threads`,{method:'POST',body:JSON.stringify({paper_ids:scope}),headers:{'Content-Type':'application/json'}});
        id=created.id;setThread(id);
      }
      const body:Options={question:question.trim(),activity,mode,depth,paper_only:paperOnly,evidence_ids:pinned};
      const key=JSON.stringify([id,body]);
      if(requestRef.current?.key!==key)requestRef.current={key,id:crypto.randomUUID()};
      await api(`/tutor/threads/${id}/messages`,{method:'POST',body:JSON.stringify({...body,request_id:requestRef.current.id}),headers:{'Content-Type':'application/json'}});
      setDraft('');setPinned([]);requestRef.current=null;
      const value=await api<{messages:Message[]}>(`/tutor/threads/${id}`);setMessages(value.messages);
    }catch(e){setError((e as Error).message);}finally{setSending(false);}
  }
  function exportChat(){
    const text=['# 研脉论文助教',...papers.filter(p=>scope.includes(p.id)).map(p=>'- '+p.metadata.title),
      ...messages.flatMap(m=>['\n## '+m.request.question,m.stale?'> 来源已更新，以下回答基于旧版本。':'',
      ...(m.answer?.blocks.flatMap(b=>[`\n### ${kinds[b.kind]} · ${states[b.status]}`,b.text,
        ...b.citations.map(c=>`> ${c.title} · ${c.page?'PDF 第 '+c.page+' 页':'页码未知'} · ${c.evidence_id}\n> ${c.text.replace(/\n/g,'\n> ')}`)])||[m.error||m.stage]),m.answer?.question||''])].join('\n');
    download('paper-tutor.md',text);
  }
  return <aside className="tutor-panel" aria-label="AI 论文助教">
    <header className="tutor-head"><div><GraduationCap size={23}/><div><strong>论文助教</strong><small>理解方法，回到原文</small></div></div>
      <button className="icon-button" aria-label="收起助教" onClick={onClose}><X size={20}/></button></header>
    <div className="tutor-controls">
      <div className="tutor-toolbar"><select aria-label="助教历史会话" value={thread} onChange={e=>{setThread(e.target.value);setMessages([]);setPinned([]);setError('');}}>
        <option value="">新对话</option>{thread&&!threads.some(t=>t.id===thread)&&<option value={thread}>当前对话 · {scope.length} 篇</option>}{threads.map((t,i)=><option value={t.id} key={t.id}>对话 {threads.length-i} · {JSON.parse(t.scope).length} 篇</option>)}</select>
        <button className="icon-button" onClick={newThread} aria-label="新建助教对话" disabled={sending}><Plus size={18}/></button>
        <button className="icon-button" onClick={exportChat} disabled={!messages.length} aria-label="导出助教对话"><Download size={18}/></button></div>
      <details><summary>阅读范围 · {scope.length} 篇 <ChevronDown size={14}/></summary>
        {thread&&<small>当前对话范围固定；新建对话可重新选择。</small>}
        {papers.map(p=><label className="tutor-paper" key={p.id}><input type="checkbox" checked={scope.includes(p.id)} disabled={!!thread||sending} onChange={e=>setScope(e.target.checked?[...scope,p.id]:scope.filter(id=>id!==p.id))}/>{p.metadata.title}</label>)}</details>
      <div className="tutor-modes">{activities.map(([id,label])=><button key={id} className={activity===id?'selected':''} onClick={()=>setActivity(id)} aria-pressed={activity===id}>{label}</button>)}</div>
      <div className="tutor-options"><select aria-label="教学方式" value={mode} onChange={e=>setMode(e.target.value as typeof mode)}><option value="direct">直接讲解</option><option value="guided">启发引导</option></select>
        <select aria-label="讲解深度" value={depth} onChange={e=>setDepth(e.target.value as typeof depth)}><option value="intuitive">直观易懂</option><option value="technical">技术细节</option></select>
        <label><input type="checkbox" checked={paperOnly} onChange={e=>setPaperOnly(e.target.checked)}/>仅依据论文</label></div>
    </div>
    <div className="tutor-conversation" aria-live="polite" aria-relevant="additions text">
      {job.result?.mode==='demo'&&<p className="tutor-notice">当前是虚构教学样例，回答不能作为真实科研引用。</p>}
      {!live?<p className="tutor-notice">当前为静态预览。请打开已部署网站并选择分析任务使用助教。</p>:service&&!service.configured?<p className="tutor-notice">助教模型尚未配置。</p>:service&&!service.online?<p className="tutor-notice">助教暂时离线，稍后会自动检查连接。</p>:null}
      {!messages.length&&<div className="tutor-welcome"><BookOpen size={30}/><h3>从你正在读的地方开始</h3><p>选择论文，问一个具体问题。引用会带你回到原文。</p>
        {['用直观的方式解释这篇论文的核心方法。','作者明确承认了哪些局限？','围绕当前方法给我一道理解题。'].map(q=><button key={q} onClick={()=>{setDraft(q);if(q.includes('理解题'))setActivity('quiz');input.current?.focus();}}>{q}</button>)}</div>}
      {messages.map(m=><article className="tutor-turn" key={m.id}>
        <div className="tutor-user"><small>{activities.find(a=>a[0]===m.request.activity)?.[1]} · {m.request.mode==='guided'?'引导':'直接'} · {m.request.depth==='technical'?'技术细节':'直观'}</small><p>{m.request.question}</p></div>
        {m.stale&&<p className="tutor-notice">论文来源已更新。此回答基于旧版本，请重新提问。</p>}
        {m.answer?<div className="tutor-answer">{m.answer.blocks.map((b,i)=><section key={i} className={'tutor-block '+b.kind}>
          <div className="tutor-block-label"><span>{kinds[b.kind]}</span><span className={'badge '+b.status}>{states[b.status]}</span></div>
          <RichText text={b.text}/>
          {b.status!=='supported'&&<small className="tutor-reason">{b.reason}</small>}
          {b.citations.map(c=><details className="tutor-citation" key={c.evidence_id}><summary><BookOpen size={13}/>{c.title} · {c.page?`第 ${c.page} 页`:'页码未知'}</summary>
            <blockquote>{c.text}</blockquote><button className="evidence-link" onClick={()=>onEvidence([c.evidence_id])}>查看完整证据块</button>
            {job.result?.mode==='live'&&<a className="evidence-link" href={`/api/jobs/${job.id}/papers/${c.paper_id}/pdf#page=${c.page||1}`} target="_blank" rel="noreferrer">打开原 PDF</a>}</details>)}
        </section>)}
          {m.answer.question&&<div className="tutor-followup"><strong>继续想一想</strong><RichText text={m.answer.question}/></div>}
          <div className="tutor-suggestions">{m.answer.suggestions.map((s,i)=><button key={i} onClick={()=>{setDraft(s);input.current?.focus();}}>{s}</button>)}</div>
          <small className="tutor-usage">{m.cache_hits>0?`复用 ${m.cache_hits} 项缓存 · `:''}{m.calls} 次调用 · {m.input_tokens+m.output_tokens} tokens</small>
        </div>:m.error?<p className="tutor-notice" role="alert">{m.error}<button onClick={()=>setDraft(m.request.question)}>重新编辑问题</button></p>:<p className="tutor-progress"><Loader2 className="spin" size={16}/>{m.stage}，核验后显示回答</p>}
      </article>)}<div ref={end}/>
    </div>
    <form className="tutor-compose" onSubmit={e=>{e.preventDefault();void send();}}>
      {pinned.length>0&&<div className="tutor-anchor">已带入 {pinned.length} 条原文证据 <button type="button" onClick={()=>setPinned([])}>清除</button></div>}
      {error&&<p className="tutor-error" role="alert">{error}</p>}
      <textarea ref={input} aria-label="向论文助教提问" placeholder={activity==='quiz'?'输入要练习的概念，或提交你的回答…':'例如：为什么这里需要对注意力分数进行缩放？'} value={draft} maxLength={3000} onChange={e=>setDraft(e.target.value)} rows={3}/>
      <div><button className="button primary" type="submit" disabled={!live||!service?.online||!service?.configured||!scope.length||!draft.trim()||pending||sending||['queued','running'].includes(job.status)}>
        {sending||pending?<Loader2 className="spin" size={16}/>:<Send size={16}/>}发送</button></div>
    </form>
  </aside>;
}
