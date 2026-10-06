import { useState, useEffect, useRef } from "react";
import type { Paper, Job } from "./types";
import EvidenceText from "./LazyEvidenceText";
import Graph from "./Graph";
import { api } from "./api";
import type { TutorSeed } from "./Tutor";

const kinds: Record<string, string> = {
  definition: "定义",
  assumption: "假设",
  lemma: "引理",
  theorem: "定理",
  proposition: "命题",
  corollary: "推论",
};

type Node = NonNullable<Paper["theory"]>["nodes"][number];
export default function Theory({
  papers,
  onEvidence,
  jobId,
  editable,
  onUpdate,
  onTutor,
}: {
  papers: Paper[];
  onEvidence: (ids: string[]) => void;
  jobId: string;
  editable: boolean;
  onUpdate: (job: Job) => void;
  onTutor: (seed: TutorSeed) => void;
}) {
  const [target, setTarget] = useState("");
  const [edit, setEdit] = useState<{
    paper: Paper;
    node: Node;
    isNew?: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [sourceQuery, setSourceQuery] = useState("");
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!edit) return;
    setSourceQuery("");
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.querySelector<HTMLElement>("select")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [edit?.paper.id, edit?.node.id]);
  async function save(nodes: Node[], paper: Paper) {
    setSaving(true);
    setError("");
    try {
      onUpdate(
        await api<Job>(`/jobs/${jobId}/papers/${paper.id}/theory`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ revision: paper.revision, nodes }),
        }),
      );
      setEdit(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }
  return (
    <div className="theory-view">
      <div className="view-note">
        从原文理论陈述构建证明依赖，箭头表示“前提 →
        使用该前提的结果”。选择学习目标可查看前置知识顺序。
      </div>
      {papers.map((paper) => {
        const theory = paper.theory;
        const selected = theory?.nodes.find(
          (n) => paper.id + ":" + n.id === target,
        );
        const path = selected ? theory?.learning_paths[selected.id] : undefined;
        return (
          <section key={paper.id} className="theory-paper">
            <h3>{paper.metadata.title}</h3>
            {theory?.status === "pending" && (
              <p role="status">
                人工修改已保存。请点击页面的重新推导，核验后将重建证明依赖和学习路径。
              </p>
            )}
            {theory?.warnings.map((w) => (
              <p key={w} role="status">
                {w}
              </p>
            ))}
            {editable && (
              <button
                disabled={saving}
                onClick={() => {
                  setError("");
                  setEdit({
                    paper,
                    isNew: true,
                    node: {
                      id: "manual-" + crypto.randomUUID(),
                      kind: "theorem",
                      label: "",
                      statement: "",
                      conditions: [],
                      evidence_ids: [],
                    },
                  });
                }}
              >
                补充理论结果
              </button>
            )}
            {!theory ? (
              <p>此分析尚未包含理论结果，可点击重新推导补充分析。</p>
            ) : !theory.nodes.length ? (
              <p>
                {theory.status === "pending"
                  ? "当前没有保留的理论节点。"
                  : "未发现有原文支持的明确理论陈述。"}
              </p>
            ) : (
              <>
                <label>
                  学习目标{" "}
                  <select
                    disabled={theory.status === "pending"}
                    value={selected ? selected.id : ""}
                    onChange={(e) => setTarget(paper.id + ":" + e.target.value)}
                  >
                    <option value="">请选择定理或概念</option>
                    {theory.nodes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.label}
                      </option>
                    ))}
                  </select>
                </label>
                {path && (
                  <ol className="theory-path">
                    {path.map((id) => {
                      const node = theory.nodes.find((n) => n.id === id)!;
                      return (
                        <li key={id}>
                          <button onClick={() => onEvidence(node.evidence_ids)}>
                            {node.label}
                          </button>
                        </li>
                      );
                    })}
                  </ol>
                )}
                {path && (
                  <button
                    onClick={() =>
                      onTutor({
                        paperIds: [paper.id],
                        evidenceIds: [
                          ...new Set([
                            ...path.flatMap(
                              (id) =>
                                theory.nodes.find((n) => n.id === id)!
                                  .evidence_ids,
                            ),
                            ...theory.edges
                              .filter(
                                (e) =>
                                  path.includes(e.source) &&
                                  path.includes(e.target),
                              )
                              .flatMap((e) => e.evidence_ids),
                          ]),
                        ],
                        question: `我的学习目标是“${selected!.label}”。请按以下前置知识顺序讲解：${path.map((id) => theory.nodes.find((n) => n.id === id)!.label).join(" → ")}。逐步解释适用前提、证明中如何使用前置结果，并在最后给一道检查理解的问题。若原文不足请明确说明。`,
                      })
                    }
                  >
                    请助教带我学习这条路径
                  </button>
                )}
                <div className="theory-nodes">
                  {theory.nodes.map((n) => (
                    <article key={n.id}>
                      <small>{kinds[n.kind]}</small>
                      <h4>{n.label}</h4>
                      <EvidenceText text={n.statement} />
                      {n.conditions.length > 0 && (
                        <>
                          <strong>适用前提</strong>
                          {n.conditions.map((c, i) => (
                            <EvidenceText key={i} text={c} />
                          ))}
                        </>
                      )}
                      <button
                        className="evidence-link"
                        onClick={() => onEvidence(n.evidence_ids)}
                      >
                        查看原文依据
                      </button>
                      {editable && (
                        <button
                          disabled={saving}
                          onClick={() => {
                            setError("");
                            setEdit({
                              paper,
                              node: {
                                ...n,
                                conditions: [...n.conditions],
                                evidence_ids: [...n.evidence_ids],
                              },
                            });
                          }}
                        >
                          修正
                        </button>
                      )}
                    </article>
                  ))}
                </div>
                <h4>证明依赖</h4>
                {theory.status !== "pending" && (
                  <Graph
                    allowLayeredLayout
                    highlightIds={path}
                    ariaLabel="理论证明依赖图；箭头由前提指向结果"
                    papers={theory.nodes.map((n) => ({
                      ...paper,
                      id: n.id,
                      extraction: {
                        ...paper.extraction,
                        method_name: n.label,
                        methods: [
                          {
                            id: n.id,
                            text: n.statement,
                            evidence_ids: n.evidence_ids,
                            kind: "author_statement",
                            status: "supported",
                            reason: "",
                          },
                        ],
                      },
                    }))}
                    synthesis={{
                      summary: [],
                      directions: [],
                      common_gaps: [],
                      relations: theory.edges.map((e) => ({
                        ...e,
                        type: "depends",
                        scope: e.explanation,
                        status: "supported",
                      })),
                    }}
                    onEvidence={onEvidence}
                  />
                )}
                {!theory.edges.length && <p>未发现明确的节点间证明依赖。</p>}
                <div className="relation-list">
                  {theory.edges.map((e) => (
                    <button
                      key={e.source + e.target}
                      onClick={() => onEvidence(e.evidence_ids)}
                    >
                      <span>
                        {theory.nodes.find((n) => n.id === e.source)?.label} →{" "}
                        {theory.nodes.find((n) => n.id === e.target)?.label}
                        <small>{e.explanation}</small>
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </section>
        );
      })}
      {edit && (
        <section
          ref={dialog}
          className="theory-editor"
          role="dialog"
          aria-modal="true"
          aria-label="修正理论结果"
          onKeyDown={(e) => {
            if (e.key === "Escape" && !saving) {
              setEdit(null);
              return;
            }
            if (e.key !== "Tab") return;
            const controls = Array.from(
              e.currentTarget.querySelectorAll<HTMLElement>(
                "button:not(:disabled), input, textarea, select",
              ),
            );
            const first = controls[0],
              last = controls[controls.length - 1];
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }}
        >
          <h3>{edit.isNew ? "补充" : "修正"}理论结果</h3>
          <label>
            类型
            <select
              value={edit.node.kind}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  node: { ...edit.node, kind: e.target.value },
                })
              }
            >
              {Object.entries(kinds).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            名称与编号
            <input
              value={edit.node.label}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  node: { ...edit.node, label: e.target.value },
                })
              }
            />
          </label>
          <label>
            完整陈述
            <textarea
              rows={5}
              value={edit.node.statement}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  node: { ...edit.node, statement: e.target.value },
                })
              }
            />
          </label>
          <label>
            适用前提（每行一条）
            <textarea
              rows={3}
              value={edit.node.conditions.join("\n")}
              onChange={(e) =>
                setEdit({
                  ...edit,
                  node: {
                    ...edit.node,
                    conditions: e.target.value.split("\n"),
                  },
                })
              }
            />
          </label>
          <fieldset>
            <legend>
              选择原文依据 · 已选 {edit.node.evidence_ids.length} 条
            </legend>
            <input
              aria-label="搜索理论原文依据"
              placeholder="按页码、章节或原文关键词搜索"
              value={sourceQuery}
              onChange={(e) => setSourceQuery(e.target.value)}
            />
            <div className="theory-source-picker">
              {edit.paper.evidence
                .filter(
                  (e) =>
                    (e.text + " " + e.section + " " + e.page)
                      .toLowerCase()
                      .includes(sourceQuery.toLowerCase()) ||
                    edit.node.evidence_ids.includes(e.id),
                )
                .map((e) => (
                  <label key={e.id}>
                    <input
                      type="checkbox"
                      checked={edit.node.evidence_ids.includes(e.id)}
                      onChange={(event) =>
                        setEdit({
                          ...edit,
                          node: {
                            ...edit.node,
                            evidence_ids: event.target.checked
                              ? [...edit.node.evidence_ids, e.id]
                              : edit.node.evidence_ids.filter(
                                  (id) => id !== e.id,
                                ),
                          },
                        })
                      }
                    />
                    <span>
                      第 {e.page ?? "未知"} 页 · {e.section}
                      <EvidenceText text={e.text} />
                    </span>
                  </label>
                ))}
            </div>
          </fieldset>
          {error && <p role="alert">{error}</p>}
          <div className="theory-editor-actions">
            <button
              disabled={
                saving ||
                !edit.node.label.trim() ||
                !edit.node.statement.trim() ||
                !edit.node.evidence_ids.length
              }
              onClick={() =>
                save(
                  [
                    ...(edit.paper.theory?.nodes || []).filter(
                      (n) => n.id !== edit.node.id,
                    ),
                    {
                      ...edit.node,
                      conditions: edit.node.conditions.filter((c) => c.trim()),
                    },
                  ],
                  edit.paper,
                )
              }
            >
              {saving ? "正在保存…" : "保存并等待核验"}
            </button>
            {!edit.isNew && (
              <button
                disabled={saving}
                onClick={() =>
                  save(
                    (edit.paper.theory?.nodes || []).filter(
                      (n) => n.id !== edit.node.id,
                    ),
                    edit.paper,
                  )
                }
              >
                删除该结果
              </button>
            )}
            <button disabled={saving} onClick={() => setEdit(null)}>
              取消
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
