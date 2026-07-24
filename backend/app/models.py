from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AuthInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)

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
