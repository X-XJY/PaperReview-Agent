export function relatedNodes(start:string, edges:{source:string;target:string}[], reverse:boolean) {
  const found=new Set<string>();
  if (!start) return found;
  const queue=[start];
  for (let i=0;i<queue.length;i++) for (const e of edges) {
    const next=reverse ? (e.target===queue[i]?e.source:'') : (e.source===queue[i]?e.target:'');
    if (next && next!==start && !found.has(next)) {found.add(next);queue.push(next);}
  }
  return found;
}
