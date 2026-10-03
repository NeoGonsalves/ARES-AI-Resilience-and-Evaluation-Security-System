from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ArenaTestConfiguration(ApiModel):
    test_name: str = Field(min_length=3, max_length=80)
    target_application: str = Field(min_length=2, max_length=80)
    system_prompt: str = Field(min_length=20, max_length=6000)
    user_prompt: str = Field(min_length=5, max_length=4000)
    provider: Literal["OpenAI", "Groq", "Gemini", "NvidiaNim"]
    model: str = Field(min_length=1, max_length=160)
    attack_source: Literal["Manual", "Corpus", "Generated"]
    attack_categories: list[str] = Field(min_length=1, max_length=8)
    temperature: float = Field(ge=0, le=2)
    max_response_tokens: int = Field(ge=64, le=4096)
    variation_count: int = Field(ge=1, le=10)
    include_hardened_comparison: bool

    @field_validator("attack_categories")
    @classmethod
    def known_categories(cls, value: list[str]) -> list[str]:
        known = {
            "DirectPromptInjection",
            "IndirectPromptInjection",
            "SystemPromptExtraction",
            "DataExfiltration",
            "PolicyBypass",
            "RoleManipulation",
            "ToolMisuse",
            "EncodingOrObfuscation",
        }
        unknown = set(value) - known
        if unknown:
            raise ValueError(f"Unknown attack categories: {', '.join(sorted(unknown))}")
        return value


class CreateTestRequest(ApiModel):
    configuration: ArenaTestConfiguration
    project_id: str | None = Field(
        default=None, description="Optional project; defaults to the caller's first project."
    )


class CreateTestResponse(ApiModel):
    test_id: str
    project_id: str
    status: str
    correlation_id: str
    created_at: datetime


class TestRunResponse(ApiModel):
    id: str
    project_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    duration_milliseconds: int
    token_estimate: int
    correlation_id: str
    failure_reason: str | None
    configuration: dict
    findings: list[dict]
    evidence: list[dict]


class CancelTestResponse(ApiModel):
    test_id: str
    status: str
    correlation_id: str


class ProjectCreate(ApiModel):
    name: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class ProjectResponse(ApiModel):
    id: str
    name: str
    description: str | None
    created_at: datetime


class PolicyCreate(ApiModel):
    name: str = Field(min_length=3, max_length=120)
    rules: dict = Field(default_factory=dict)


class PolicyResponse(ApiModel):
    id: str
    project_id: str
    name: str
    version: int
    is_active: bool
    rules: dict
    created_at: datetime


class DashboardSummary(ApiModel):
    metrics: list[dict]
    corpus_size: int
    protected_applications: int
    generated_at: datetime
    is_partial: bool = False


class RecentTestsResponse(ApiModel):
    items: list[dict]
    next_cursor: str | None = None


class ArenaSubmissionCreate(ApiModel):
    challenge_id: str = Field(min_length=1, max_length=40)
    test_run_id: str = Field(min_length=1, max_length=36)
