import { useState, useEffect, useRef } from "react";
import type { Paper, Job } from "./types";
import EvidenceText from "./LazyEvidenceText";
import Graph from "./Graph";
import ProofWalkthrough from "./ProofWalkthrough";
import { BookOpen, ChevronDown } from "lucide-react";
import MethodStudy from "./MethodStudy";
import LearningPath from "./LearningPath";
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
  isDemo = false,
  onEvidence,
  jobId,
  editable,
  onUpdate,
  onTutor,
}: {
  papers: Paper[];
  isDemo?: boolean;
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
        先选一个想弄懂的结论，再按前置知识顺序学习。有正式理论结果时展示证明关系；没有时提供有原文依据的方法学习路线。
        <details className="theory-help">
          <summary>
            <BookOpen size={21} />
            <span>
              <strong>第一次使用？了解这些内容与学习目标</strong>
              <small>点击查看使用指南</small>
            </span>
            <ChevronDown size={20} className="theory-help-chevron" />
          </summary>
          <p>
            定义：约定术语或计算方式。假设：结论成立所需的条件。引理：证明大结论时使用的小结论。定理／命题：在指定条件下得到的结论。推论：从已有结论进一步得到的结果。
          </p>
          <p>
            证明依赖图中，每个点是一条理论陈述；箭头从“被使用的前提”指向“使用它的结论”。没有连线的点不自动代表没有关系，只表示当前未提取到有依据的依赖。
          </p>
          <p>
            切换学习目标会更新前置知识清单、高亮图谱中的相关节点，并按这条路径计算学习进度；不会修改论文结论或重新调用模型。已掌握的共同知识仍会保留。下方完整理论卡片仍保留供查阅。
          </p>
          <p>
            点击路径中的知识名称可查看依据并定位
            PDF；选择学习状态记录自己的掌握程度。“请助教带我学习这条路径”会打开带有当前目标与前置顺序的提问，提交后由助教讲解。
          </p>
        </details>
      </div>
      {isDemo && (
        <p className="theory-demo-note">
          教学演示：以下定义、引理、定理及证明为原创数学样例，用于体验证据溯源和学习路径，不是真实论文成果，也不证明对应方法的实际效果。
        </p>
      )}
      {papers.map((paper) => {
        const theory = paper.theory;
        const selected = theory?.nodes.find(
          (n) => paper.id + ":" + n.id === target,
        );
        const path = selected ? theory?.learning_paths[selected.id] : undefined;
        return (
          <section
            key={paper.id}
            className={`theory-paper${!theory?.nodes.length ? " theory-paper-empty" : ""}`}
          >
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
              <>
                <p>此分析尚未包含正式理论结果，以下可先学习已有的方法内容。</p>
                <MethodStudy
                  paper={paper}
                  jobId={jobId}
                  onEvidence={onEvidence}
                  onTutor={onTutor}
                />
              </>
            ) : !theory.nodes.length ? (
              <div className="theory-empty-content">
                <p>
                  {theory.status === "pending"
                    ? "当前没有保留的理论节点，重新推导后会更新结果。"
                    : isDemo
                      ? "这是旧版教学样例，尚未配置理论演示。点击页面顶部的“打开教学示例”可加载完整示例。"
                      : "本次未提取到正式理论结果，已转为展示有原文依据的方法学习内容。"}
                </p>
                {!isDemo && theory.status !== "pending" && (
                  <>
                    <MethodStudy
                      paper={paper}
                      jobId={jobId}
                      onEvidence={onEvidence}
                      onTutor={onTutor}
                    />
                    <p className="muted">
                      这不代表论文没有研究价值，也不能据此断定原文没有理论结果。实验型论文可能侧重方法与评测；如果原文确有明确理论陈述，可查看依据并手动补充。
                    </p>
                    <div className="theory-empty-actions">
                      <button
                        onClick={() =>
                          onEvidence(
                            paper.extraction.methods.flatMap(
                              (c) => c.evidence_ids,
                            ),
                          )
                        }
                        disabled={
                          !paper.extraction.methods.some(
                            (c) => c.evidence_ids.length,
                          )
                        }
                      >
                        查看方法原文
                      </button>
                      <button
                        onClick={() =>
                          onTutor({
                            paperIds: [paper.id],
                            evidenceIds: paper.extraction.methods.flatMap(
                              (c) => c.evidence_ids,
                            ),
                            question:
                              "请依据这篇论文的原文，讲解核心方法、适用条件与作者明确写出的局限。区分方法说明和正式理论结果，不要将方法描述包装成定理或虚构证明。",
                          })
                        }
                      >
                        请助教讲解方法
                      </button>
                    </div>
                  </>
                )}
              </div>
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
                  <p className="view-note">
                    当前目标：{selected!.label}。{selected!.statement}{" "}
                    这条路径共 {path.length} 项，包含目标及其前置知识。
                  </p>
                )}
                {isDemo && paper.id === "demo-atlas" && selected && (
                  <p className="theory-demo-note">
                    直观例子：有 3 条相关证据，最初检索到其中 2 条，召回率为
                    2/3；扩大检索集合后找齐 3 条，召回率为
                    1。这里说明的是“不删除已有证据时召回率不会下降”，并不保证答案更正确，也不保证无关证据更少。
                  </p>
                )}
                {path && (
                  <LearningPath
                    key={jobId + paper.id}
                    jobId={jobId}
                    paper={paper}
                    path={path}
                    onEvidence={onEvidence}
                  />
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
                {selected && theory.status !== "pending" && <ProofWalkthrough paper={paper} target={selected.id} onEvidence={onEvidence} onTutor={onTutor}/>}
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
                    targetId={selected?.id}
                    nodeKinds={Object.fromEntries(theory.nodes.map(n=>[n.id,n.kind]))}
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
