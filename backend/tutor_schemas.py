from typing import Literal
from pydantic import Field
from .schemas import Strict

class TutorThreadInput(Strict):
    paper_ids: list[str] = Field(min_length=1, max_length=8)

class TutorRequest(Strict):
    request_id: str = Field(min_length=16, max_length=80)
    question: str = Field(min_length=1, max_length=3000)
    activity: Literal['ask','explain','compare','quiz'] = 'ask'
    mode: Literal['direct','guided'] = 'direct'
    depth: Literal['intuitive','technical'] = 'intuitive'
    paper_only: bool = False
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)

class TutorQuery(Strict):
    keywords: list[str] = Field(max_length=12)

class TutorBlock(Strict):
    kind: Literal['paper_fact','background','hypothesis']
    text: str = Field(min_length=1, max_length=2500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)

class TutorAnswer(Strict):
    blocks: list[TutorBlock] = Field(max_length=8)
    question: str = Field(default='', max_length=700)
    suggestions: list[str] = Field(default_factory=list, max_length=3)

class TutorCheck(Strict):
    index: int = Field(ge=0, le=7)
    status: Literal['supported','partial','unsupported','unverified']
    reason: str = Field(max_length=500)

class TutorChecks(Strict):
    checks: list[TutorCheck] = Field(max_length=8)
