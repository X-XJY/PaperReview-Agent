import type { Paper } from "./types";
export type StudyNode = {
  id: string;
  kind: string;
  label: string;
  statement: string;
  conditions: string[];
  evidence_ids: string[];
};
export function methodStudyNodes(paper: Paper): StudyNode[] {
  const evidence = new Set(
    paper.evidence.filter((e) => e.paper_id === paper.id).map((e) => e.id),
  );
  const nodes: StudyNode[] = [];
  for (const [key, label] of [
    ["methods", "方法设计"],
    ["advantages", "优势与证据"],
    ["limitations", "作者局限"],
  ] as const) {
    const seen = new Set<string>();
    for (const claim of paper.extraction[key]) {
      const text = claim.text.trim(),
        marker = text.replace(/\s/g, "");
      if (
        claim.status !== "supported" ||
        claim.kind !== "author_statement" ||
        !text ||
        !claim.evidence_ids.length ||
        !claim.evidence_ids.every((id) => evidence.has(id)) ||
        seen.has(marker)
      )
        continue;
      seen.add(marker);
      nodes.push({
        id: "method-study:" + key + ":" + claim.id,
        kind: key,
        label: label + " " + seen.size,
        statement: text,
        conditions: [],
        evidence_ids: claim.evidence_ids,
      });
    }
  }
  return nodes;
}
