import { useEffect, useRef } from "react";
export function readMemory<T>(key:string, fallback:T):T {
  try { const value=localStorage.getItem(key); return value ? JSON.parse(value) : fallback; } catch { return fallback; }
}
export function writeMemory(key:string,value:unknown) { try { localStorage.setItem(key,JSON.stringify(value)); } catch { /* Reading still works when browser storage is unavailable. */ } }
export function useReadingPosition(key:string) {
  const root=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const element=root.current;if(!element)return;
    const saved=readMemory<{open:Record<string,boolean>;y:number}>(key,{open:{},y:0});
    const restored=new WeakSet<HTMLDetailsElement>();let restoring=true, timer:ReturnType<typeof setTimeout>;
    const identity=(d:HTMLDetailsElement)=> {
      const paper=d.closest('[data-paper-id]')?.getAttribute('data-paper-id')||'guide';
      const section=d.closest('article, .proof-walkthrough, [data-paper-id]')||element;
      const heading=section.querySelector('h4,h5,strong')?.textContent||'';
      const summary=d.querySelector('summary')?.textContent||'';
      const peers=Array.from(section.querySelectorAll('details')).filter(peer=>peer.querySelector('summary')?.textContent===summary);
      return paper+':'+heading+':'+peers.indexOf(d)+':'+summary;
    };
    const restore=()=>{element.querySelectorAll('details').forEach(d=>{if(!restored.has(d)){restored.add(d);const open=saved.open[identity(d)];if(open!==undefined)d.open=open;}});if(restoring&&saved.y)window.scrollTo(0,saved.y);};
    const persist=()=>{if(restoring)return;const open:Record<string,boolean>={...saved.open};element.querySelectorAll('details').forEach(d=>open[identity(d)]=d.open);saved.open=open;saved.y=window.scrollY;writeMemory(key,saved);};
    const stop=()=>{restoring=false;};
    const toggle=()=>{stop();persist();};
    const leave=()=>{stop();persist();};
    restore();const observer=new MutationObserver(restore);observer.observe(element,{childList:true,subtree:true});
    const finish=setTimeout(stop,1800);
    const scroll=()=>{clearTimeout(timer);timer=setTimeout(persist,180);};
    element.addEventListener('toggle',toggle,true);window.addEventListener('scroll',scroll,{passive:true});window.addEventListener('wheel',stop,{passive:true});window.addEventListener('pointerdown',stop);window.addEventListener('keydown',stop);window.addEventListener('pagehide',leave);
    return()=>{persist();observer.disconnect();clearTimeout(timer);clearTimeout(finish);element.removeEventListener('toggle',toggle,true);window.removeEventListener('scroll',scroll);window.removeEventListener('wheel',stop);window.removeEventListener('pointerdown',stop);window.removeEventListener('keydown',stop);window.removeEventListener('pagehide',leave);};
  },[key]);return root;
}
