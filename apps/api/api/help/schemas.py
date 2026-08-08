"""Schemas publicos dos endpoints de ajuda contextual."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HelpEventType = Literal[
    "article_opened",
    "search_performed",
    "search_no_results",
    "tour_started",
    "tour_completed",
    "tour_skipped",
    "tour_failed",
    "feedback_yes",
    "feedback_no",
]

RouteKey = Literal[
    "dashboard",
    "companies",
    "company_detail",
    "credential",
    "executions",
    "execution_new",
    "execution_detail",
    "schedules",
    "occurrences",
    "occurrence_detail",
    "files",
    "users",
    "subscription",
    "help",
]

_SAFE_ID = r"^[a-z0-9][a-z0-9_-]{0,79}$"


class HelpEventIn(BaseModel):
    """Evento anonimo e normalizado; nunca recebe texto pesquisado ou URL."""

    model_config = ConfigDict(extra="forbid")

    event_type: HelpEventType
    article_slug: str | None = Field(default=None, pattern=_SAFE_ID, max_length=80)
    route_key: RouteKey | None = None
    tour_id: str | None = Field(default=None, pattern=_SAFE_ID, max_length=80)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> "HelpEventIn":
        if self.event_type in {
            "article_opened",
            "feedback_yes",
            "feedback_no",
        } and not self.article_slug:
            raise ValueError("article_slug e obrigatorio para o evento")
        if self.event_type in {"search_performed", "search_no_results"}:
            if not self.route_key:
                raise ValueError("route_key e obrigatorio para pesquisa")
        if self.event_type.startswith("tour_"):
            if not self.route_key or not self.tour_id:
                raise ValueError("route_key e tour_id sao obrigatorios para tour")
        return self


class HelpInsightsTotals(BaseModel):
    article_opened: int = 0
    search_performed: int = 0
    search_no_results: int = 0
    tour_started: int = 0
    tour_completed: int = 0
    tour_skipped: int = 0
    tour_failed: int = 0
    feedback_yes: int = 0
    feedback_no: int = 0


class HelpInsightRow(BaseModel):
    article_slug: str
    route_key: str
    article_opened: int = 0
    search_performed: int = 0
    search_no_results: int = 0
    tour_started: int = 0
    tour_completed: int = 0
    tour_skipped: int = 0
    tour_failed: int = 0
    feedback_yes: int = 0
    feedback_no: int = 0


class HelpInsightsOut(BaseModel):
    days: Literal[7, 30, 90]
    date_from: date
    date_to: date
    totals: HelpInsightsTotals
    rows: list[HelpInsightRow]
