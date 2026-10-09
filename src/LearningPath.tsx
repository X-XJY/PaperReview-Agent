import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Paper } from "./types";
import type { StudyNode as Node } from "./studyNodes";
import StudyCoach from "./StudyCoach";
import EvidenceText from "./LazyEvidenceText";
type State = "not_started" | "review" | "mastered";
type Progress = {
  pending: boolean;
  nodes: Record<string, { status: State; fingerprint: string }>;
};
const labels: Record<State, string> = {
  not_started: "未开始",
  review: "需要复习",
  mastered: "已掌握",
};
export default function LearningPath({
  jobId,
  paper,
  path,
  onEvidence,
  studyNodes,
}: {
  jobId: string;
  paper: Paper;
  path: string[];
  studyNodes?: Node[];
  onEvidence: (ids: string[]) => void;
}) {
  const [progress, setProgress] = useState<Progress | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const availableNodes = studyNodes || paper.theory?.nodes || [];
  const signature = JSON.stringify(availableNodes);
  const storageKey = "paper-learning-v1:" + paper.id;
  const local = jobId === "local-demo";
  useEffect(() => {
    let active = true;
    generation.current++;
    setBusy(false);
    setProgress(null);
    setError("");
    if (local) {
      let stored: Progress["nodes"] = {};
      try {
        const parsed = JSON.parse(localStorage.getItem(storageKey) || "{}");
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed))
          stored = parsed;
      } catch {
        /* Storage is optional. */
      }
      const nodes = Object.fromEntries(
        availableNodes.map((n) => {
          const fingerprint = JSON.stringify(n);
          const old = stored[n.id];
          return [
            n.id,
            {
              fingerprint,
              status:
                old?.fingerprint === fingerprint && old.status in labels
                  ? old.status
                  : "not_started",
            },
          ];
        }),
      );
      setProgress({ pending: false, nodes });
    } else
      api<Progress>(`/jobs/${jobId}/papers/${paper.id}/learning`)
        .then((p) => {
          if (active) setProgress(p);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    return () => {
      active = false;
    };
  }, [jobId, paper.id, signature, local]);
  async function mark(node: Node, status: State) {
    if (!progress) return;
    const current = generation.current;
    setBusy(true);
    setError("");
    try {
      if (local) {
        const next = {
          ...progress,
          nodes: {
            ...progress.nodes,
            [node.id]: { ...progress.nodes[node.id], status },
          },
        };
        localStorage.setItem(storageKey, JSON.stringify(next.nodes));
        setProgress(next);
      } else {
        const saved = await api<Progress>(
          `/jobs/${jobId}/papers/${paper.id}/learning`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              node_id: node.id,
              status,
              fingerprint: progress.nodes[node.id]?.fingerprint,
            }),
          },
        );
        if (current === generation.current) setProgress(saved);
      }
    } catch (e) {
      if (current === generation.current)
        setError(e instanceof Error ? e.message : "无法保存进度");
    } finally {
      if (current === generation.current) setBusy(false);
    }
  }
  const nodes = path
    .map((id) => availableNodes.find((n) => n.id === id))
    .filter((n): n is Node => !!n);
  const mastered = nodes.filter(
    (n) => progress?.nodes[n.id]?.status === "mastered",
  ).length;
  const next = nodes.find((n) => progress?.nodes[n.id]?.status !== "mastered");
  return (
    <section className="learning-path" aria-label="交互式学习路径">
      <div className="learning-progress">
        <strong>当前目标的学习进度</strong>
        <span>
          {mastered} / {nodes.length} 已掌握
        </span>
        <progress
          value={mastered}
          max={Math.max(1, nodes.length)}
          aria-label="学习进度"
        />
      </div>
      {next && <p>建议下一步：{next.label}</p>}
      <ol className="learning-steps">
        {nodes.map((n) => (
          <li
            key={n.id}
            className={
              "learning-step " +
              (progress?.nodes[n.id]?.status || "not_started")
            }
          >
            <button onClick={() => onEvidence(n.evidence_ids)}>
              {n.label}{studyNodes&&" · 查看原文"}
            </button>
            {studyNodes && (
              <div className="method-step-text">
                <EvidenceText text={n.statement} />
              </div>
            )}
            <StudyCoach jobId={jobId} paper={paper} node={n} onEvidence={onEvidence} onReview={id=>{const review=availableNodes.find(x=>x.id===id);if(review)onEvidence(review.evidence_ids);}}/>
            <label>
              学习状态{" "}
              <select
                aria-label={n.label + " 学习状态"}
                value={progress?.nodes[n.id]?.status || "not_started"}
                disabled={!progress || busy || progress.pending}
                onChange={(e) => mark(n, e.target.value as State)}
              >
                {Object.entries(labels).map(([s, t]) => (
                  <option key={s} value={s}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          </li>
        ))}
      </ol>
      {!progress && !error && <p role="status">正在读取学习进度…</p>}
      {error && <p role="alert">{error}</p>}
      <small>
        掌握程度由你标记。切换学习目标会保留已学节点；内容更新后，旧标记不再视为当前进度。
      </small>
    </section>
  );
}
