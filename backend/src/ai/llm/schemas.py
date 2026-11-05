from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Investigation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    summary: str = Field(min_length=1, max_length=6000)
    observations: list[str] = Field(max_length=40)
    supporting_evidence: list[str] = Field(max_length=40)
    possible_threats: list[str] = Field(max_length=40)
    benign_explanations: list[str] = Field(max_length=40)
    recommended_actions: list[str] = Field(max_length=40)
    confidence: Literal['low', 'medium', 'high']
    limitations: list[str] = Field(max_length=40)


class Generation(BaseModel):
    report: Investigation
    model_identifier: str
    model_version: str
    adapter_identifier: str | None = None
    fine_tuned: bool
    generated_at: str
    duration_seconds: float
    evidence: dict | None = None


class MuseReport(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    verdict: Literal['supported', 'partially_supported', 'unsupported', 'inconclusive']
    summary: str = Field(min_length=1, max_length=6000)
    verified_observations: list[str] = Field(max_length=40)
    unsupported_claims: list[str] = Field(max_length=40)
    benign_explanations: list[str] = Field(max_length=40)
    recommended_actions: list[str] = Field(max_length=40)
    confidence: Literal['low', 'medium', 'high']


class MuseGeneration(BaseModel):
    report: MuseReport
    model_identifier: str
    generated_at: str
    duration_seconds: float
    evidence: dict
    llama_report_hash: str
    tool_calls: list[dict]


def parse_response(raw):
    # Never repair invalid answers by inventing missing fields or content.
    text = raw.strip()
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    elif text.startswith('```') and text.endswith('```'):
        text = text[3:-3].strip()
    return Investigation.model_validate_json(text)
