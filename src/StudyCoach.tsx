import { useEffect, useState } from "react";
import { api } from "./api";
import type { Paper } from "./types";
import type { StudyNode } from "./studyNodes";
import EvidenceText from "./LazyEvidenceText";
import { readMemory, writeMemory } from "./readingMemory";
type Citation = { evidence_id: string; quote: string };
type Question = {
  id: string;
  question: string;
  options: string[];
  citations: Citation[];
};
type Formula = {
  id: string;
  formula: string;
  explanation: string;
  conditions: string[];
  symbols: {
    symbol: string;
    meaning: string;
    origin: "source" | "general";
    citations: Citation[];
  }[];
  citations: Citation[];
};
type Task = {
  status: string;
  fingerprint: string;
  error: string | null;
  result: { questions: Question[]; formulas: Formula[]; notice: string } | null;
};
type Feedback = {
  results: {
    id: string;
    correct: boolean;
    answer: number;
    explanation: string;
    review_nodes: string[];
    citations: Citation[];
  }[];
  score: number;
  total: number;
};
type RecordEntry = {
  fingerprint: string;
  feedback: Feedback;
  answers: Record<string, number>;
  due: number;
  streak: number;
};
export default function StudyCoach({
  jobId,
  paper,
  node,
  onEvidence,
  onReview,
}: {
  jobId: string;
  paper: Paper;
  node: StudyNode;
  onEvidence: (ids: string[]) => void;
  onReview?: (id: string) => void;
}) {
  const [open, setOpen] = useState(false),
    [tab, setTab] = useState<"quiz" | "formula">("quiz");
  const [task, setTask] = useState<Task | null>(null),
    [answers, setAnswers] = useState<Record<string, number>>({}),
    [feedback, setFeedback] = useState<Feedback | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const base = `/jobs/${jobId}/papers/${paper.id}/study/${encodeURIComponent(node.id)}`;
  const storage = "paper-review:quiz:" + jobId + ":" + paper.id + ":" + node.id;
  const signature = JSON.stringify(node);
  const [record, setRecord] = useState<RecordEntry | null>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setTask(null);
    setAnswers({});
    setFeedback(null);
    setRecord(null);
    setError("");
    async function poll() {
      try {
        const result = await api<Task>(base);
        if (!active) return;
        setTask(result);
        const saved = readMemory<RecordEntry | null>(storage, null);
        if (saved?.fingerprint === result.fingerprint) {
          setRecord(saved);
          setFeedback(saved.feedback);
          setAnswers(saved.answers);
        }
        if (["queued", "running"].includes(result.status))
          timer = setTimeout(poll, 2000);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "读取失败");
      }
    }
    if (open && jobId !== "local-demo") void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [open, base, signature]);
  async function start() {
    setBusy(true);
    setError("");
    try {
      const t = await api<Task>(base, { method: "POST" });
      setTask(t);
      if (["queued", "running"].includes(t.status)) {
        setOpen(false);
        setTimeout(() => setOpen(true), 0);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "生成失败");
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    if (!task) return;
    setBusy(true);
    setError("");
    try {
      const f = await api<Feedback>(base + "/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fingerprint: task.fingerprint, answers }),
      });
      setFeedback(f);
      const passed = f.score === f.total;
      const streak = passed ? (record?.streak || 0) + 1 : 0;
      const days = passed ? [1, 3, 7, 14][Math.min(streak - 1, 3)] : 0;
      const next = {
        fingerprint: task.fingerprint,
        feedback: f,
        answers,
        due: Date.now() + (days ? days * 86400000 : 600000),
        streak,
      };
      setRecord(next);
      writeMemory(storage, next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "检查失败");
    } finally {
      setBusy(false);
    }
  }
  const nodes = [...(paper.theory?.nodes || []), node];
  const review = [
    ...new Set(feedback?.results.flatMap((r) => r.review_nodes) || []),
  ];
  function evidence(refs: Citation[]) {
    return (
      <button
        onClick={() => onEvidence([...new Set(refs.map((c) => c.evidence_id))])}
      >
        查看原文依据
      </button>
    );
  }
  return (
    <div className="study-coach">
      <div className="study-coach-actions">
        <button
          onClick={() => {
            setOpen(true);
            setTab("quiz");
          }}
        >
          理解检查与复习
        </button>
        <button
          onClick={() => {
            setOpen(true);
            setTab("formula");
          }}
        >
          公式与符号解释
        </button>
        {open && <button onClick={() => setOpen(false)}>收起学习工具</button>}
      </div>
      {open && (
        <section
          className="study-coach-panel"
          aria-label={node.label + " 学习工具"}
        >
          <h4>
            {node.label} · {tab === "quiz" ? "理解检查" : "公式与符号"}
          </h4>
          <p className="muted">
            {tab === "quiz"
              ? "完成原文支持的理解题，查看解释与个性化复习建议。"
              : "解释当前节点及前置知识的公式，区分作者原文定义与通用数学解释。"}
          </p>
          {jobId === "local-demo" ? (
            <p>连接后端后可生成有原文依据的学习材料。</p>
          ) : (
            !task?.result && (
              <button
                disabled={
                  busy || ["queued", "running"].includes(task?.status || "")
                }
                onClick={start}
              >
                {busy
                  ? "提交中…"
                  : task?.status === "queued"
                    ? "已排队，等待生成"
                    : task?.status === "running"
                      ? "正在生成并核验…"
                      : "生成学习材料"}
              </button>
            )
          )}
          {(error || task?.error) && <p role="alert">{error || task?.error}</p>}
          {task?.result && (
            <>
              {tab === "quiz" ? (
                <>
                  {task.result.questions.length ? (
                    task.result.questions.map((q, i) => (
                      <fieldset key={q.id} className="study-question">
                        <legend>
                          {i + 1}. {q.question}
                        </legend>
                        {q.options.map((option, j) => (
                          <label key={j}>
                            <input
                              type="radio"
                              name={paper.id + node.id + q.id}
                              checked={answers[q.id] === j}
                              disabled={busy || !!feedback}
                              onChange={() =>
                                setAnswers({ ...answers, [q.id]: j })
                              }
                            />
                            <span>{option}</span>
                          </label>
                        ))}
                        {evidence(q.citations)}
                        {feedback && (
                          <div
                            className={
                              feedback.results.find((r) => r.id === q.id)
                                ?.correct
                                ? "quiz-correct"
                                : "quiz-review"
                            }
                          >
                            {feedback.results
                              .filter((r) => r.id === q.id)
                              .map((r) => (
                                <div key={r.id}>
                                  <strong>
                                    {r.correct ? "回答正确" : "建议复习"} ·
                                    正确选项：{q.options[r.answer]}
                                  </strong>
                                  <EvidenceText text={r.explanation} />
                                </div>
                              ))}
                          </div>
                        )}
                      </fieldset>
                    ))
                  ) : (
                    <p>
                      当前未生成通过自动检查的题目。可先阅读原文与学习路径。
                    </p>
                  )}
                  {!feedback && task.result.questions.length > 0 && (
                    <button
                      disabled={
                        busy ||
                        task.result.questions.some(
                          (q) => answers[q.id] === undefined,
                        )
                      }
                      onClick={submit}
                    >
                      {busy ? "检查中…" : "提交答案，查看复习建议"}
                    </button>
                  )}
                  {feedback && (
                    <div className="quiz-feedback" role="status">
                      <strong>
                        本次理解检查：{feedback.score} / {feedback.total}
                      </strong>
                      {review.length > 0 ? (
                        <>
                          <p>建议先复习以下知识，再重新答题：</p>
                          {review.map((id) => (
                            <button
                              key={id}
                              onClick={() => {
                                if (onReview) onReview(id);
                                else onEvidence(node.evidence_ids);
                              }}
                            >
                              {nodes.find((n) => n.id === id)?.label ||
                                "当前节点"}
                            </button>
                          ))}
                        </>
                      ) : (
                        <p>已通过本次检查，建议按计划再次回顾。</p>
                      )}
                      {record && (
                        <p>
                          下次复习：
                          {record.due <= Date.now()
                            ? "现在可以复习"
                            : new Date(record.due).toLocaleString("zh-CN", {
                                month: "numeric",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                          。通过后逐步延长复习间隔。
                        </p>
                      )}
                      <button
                        onClick={() => {
                          setFeedback(null);
                          setAnswers({});
                        }}
                      >
                        重新答题
                      </button>
                      <small>
                        答题记录保存在当前浏览器；不会自动替你标记已掌握。
                      </small>
                    </div>
                  )}
                </>
              ) : (
                <>
                  {task.result.formulas.length ? (
                    task.result.formulas.map((f) => (
                      <article className="formula-guide" key={f.id}>
                        <EvidenceText text={f.formula.includes("$") || f.formula.startsWith("\\[") ? f.formula : `$$${f.formula}$$`} />
                        <EvidenceText text={f.explanation} />
                        {evidence(f.citations)}
                        <h5>符号含义 · 本论文</h5>
                        {f.symbols.length ? (
                          <dl>
                            {f.symbols.map((s, i) => (
                              <div key={i}>
                                <dt>
                                  <EvidenceText text={s.symbol.includes("$") ? s.symbol : `$${s.symbol}$`} />
                                </dt>
                                <dd>
                                  <small>
                                    {s.origin === "source"
                                      ? "原文定义"
                                      : "通用数学解释 · 知识补充"}
                                  </small>
                                  <EvidenceText text={s.meaning} />
                                  {s.citations.length > 0 &&
                                    evidence(s.citations)}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        ) : (
                          <p>当前材料未提供可确定的符号解释。</p>
                        )}
                        <h5>适用条件</h5>
                        {f.conditions.length ? (
                          f.conditions.map((c, i) => (
                            <EvidenceText key={i} text={c} />
                          ))
                        ) : (
                          <p>当前依据未明确给出额外适用条件。</p>
                        )}
                        <details>
                          <summary>展开公式原文上下文</summary>
                          {f.citations.map((c, i) => (
                            <EvidenceText key={i} text={c.quote} />
                          ))}
                        </details>
                      </article>
                    ))
                  ) : (
                    <p>
                      当前节点的原文依据中没有可解释的公式。可切换到包含公式的定义或定理。
                    </p>
                  )}
                </>
              )}
              <small>
                材料已保存并通过引用匹配与自动语义检查。
              </small>
            </>
          )}
        </section>
      )}
    </div>
  );
}
