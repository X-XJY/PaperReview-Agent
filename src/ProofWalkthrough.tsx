import type {Paper} from './types';
import type {TutorSeed} from './Tutor';
import EvidenceText from './LazyEvidenceText';
import StructuredProof from './StructuredProof';

export default function ProofWalkthrough({paper,target,jobId,onEvidence,onTutor}:{jobId:string;paper:Paper;target:string;onEvidence:(ids:string[])=>void;onTutor:(seed:TutorSeed)=>void}) {
  const theory=paper.theory!;
  const node=theory.nodes.find(n=>n.id===target)!;
  const edges=theory.edges.filter(e=>e.target===target);
  // Keep the paper's source order; dependency order is not a proof sequence.
  const refs=new Set(edges.flatMap(e=>e.evidence_ids));
  const blocks=paper.evidence.filter(e=>refs.has(e.id));
  const steps=blocks.flatMap(b=> {
    // Split only explicit prose proof bodies; retain equations and paragraphs intact.
    const marker=/\bProof\s*[:：.]|证明\s*[:：]/i.exec(b.text);
    const body=marker ? b.text.slice(marker.index+marker[0].length).trim() : b.text;
    const pieces=body.includes("$") || body.includes("\\[") ? [body] : body.split(/\n\s*\n|(?<=[。；])|(?<=[.])\s+(?=[A-Z])/).filter(x=>x.trim());
    return pieces.map(text=>({...b,text:text.trim()}));
  });
  const formal=['theorem','lemma','proposition','corollary'].includes(node.kind);
  const evidenceButton=(ids:string[]) => <button disabled={!ids.length} onClick={()=>onEvidence(ids)}>定位原文依据</button>;
  return <section className="proof-walkthrough">
    <StructuredProof key={jobId+paper.id+target} jobId={jobId} paper={paper} target={target} onEvidence={onEvidence}/>
    <h4>原文证明导读 · {node.label}</h4>
    <p className="muted">按原文顺序阅读证明依据。以下为证据导读；依赖关系不自动等于完整证明。</p>
    <article><h5>1 · 目标</h5><EvidenceText text={node.statement}/>{evidenceButton(node.evidence_ids)}</article>
    <article><h5>2 · 使用的前提</h5>
      {node.conditions.map((c,i)=><div key={i}><EvidenceText text={c}/>{evidenceButton(node.evidence_ids)}</div>)}
      {edges.map(e=><div key={e.source}><strong>{theory.nodes.find(n=>n.id===e.source)?.label}</strong><EvidenceText text={e.explanation}/>{evidenceButton(e.evidence_ids)}</div>)}
      {!node.conditions.length&&!edges.length&&<p>尚未提取到可核对的适用前提或证明依赖。</p>}
    </article>
    <article><h5>3 · 推导步骤</h5>
      {!blocks.length&&<p>{formal?'尚无已绑定的证明段落，不能根据结论补造推导。':'该节点是概念或假设，不要求提供证明。'}</p>}
      {steps.map((b,i)=><details key={b.id+":"+i} className="proof-step"><summary>原文步骤 {i+1} · {b.section||'原文'}{b.page ? ` · PDF 第 ${b.page} 页`:''} — 展开原文与公式</summary><EvidenceText text={b.text}/>{evidenceButton([b.id])}<button onClick={()=>onTutor({paperIds:[paper.id],evidenceIds:[...new Set([b.id,...node.evidence_ids,...edges.flatMap(e=>e.evidence_ids)])],question:`请以“${node.label}”为目标，讲解这段证明原文：${b.text}\n按“目标—使用的前提—推导步骤—结论”组织。展开公式中各符号的含义，解释关键跳步和所用规则；每一步引用给定依据。区分原文步骤与教学补充，原文未给出或依据不足时明确说明，不虚构证明。`})}>请助教解释公式与关键跳步</button></details>)}
    </article>
    <article><h5>4 · 结论</h5><EvidenceText text={node.statement}/>{evidenceButton(node.evidence_ids)}<p className="muted">结论仅在上述适用条件下成立；步骤是否完整请结合原文核对。</p></article>
  </section>;
}
