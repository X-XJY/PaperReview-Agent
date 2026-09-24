import { lazy, Suspense } from 'react';
const EvidenceText = lazy(() => import('./EvidenceText'));
export default function LazyEvidenceText({text}:{text:string}) {
  return <Suspense fallback={<span>加载原文…</span>}><EvidenceText text={text}/></Suspense>;
}
