export type Status = "supported" | "partial" | "unsupported" | "unverified";
export type Evidence = {
  id: string;
  paper_id: string;
  text: string;
  page: number | null;
  section: string;
};
export type Claim = {
  id: string;
  text: string;
  evidence_ids: string[];
  kind: "author_statement" | "inference" | "human_note";
  status: Status;
  reason: string;
};
export type Field = "methods" | "advantages" | "limitations" | "future_work";
export type Paper = {
  id: string;
  filename: string;
  revision: number;
  warnings: string[];
  metadata: {
    title: string;
    authors: string[];
    year: number | null;
    venue: string | null;
    task: string;
    evidence_ids: string[];
  };
  extraction: {
    method_name: string;
    methods: Claim[];
    advantages: Claim[];
    limitations: Claim[];
    future_work: Claim[];
    evaluations: {
      dataset: string;
      metric: string;
      value: string | null;
      setting: string;
      evidence_ids: string[];
    }[];
  };
  classification: {
    task_ids: string[];
    method_ids: string[];
    rationale: string;
    evidence_ids: string[];
  };
  evidence: Evidence[];
};
export type Direction = {
  id: string;
  title: string;
  problem: string;
  hypothesis: string;
  reasoning: string;
  experiment: string;
  failure_condition: string;
  evidence_ids: string[];
  status: Status;
  reason: string;
};
export type Synthesis = {
  summary: Claim[];
  relations: {
    source: string;
    target: string;
    type: string;
    scope: string;
    evidence_ids: string[];
    status: Status;
  }[];
  directions: Direction[];
  common_gaps: {
    method: string;
    limitation: string;
    idea: string;
    evidence_ids: string[];
  }[];
};
export type Result = {
  mode: "demo" | "live";
  papers: Paper[];
  synthesis: Synthesis | null;
  failures: { filename: string; message: string }[];
};
export type Job = {
  id: string;
  status: string;
  stage: string;
  created: number;
  stale: number;
  result: Result | null;
  error: string | null;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cache_hits: number;
  generation: number;
};
export type Config = {
  configured: boolean;
  worker_online: boolean;
  max_files: number;
  max_file_mb: number;
  max_pages: number;
};
export type Tag = {
  id: string;
  label: string;
  definition: string;
  children?: Tag[];
};
