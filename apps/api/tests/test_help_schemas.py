"""Contratos dos eventos anonimizados da ajuda."""

import pytest
from pydantic import ValidationError

from api.help.schemas import HelpEventIn


@pytest.mark.parametrize(
    ("event_type", "extra"),
    [
        ("article_opened", {"article_slug": "schedules"}),
        ("search_performed", {"route_key": "help"}),
        ("search_no_results", {"route_key": "files"}),
        (
            "tour_completed",
            {"route_key": "schedules", "tour_id": "schedules-tour"},
        ),
        ("feedback_yes", {"article_slug": "files"}),
    ],
)
def test_accepts_normalized_events(event_type: str, extra: dict) -> None:
    event = HelpEventIn(event_type=event_type, **extra)
    assert event.event_type == event_type


@pytest.mark.parametrize(
    "payload",
    [
        {"event_type": "article_opened"},
        {"event_type": "tour_started", "route_key": "dashboard"},
        {"event_type": "search_performed"},
        {"event_type": "unknown", "route_key": "help"},
        {"event_type": "article_opened", "article_slug": "segredo fiscal"},
        {
            "event_type": "search_performed",
            "route_key": "company/uuid-dinamico",
        },
        {
            "event_type": "search_performed",
            "route_key": "help",
            "query": "texto que nao pode sair do navegador",
        },
    ],
)
def test_rejects_missing_or_sensitive_dimensions(payload: dict) -> None:
    with pytest.raises(ValidationError):
        HelpEventIn(**payload)
