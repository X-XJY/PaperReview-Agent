from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Evidence(Strict):
    id: str
    paper_id: str
    text: str
    page: int | None = None
    section: str = ''

class Claim(Strict):
    id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    kind: Literal['author_statement', 'inference', 'human_note'] = 'author_statement'
    status: Literal['supported', 'partial', 'unsupported', 'unverified'] = 'unverified'
    reason: str = ''

class Metadata(Strict):
    title: str
    authors: list[str]
    year: int | None = Field(default=None, ge=1900, le=2100)
    venue: str | None = None
    task: str
    evidence_ids: list[str]

class Evaluation(Strict):
    dataset: str
    metric: str
    value: str | None = None
    setting: str
    evidence_ids: list[str]

class Extraction(Strict):
    method_name: str
    methods: list[Claim]
    advantages: list[Claim]
    limitations: list[Claim]
    future_work: list[Claim]
    evaluations: list[Evaluation]

class Classification(Strict):
    task_ids: list[str]
    method_ids: list[str]
    rationale: str
    evidence_ids: list[str]

class Paper(Strict):
    id: str
    filename: str
    metadata: Metadata
    extraction: Extraction
    classification: Classification
    evidence: list[Evidence]
    revision: int = 1
    warnings: list[str] = Field(default_factory=list)

class Relation(Strict):
    source: str
    target: str
    type: Literal['inherits', 'improves', 'replaces']
    scope: str
    evidence_ids: list[str]
    status: Literal['supported', 'partial', 'unsupported', 'unverified'] = 'unverified'

class Direction(Strict):
    id: str
    title: str
    problem: str
    hypothesis: str
    reasoning: str
    experiment: str
    failure_condition: str
    evidence_ids: list[str]
    status: Literal['supported', 'partial', 'unsupported', 'unverified'] = 'unverified'
    reason: str = ''

class CommonGap(Strict):
    method: str
    limitation: str
    idea: str
    evidence_ids: list[str]

class Synthesis(Strict):
    summary: list[Claim]
    relations: list[Relation]
    directions: list[Direction]
    common_gaps: list[CommonGap]

class CheckItem(Strict):
    id: str
    status: Literal['supported', 'partial', 'unsupported', 'unverified']
    reason: str

class Verification(Strict):
    checks: list[CheckItem]

class Edit(Strict):
    revision: int
    field: Literal['methods', 'advantages', 'limitations', 'future_work']
    claim_id: str
    text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str]
    kind: Literal['author_statement', 'human_note']
