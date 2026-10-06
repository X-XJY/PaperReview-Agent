import { useEffect, useRef, useState } from "react";
import { ZoomIn, ZoomOut, RotateCcw, Maximize2, Minimize2 } from "lucide-react";
import * as echarts from "echarts/core";
import { GraphChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Paper, Synthesis } from "./types";
import { dependencyPositions } from "./graphLayout";
echarts.use([GraphChart, TooltipComponent, CanvasRenderer]);
export default function Graph({
  papers,
  synthesis,
  onEvidence,
  ariaLabel = "方法演进力导向图；下方另有可访问的关系列表",
  highlightIds,
  allowLayeredLayout = false,
}: {
  papers: Paper[];
  synthesis: Synthesis | null;
  onEvidence: (ids: string[]) => void;
  ariaLabel?: string;
  highlightIds?: string[];
  allowLayeredLayout?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const evidenceHandler = useRef(onEvidence);
  evidenceHandler.current = (ids) => { setExpanded(false); onEvidence(ids); };
  const shell = useRef<HTMLDivElement>(null);
  const expandButton = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [zoomPercent, setZoomPercent] = useState(100);
  const [layered, setLayered] = useState(allowLayeredLayout);
  const ids = new Set(papers.map((p) => p.id));
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
    const chart = echarts.init(container.current);
    chartRef.current = chart;
    chart.on("click", (p: unknown) => {
      const data = (p as { data?: { evidence?: string[] } }).data;
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
    const ids = new Set(papers.map((p) => p.id));
    const relations = (synthesis?.relations || []).filter(
      (r) => ids.has(r.source) && ids.has(r.target),
    );
    chart.setOption({
      tooltip: { trigger: "item", renderMode: "richText" },
      series: [
        {
          type: "graph",
          layout: layered && positions ? "none" : "force",
          top: 48,
          bottom: 64,
          left: 40,
          right: 40,
          preserveAspect: true,
          roam: true,
          scaleLimit: { min: 0.3, max: 3 },
          draggable: true,
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: 9,
          force: { repulsion: 600, edgeLength: 180, gravity: 0.08 },
          label: {
            show: true,
            position: "bottom",
            color: "#263c51",
            fontSize: 14,
          },
          lineStyle: { color: "#829bb0", width: 2, curveness: 0.12 },
          emphasis: { focus: "adjacency" },
          data: papers.map((p, i) => ({
            id: p.id,
            name: p.extraction.method_name,
            ...(layered && positions ? positions[p.id] : {}),
            symbolSize: Math.min(52 + i * 3, 68),
            itemStyle: {
              opacity: !highlightIds || highlightIds.includes(p.id) ? 1 : 0.25,
              color: ["#1b6870", "#3371ac", "#9a7544", "#675a9a", "#537c65"][
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
    });
  }, [papers, synthesis, highlightIds, layered]);
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
            ? "前提在上 · 结果在下 · 点击查看依据"
            : "拖动节点 · 滚轮缩放 · 点击查看依据"}
        </span>
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
      <div
        ref={container}
        className="graph"
        role="img"
        aria-label={ariaLabel}
      />
    </div>
  );
}
