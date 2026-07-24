from typing import Literal

from pydantic import BaseModel, Field


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
