import { useState } from "react";
import type { Paper } from "./types";
import type { TutorSeed } from "./Tutor";
import LearningPath from "./LearningPath";
import { methodStudyNodes } from "./studyNodes";
export default function MethodStudy({
  paper,
  jobId,
  onEvidence,
  onTutor,
}: {
  paper: Paper;
  jobId: string;
  onEvidence: (ids: string[]) => void;
  onTutor: (seed: TutorSeed) => void;
}) {
  const [goal, setGoal] = useState("methods");
  const nodes = methodStudyNodes(paper);
  const selected = nodes.filter((n) => goal === "all" || n.kind === goal);
  if (!nodes.length)
    return (
      <p className="muted">
        当前没有通过原文支持核验的方法学习内容，请查看论文详情中的抽取状态和依据。
      </p>
    );
  return (
    <section className="method-study" aria-label="方法学习路线">
      <h4>方法学习 · {paper.extraction.method_name || "理解论文方法"}</h4>
      <p>
        已保留 {nodes.length}{" "}
        项有原文支持的内容。以下是阅读路线，不是定理或证明依赖；顺序按论文抽取结果安排。
      </p>
      <label>
        方法学习目标{" "}
        <select value={goal} onChange={(e) => setGoal(e.target.value)}>
          <option value="methods">理解方法设计</option>
          <option value="advantages">理解优势与证据</option>
          <option value="limitations">理解作者局限</option>
          <option value="all">完整阅读路线</option>
        </select>
      </label>
      {selected.length ? (
        <>
          <LearningPath
            key={jobId + paper.id}
            paper={paper}
            jobId={jobId}
            studyNodes={nodes}
            path={selected.map((n) => n.id)}
            onEvidence={onEvidence}
          />
          <button
            className="method-study-tutor"
            onClick={() =>
              onTutor({
                paperIds: [paper.id],
                evidenceIds: [
                  ...new Set(selected.flatMap((n) => n.evidence_ids)),
                ],
                question:
                  "请依据这篇论文的原文，带我学习“" +
                  {
                    methods: "方法设计",
                    advantages: "优势与证据",
                    limitations: "作者局限",
                    all: "完整阅读路线",
                  }[goal] +
                  "”。逐步解释设计动机、核心机制、实验支持与适用限制，并提出一个理解检查问题；明确区分方法描述、实验观察和正式理论，不能虚构定理或证明。",
              })
            }
          >
            请助教带我学习这些内容
          </button>
        </>
      ) : (
        <p>这一类内容暂未通过原文支持核验，可切换其他学习目标。</p>
      )}
    </section>
  );
}
