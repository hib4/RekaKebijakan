from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Alamat email tidak valid")
        return value


class RegisterInput(AuthInput):
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Nama terlalu pendek")
        return value


class LoginInput(AuthInput):
    pass


class ProjectInput(BaseModel):
    project_name: str = Field(min_length=2, max_length=160)
    institution: str = Field(min_length=2, max_length=160)
    objective: str = Field(min_length=2, max_length=1000)


class EnvironmentInput(BaseModel):
    rounds: Literal[3, 5, 8] = 5
    socialization: str = Field(default="Sedang", max_length=40)
    response_mode: str = Field(default="Responsif", max_length=40)


class InteractionInput(BaseModel):
    tool: Literal["report", "persona", "evidence", "risk", "compare", "revision"] = "report"
    question: str = Field(min_length=2, max_length=2000)
    persona_group: str | None = Field(default=None, max_length=120)


class InterviewInput(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    persona_ids: list[str] = Field(default_factory=list, max_length=10)


class GraphFeedbackInput(BaseModel):
    action: Literal["add_node", "update_node", "remove_node", "add_edge", "update_edge", "remove_edge"]
    target_id: str | None = None
    patch: dict = Field(default_factory=dict)
    reason: str = Field(min_length=2, max_length=2000)
    base_revision: int | None = None


class ProjectUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    institution: str | None = Field(default=None, min_length=2, max_length=160)
    objective: str | None = Field(default=None, min_length=2, max_length=1000)
    expected_version: int = Field(ge=1)


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    rounds: Literal[3, 5, 8] | None = None
    socialization: str | None = Field(default=None, max_length=40)
    response_mode: str | None = Field(default=None, max_length=40)


class ScenarioInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    kind: Literal["baseline", "revision", "custom"] = "custom"
    config: ScenarioConfig = Field(default_factory=ScenarioConfig)


class ScenarioUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    kind: Literal["baseline", "revision", "custom"] | None = None
    config: ScenarioConfig | None = None
    expected_version: int = Field(ge=1)


class PersonaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    group: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, min_length=1, max_length=160)
    stance: str | None = Field(default=None, min_length=1, max_length=80)
    concern: str | None = Field(default=None, min_length=1, max_length=1000)
    topics: list[str] | None = Field(default=None, max_length=20)
    count: int | None = Field(default=None, ge=1, le=1000)
    active: bool | None = None


class PersonaOverrideInput(BaseModel):
    expected_version: int = Field(ge=1)
    base_environment_revision: int = Field(ge=0)
    patch: PersonaPatch


class PersonaOverrideDeleteInput(BaseModel):
    expected_version: int = Field(ge=1)
    base_environment_revision: int = Field(ge=0)
