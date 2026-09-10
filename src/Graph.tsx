import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { GraphChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Paper, Synthesis } from "./types";
echarts.use([GraphChart, TooltipComponent, CanvasRenderer]);
export default function Graph({
  papers,
  synthesis,
  onEvidence,
}: {
  papers: Paper[];
  synthesis: Synthesis | null;
  onEvidence: (ids: string[]) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const chart = echarts.init(container.current);
    const ids = new Set(papers.map((p) => p.id));
    const relations = (synthesis?.relations || []).filter(
      (r) => ids.has(r.source) && ids.has(r.target),
    );
    chart.setOption({
      tooltip: { trigger: "item", renderMode: "richText" },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: true,
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
            symbolSize: 52 + i * 3,
            itemStyle: {
              color: ["#1b6870", "#3371ac", "#9a7544", "#675a9a", "#537c65"][
                i % 5
              ],
            },
            evidence: p.extraction.methods.flatMap((c) => c.evidence_ids),
          })),
          links: relations.map((r) => ({
            source: r.source,
            target: r.target,
            name: r.scope,
            evidence: r.evidence_ids,
            label: {
              show: true,
              formatter:
                { inherits: "继承", improves: "改进", replaces: "替代" }[
                  r.type
                ] || r.type,
              fontSize: 12,
            },
          })),
        },
      ],
    });
    chart.on("click", (p: unknown) => {
      const data = (p as { data?: { evidence?: string[] } }).data;
      if (data?.evidence) onEvidence(data.evidence);
    });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [papers, synthesis, onEvidence]);
  return (
    <div
      ref={container}
      className="graph"
      role="img"
      aria-label="方法演进力导向图；下方另有可访问的关系列表"
    />
  );
}
