import { useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2 } from "lucide-react";
import * as echarts from "echarts/core";
import { GraphChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer, SVGRenderer } from "echarts/renderers";
import type { Paper, Synthesis } from "./types";
import { dependencyPositions } from "./graphLayout";
import { relatedNodes } from "./graphReading";
echarts.use([GraphChart, TooltipComponent, CanvasRenderer, SVGRenderer]);
export default function Graph({
  papers,
  synthesis,
  onEvidence,
  ariaLabel = "方法演进力导向图；下方另有可访问的关系列表",
  highlightIds,
  allowLayeredLayout = false,
  nodeKinds,
  targetId,
}: {
  papers: Paper[];
  synthesis: Synthesis | null;
  onEvidence: (ids: string[]) => void;
  ariaLabel?: string;
  highlightIds?: string[];
  allowLayeredLayout?: boolean;
  nodeKinds?: Record<string, string>;
  targetId?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const evidenceHandler = useRef(onEvidence);
  evidenceHandler.current = (ids) => { setExpanded(false); onEvidence(ids); };
  const shell = useRef<HTMLDivElement>(null);
  const expandButton = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [exportUrl, setExportUrl] = useState<{url:string;format:string}|null>(null);
  useEffect(()=>()=>{if(exportUrl) URL.revokeObjectURL(exportUrl.url);},[exportUrl]);
  const [zoomPercent, setZoomPercent] = useState(100);
  const [layered, setLayered] = useState(allowLayeredLayout);
  const [focusId, setFocusId] = useState("");
  const [onlyTarget, setOnlyTarget] = useState(false);
  const focusHandler = useRef(setFocusId);
  const allRelations = synthesis?.relations || [];
  const traverse = (start:string, reverse:boolean) => relatedNodes(start, allRelations, reverse);
  const upstream = traverse(focusId, true), downstream = traverse(focusId, false);
  const visible = targetId && onlyTarget ? new Set([targetId, ...traverse(targetId, true)]) : null;
  const shownPapers = papers.filter(p => !visible || visible.has(p.id));
  const kindLabels: Record<string,string> = {definition:"定义", assumption:"假设", lemma:"引理", theorem:"定理", proposition:"命题", corollary:"推论"};
  const kindColors: Record<string,string> = {definition:"#3371ac", assumption:"#7a6b52", lemma:"#675a9a", theorem:"#b07835", proposition:"#416ba0", corollary:"#ae5977"};
  const focused = papers.find(p=>p.id===focusId);
  const ids = new Set(shownPapers.map((p) => p.id));
  const positions = allowLayeredLayout
    ? dependencyPositions(
        Array.from(ids),
        (synthesis?.relations || []).filter(
          (r) => ids.has(r.source) && ids.has(r.target),
        ),
      )
    : null;
  useEffect(() => {
    if (!container.current) return;
    const chart = echarts.init(container.current, undefined, {renderer: "svg"});
    chartRef.current = chart;
    chart.on("click", (p: unknown) => {
      const event = p as {dataType?: string; data?: {id?: string; evidence?: string[]}};
      const data = event.data;
      if (event.dataType === "node" && data?.id) { focusHandler.current(data.id); return; }
      if (data?.evidence) evidenceHandler.current(data.evidence);
    });
    chart.on("graphroam", () => {
      const series = chart.getOption().series as { zoom?: number }[];
      setZoomPercent(Math.round((series[0]?.zoom || 1) * 100));
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);
  useEffect(() => {
    if (!expanded) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    expandButton.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [expanded]);
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const ids = new Set(shownPapers.map((p) => p.id));
    const relations = (synthesis?.relations || []).filter(
      (r) => ids.has(r.source) && ids.has(r.target),
    );
    chart.setOption({
      animation: false,
      tooltip: { trigger: "item", renderMode: "richText" },
      series: [
        {
          type: "graph",
          layout: layered && positions ? "none" : "force",
          ...(allowLayeredLayout ? { top: 44, bottom: 72, left: 72, right: 72, preserveAspect: true } : {}),
          roam: true,
          scaleLimit: { min: 0.3, max: 3 },
          draggable: true,
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: 9,
          force: { repulsion: 600, edgeLength: 180, gravity: 0.08 },
          label: {
            show: true,
            ...(allowLayeredLayout ? { width: 110, overflow: "break" } : {}),
            position: "bottom",
            color: "#263c51",
            fontSize: allowLayeredLayout && papers.length > 4 ? 12 : 14,
          },
          lineStyle: { color: "#829bb0", width: 2, curveness: 0.12 },
          emphasis: { focus: "adjacency" },
          data: shownPapers.map((p, i) => ({
            id: p.id,
            name: p.extraction.method_name,
            ...(layered && positions ? positions[p.id] : {}),
            symbolSize: allowLayeredLayout && papers.length > 4 ? 38 : Math.min(52 + i * 3, 68),
            itemStyle: {
              opacity: focusId ? (p.id===focusId || upstream.has(p.id) || downstream.has(p.id) ? 1 : 0.2) : (!highlightIds || highlightIds.includes(p.id) ? 1 : 0.25),
              borderColor: p.id===focusId ? "#172d45" : upstream.has(p.id) ? "#436de3" : downstream.has(p.id) ? "#df8a35" : "transparent",
              borderWidth: focusId && (p.id===focusId || upstream.has(p.id) || downstream.has(p.id)) ? 4 : 0,
              color: (nodeKinds && kindColors[nodeKinds[p.id]]) || ["#1b6870", "#3371ac", "#9a7544", "#675a9a", "#537c65"][
                i % 5
              ],
            },
            evidence: p.extraction.methods.flatMap((c) => c.evidence_ids),
          })),
          links: relations.map((r) => ({
            lineStyle: {
              opacity:
                !highlightIds ||
                (highlightIds.includes(r.source) &&
                  highlightIds.includes(r.target))
                  ? 1
                  : 0.15,
            },
            source: r.source,
            target: r.target,
            name: r.scope,
            evidence: r.evidence_ids,
            label: {
              show: !allowLayeredLayout || !layered,
              formatter:
                { inherits: "继承", improves: "改进", replaces: "替代" }[
                  r.type
                ] || (r.type === "depends" ? "证明依赖" : r.type),
              fontSize: 12,
            },
          })),
        },
      ],
    }, {replaceMerge: ["series"]});
  }, [papers, synthesis, highlightIds, layered, focusId, onlyTarget, targetId, nodeKinds]);
  function exportGraph(format: "svg" | "png") {
    const svg = container.current?.querySelector("svg"); if (!svg) return;
    const markup = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([markup], {type:"image/svg+xml;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const download = (href:string) => { setExportUrl({url:href,format}); const a=document.createElement("a"); a.href=href; a.download=`研脉-知识图谱.${format}`; a.click(); };
    if (format==="svg") { download(url); return; }
    const image = new Image(); image.onload=()=> { const canvas=document.createElement("canvas"); canvas.width=svg.clientWidth*2; canvas.height=svg.clientHeight*2; const ctx=canvas.getContext("2d")!; ctx.fillStyle="#fff";ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(image,0,0,canvas.width,canvas.height);canvas.toBlob(b=>{if(b){const u=URL.createObjectURL(b);download(u);}},"image/png");URL.revokeObjectURL(url); }; image.onerror=()=>URL.revokeObjectURL(url); image.src=url;
  }
  function zoom(factor: number) {
    const chart = chartRef.current;
    if (!chart) return;
    const series = chart.getOption().series as { zoom?: number }[];
    const next = Math.max(0.3, Math.min(3, (series[0]?.zoom || 1) * factor));
    chart.setOption({ series: [{ zoom: next }] });
    setZoomPercent(Math.round(next * 100));
  }
  return (
    <div
      ref={shell}
      className={`graph-shell${expanded ? " graph-shell-expanded" : ""}`}
      role={expanded ? "dialog" : undefined}
      aria-modal={expanded || undefined}
      aria-label={expanded ? "全屏图谱" : undefined}
      onKeyDown={(event) => {
        if (!expanded) return;
        if (event.key === "Escape") {
          event.preventDefault();
          event.stopPropagation();
          setExpanded(false);
        }
        if (event.key === "Tab") {
          const buttons = Array.from(
            shell.current?.querySelectorAll<HTMLButtonElement>(
              "button:not(:disabled)",
            ) || [],
          );
          if (event.shiftKey && document.activeElement === buttons[0]) {
            event.preventDefault();
            buttons.at(-1)?.focus();
          } else if (
            !event.shiftKey &&
            document.activeElement === buttons.at(-1)
          ) {
            event.preventDefault();
            buttons[0]?.focus();
          }
        }
      }}
    >
      <div className="graph-toolbar" role="group" aria-label="图谱查看工具">
        <span>
          {layered && positions
            ? "前提在上 · 结果在下 · 点击节点看详情"
            : "拖动节点 · 滚轮缩放 · 点击节点看详情"}
        </span>
        <select aria-label="查看图谱节点详情" value={focusId} onChange={e=>setFocusId(e.target.value)}><option value="">选择节点查看详情</option>{shownPapers.map(p=><option key={p.id} value={p.id}>{p.extraction.method_name}</option>)}</select>
        {allowLayeredLayout && (
          <button
            type="button"
            disabled={!positions}
            onClick={() => {
              setLayered(!layered);
              chartRef.current?.setOption({
                series: [{ zoom: 1, center: ["50%", "50%"] }],
              });
              setZoomPercent(100);
            }}
          >
            {layered && positions ? "力导向布局" : "分层布局"}
          </button>
        )}
        {allowLayeredLayout && <button disabled={!targetId} aria-pressed={onlyTarget} onClick={()=>setOnlyTarget(!onlyTarget)}>{onlyTarget ? "显示完整图谱" : "只看目标依赖"}</button>}
        <button onClick={()=>exportGraph("svg")}>导出 SVG</button>
        <button onClick={()=>exportGraph("png")}>导出 PNG</button>
        <output aria-label="图谱缩放比例" aria-live="polite">
          {zoomPercent}%
        </output>
        <button
          type="button"
          aria-label="放大图谱"
          title="放大"
          onClick={() => zoom(1.25)}
        >
          <ZoomIn size={17} />
        </button>
        <button
          type="button"
          aria-label="缩小图谱"
          title="缩小"
          onClick={() => zoom(0.8)}
        >
          <ZoomOut size={17} />
        </button>
        <button
          type="button"
          aria-label="复位图谱视角"
          title="复位视角"
          onClick={() => {
            chartRef.current?.setOption({
              series: [{ zoom: 1, center: ["50%", "50%"] }],
            });
            setZoomPercent(100);
          }}
        >
          <RotateCcw size={17} />
        </button>
        <button
          ref={expandButton}
          type="button"
          aria-label={expanded ? "退出全屏图谱" : "全屏查看图谱"}
          title={expanded ? "退出全屏" : "全屏查看"}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
        </button>
      </div>
      {exportUrl && <p role="status">图片已生成：<a href={exportUrl.url} download={`研脉-知识图谱.${exportUrl.format}`}>点击保存 {exportUrl.format.toUpperCase()} 图片</a></p>}
      {nodeKinds && <div className="graph-legend">{Object.entries(kindLabels).map(([k,label])=><span key={k}><i style={{background:kindColors[k]}}/>{label}</span>)}<span>蓝色描边：上游前提 · 橙色描边：下游结果</span></div>}
      {focused && <div className="graph-detail"><strong>{focused.extraction.method_name}</strong><p>{focused.extraction.methods[0]?.text}</p><p>上游 {upstream.size} 项 · 下游 {downstream.size} 项</p><button onClick={()=>evidenceHandler.current(focused.extraction.methods.flatMap(c=>c.evidence_ids))}>查看节点原文依据</button><button onClick={()=>setFocusId("")}>清除高亮</button></div>}
      <div
        ref={container}
        className="graph"
        role="img"
        aria-label={ariaLabel}
      />
    </div>
  );
}
