import type { Job, Result } from "./types";
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api" + path, {
    ...init,
    headers: { "X-Requested-With": "PaperMethodAgent", ...init?.headers },
  });
  if (!response.headers.get("content-type")?.includes("json"))
    throw new Error("后端服务未连接。可以浏览示例；真实分析需要启动后端。");
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "请求未通过校验，请检查输入。",
    );
  return body;
}
export async function localDemo(): Promise<Job> {
  const response = await fetch("/demo.json");
  if (!response.ok) throw new Error("无法加载教学示例。");
  const result: Result = await response.json();
  return {
    id: "local-demo",
    status: "completed",
    stage: "示例分析",
    created: Date.now() / 1000,
    stale: 0,
    result,
    error: null,
    calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    cache_hits: 0,
    generation: 1,
  };
}
export function download(name: string, text: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/markdown;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const cell = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");
export function matrixMarkdown(result: Result) {
  return [
    "# 多论文方法对比",
    result.mode === "demo" ? "\n> 原创教学样例，非真实论文分析。" : "",
    "\n| 论文 | 核心方法 | 优势 | 作者局限 | 数据集 |",
    "|---|---|---|---|---|",
    ...result.papers.map(
      (p) =>
        "| " +
        [
          p.metadata.title,
          ...(["methods", "advantages", "limitations"] as const).map(
            (f) =>
              p.extraction[f]
                .map(
                  (c) =>
                    `${c.text} [${c.status}] ${c.evidence_ids.map((id) => `[${id}]`).join(" ")}`,
                )
                .join("；") || "未找到明确陈述",
          ),
          p.extraction.evaluations.map((e) => e.dataset).join("；") ||
            "未抽取到",
        ]
          .map(cell)
          .join(" | ") +
        " |",
    ),
  ].join("\n");
}
export function localReport(job: Job) {
  const result = job.result!;
  const s = result.synthesis;
  return [
    matrixMarkdown(result),
    job.stale ? "\n> 人工修正后，聚合结果已过期。" : "",
    "\n## 论文详情",
    ...result.papers.flatMap((p) => [
      "\n### " + p.metadata.title,
      `作者：${p.metadata.authors.join("、")}；年份：${p.metadata.year ?? "未知"}；会议：${p.metadata.venue ?? "未知"}`,
      `任务：${p.metadata.task}；方法标签：${p.classification.method_ids.join("、")}`,
      ...p.extraction.future_work.map(
        (c) => "未来工作：" + c.text + " " + c.evidence_ids.join("、"),
      ),
      ...p.warnings.map((w) => "告警：" + w),
    ]),
    "\n## 演进总结",
    ...(s?.summary.map((c) => c.text + " " + c.evidence_ids.join("、")) || []),
    "\n## 方法关系",
    ...(s?.relations.map(
      (r) =>
        `${r.source} → ${r.target}：${r.type}；${r.scope}；${r.evidence_ids.join("、")}`,
    ) || []),
    "\n## 方法—共性缺陷—改进思路",
    ...(s?.common_gaps.map(
      (g) =>
        `${g.method}：${g.limitation}；${g.idea}；${g.evidence_ids.join("、")}`,
    ) || []),
    "\n## 待验证研究方向",
    ...(s?.directions.flatMap((d) => [
      "\n### " + d.title,
      `依据状态：${d.status}；${d.reason}`,
      d.problem,
      "假设：" + d.hypothesis,
      "推导：" + d.reasoning,
      "实验：" + d.experiment,
      "失败条件：" + d.failure_condition,
      d.evidence_ids.join("、"),
    ]) || []),
    "\n## 原文证据",
    ...result.papers.flatMap((p) =>
      p.evidence.map(
        (e) =>
          `\n### [${e.id}] · ${p.metadata.title} · 第 ${e.page ?? "未知"} 页\n> ${e.text.replace(/\n/g, "\n> ")}`,
      ),
    ),
  ].join("\n");
}
