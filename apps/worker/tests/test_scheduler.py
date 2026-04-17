"""Unit tests do scheduler (API-14).

Estrategia: monkey-patch em `worker.scheduler` para substituir
`get_admin_session` / `get_tenant_session` por um fake que captura as
queries emitidas e devolve rows pre-configuradas. `enqueue` e injetado
via parametro de `run_tick` (stub que registra chamadas).

Cobre a DoD do ticket:

1. Tick feliz: 1 schedule devido com company_id explicito -> cria 1
   execution + 1 enqueue + atualiza next_run_at/last_run_at.
2. Tick sem schedules devidos -> summary zerado, sem enqueue.
3. Overlap: ha execution em `running` -> cria occurrence
   SCHEDULE_OVERLAP, NAO cria execution, NAO atualiza last_run_at.
4. Schedule tenant-wide (company_id=NULL) -> itera todas as companies
   ativas do tenant.
5. Enqueue falha depois do INSERT -> marca execution como failed com
   error_summary='enqueue_failed'.
6. Cron invalido -> pula o schedule sem atualizar campos, summary
   reflete apenas o processado.
7. build_scheduler usa cron `* * * * *` coalescente com max_instances=1.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from worker import scheduler as scheduler_module
from worker.scheduler import _DueSchedule, _TickSummary, build_scheduler, run_tick


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = list(rows) if rows is not None else []
        self._row = row

    def all(self):
        return self._rows

    def one(self):
        if self._row is None:
            raise RuntimeError("no row")
        return self._row

    def one_or_none(self):
        return self._row


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeSession:
    """Resposta estatica por `contains` case-insensitive no SQL.

    O scheduler emite um conjunto pequeno de SQLs distintos (SELECT
    schedules, SELECT companies, SELECT executions inflight, INSERT
    executions, INSERT occurrences, UPDATE schedules, UPDATE executions
    failed). Cada teste configura os matchers que precisa.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._answers: list[tuple[str, object]] = []

    def set_answer(self, sql_contains: str, response) -> None:
        self._answers.append((sql_contains.lower(), response))

    def execute(self, clause, params=None):
        sql = str(clause).lower()
        self.calls.append((sql, dict(params or {})))
        for key, response in self._answers:
            if key in sql:
                if isinstance(response, _FakeResult):
                    return response
                if isinstance(response, list):
                    return _FakeResult(rows=response)
                return _FakeResult(row=response)
        return _FakeResult(rows=[], row=None)

    def has_call(self, contains: str) -> bool:
        needle = contains.lower()
        return any(needle in sql for sql, _ in self.calls)

    def count_calls(self, contains: str) -> int:
        needle = contains.lower()
        return sum(1 for sql, _ in self.calls if needle in sql)


@pytest.fixture
def tenant_id() -> UUID:
    return uuid4()


@pytest.fixture
def schedule_id() -> UUID:
    return uuid4()


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def fake_sessions(monkeypatch):
    """Dois `_FakeSession`: admin (para SELECT schedules) e tenant.

    Retorna `(admin, tenant)`. Tenant e compartilhado por todas as chamadas
    `get_tenant_session(tid)` dentro do tick (simplifica; o scheduler
    real abre uma por schedule, mas os SQLs sao independentes).
    """
    admin = _FakeSession()
    tenant = _FakeSession()

    @contextmanager
    def _admin_cm():
        yield admin

    @contextmanager
    def _tenant_cm(_tid):
        yield tenant

    monkeypatch.setattr(scheduler_module, "get_admin_session", _admin_cm)
    monkeypatch.setattr(scheduler_module, "get_tenant_session", _tenant_cm)
    return admin, tenant


# ---------------------------------------------------------------------------
# run_tick
# ---------------------------------------------------------------------------


def test_run_tick_sem_schedules_devidos(fake_sessions) -> None:
    admin, _tenant = fake_sessions
    admin.set_answer("from schedules", [])

    summary = run_tick(now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc))

    assert summary == _TickSummary()


def test_run_tick_cria_execution_e_enqueue(
    fake_sessions, tenant_id, schedule_id, company_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=company_id,
                cron_expr="* * * * *",
                timezone="UTC",
            )
        ],
    )
    # Resolve company (company_id preenchido -> 1 row).
    tenant.set_answer("from companies\n                 where id =", _Row(id=company_id))
    # Nao ha execution inflight.
    tenant.set_answer("from executions\n             where company_id", None)
    # INSERT execution retorna id novo.
    new_execution_id = uuid4()
    tenant.set_answer("insert into executions", _Row(id=new_execution_id))

    calls: list[tuple[UUID, UUID]] = []

    def _enqueue(eid: UUID, tid: UUID) -> str:
        calls.append((eid, tid))
        return "job-123"

    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=_enqueue,
    )

    assert summary.picked == 1
    assert summary.executions_created == 1
    assert summary.overlaps == 0
    assert calls == [(new_execution_id, tenant_id)]
    # UPDATE com last_run_at setado.
    assert tenant.has_call("update schedules")
    update_calls = [
        params for sql, params in tenant.calls if "update schedules" in sql
    ]
    assert update_calls
    # Procura o UPDATE com `last_run_at = now()` (branch touched_last_run).
    assert any(
        "last_run_at = now()" in sql
        for sql, _ in tenant.calls
        if "update schedules" in sql
    )


def test_run_tick_overlap_cria_occurrence_sem_duplicar(
    fake_sessions, tenant_id, schedule_id, company_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=company_id,
                cron_expr="* * * * *",
                timezone="UTC",
            )
        ],
    )
    tenant.set_answer("from companies\n                 where id =", _Row(id=company_id))
    # Execution inflight -> overlap.
    tenant.set_answer("from executions\n             where company_id", _Row(presente=1))

    enqueue = MagicMock()
    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=enqueue,
    )

    assert summary.picked == 1
    assert summary.executions_created == 0
    assert summary.overlaps == 1
    # Enqueue nao chamado.
    enqueue.assert_not_called()
    # INSERT em occurrences feito (SCHEDULE_OVERLAP).
    occurrence_calls = [
        params for sql, params in tenant.calls if "insert into occurrences" in sql
    ]
    assert len(occurrence_calls) == 1
    # INSERT em executions NAO foi feito.
    assert not tenant.has_call("insert into executions")
    # UPDATE schedules aconteceu (recomputa next_run_at) mas sem
    # last_run_at = now() (branch overlap-only).
    update_sqls = [sql for sql, _ in tenant.calls if "update schedules" in sql]
    assert len(update_sqls) == 1
    assert "last_run_at = now()" not in update_sqls[0]


def test_run_tick_tenant_wide_itera_companies(
    fake_sessions, tenant_id, schedule_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=None,
                cron_expr="* * * * *",
                timezone="UTC",
            )
        ],
    )
    c1, c2, c3 = uuid4(), uuid4(), uuid4()
    # Resolve companies tenant-wide (match na query sem `where id`).
    tenant.set_answer(
        "from companies\n             where deleted_at is null",
        [_Row(id=c1), _Row(id=c2), _Row(id=c3)],
    )
    # Nenhuma inflight.
    tenant.set_answer("from executions\n             where company_id", None)
    # Cada INSERT retorna id diferente — simplificamos devolvendo o mesmo
    # placeholder porque `_insert_execution` nao usa o id de retorno em
    # nenhuma logica alem do enqueue.
    tenant.set_answer("insert into executions", _Row(id=uuid4()))

    calls: list[tuple[UUID, UUID]] = []

    def _enqueue(eid: UUID, tid: UUID) -> str:
        calls.append((eid, tid))
        return f"job-{len(calls)}"

    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=_enqueue,
    )

    assert summary.picked == 1
    assert summary.executions_created == 3
    assert summary.overlaps == 0
    assert len(calls) == 3


def test_run_tick_enqueue_falha_marca_execution_failed(
    fake_sessions, tenant_id, schedule_id, company_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=company_id,
                cron_expr="* * * * *",
                timezone="UTC",
            )
        ],
    )
    tenant.set_answer("from companies\n                 where id =", _Row(id=company_id))
    tenant.set_answer("from executions\n             where company_id", None)
    new_execution_id = uuid4()
    tenant.set_answer("insert into executions", _Row(id=new_execution_id))

    def _enqueue(eid: UUID, tid: UUID) -> str:
        raise RuntimeError("redis down")

    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=_enqueue,
    )

    assert summary.picked == 1
    assert summary.executions_created == 0
    assert summary.enqueue_failed == 1
    # UPDATE marcando execution como failed com error_summary='enqueue_failed'.
    failed_updates = [
        sql for sql, _ in tenant.calls
        if "update executions" in sql and "enqueue_failed" in sql
    ]
    assert len(failed_updates) == 1
    # Schedule UPDATE sem last_run_at (nenhuma execucao efetiva criada).
    update_sqls = [sql for sql, _ in tenant.calls if "update schedules" in sql]
    assert len(update_sqls) == 1
    assert "last_run_at = now()" not in update_sqls[0]


def test_run_tick_cron_invalido_pula_sem_atualizar(
    fake_sessions, tenant_id, schedule_id, company_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=company_id,
                cron_expr="xx yy zz ww vv",  # invalido
                timezone="UTC",
            )
        ],
    )

    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=lambda _eid, _tid: "",
    )

    assert summary.picked == 1
    assert summary.executions_created == 0
    # Nenhum UPDATE em schedules (preserva next_run_at para o owner investigar).
    assert not tenant.has_call("update schedules")
    # Tambem nao consultou companies (bailou antes).
    assert not tenant.has_call("from companies")


def test_run_tick_company_inexistente_pula_sem_erro(
    fake_sessions, tenant_id, schedule_id, company_id
) -> None:
    admin, tenant = fake_sessions
    admin.set_answer(
        "from schedules",
        [
            _Row(
                id=schedule_id,
                tenant_id=tenant_id,
                company_id=company_id,
                cron_expr="* * * * *",
                timezone="UTC",
            )
        ],
    )
    # Company soft-deleted ou inexistente -> 0 rows.
    tenant.set_answer("from companies\n                 where id =", None)

    summary = run_tick(
        now=datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc),
        enqueue=lambda _eid, _tid: "",
    )

    assert summary.picked == 1
    assert summary.executions_created == 0
    # Schedule ainda tem next_run_at avancado (evita loop infinito no tick).
    update_sqls = [sql for sql, _ in tenant.calls if "update schedules" in sql]
    assert len(update_sqls) == 1


# ---------------------------------------------------------------------------
# build_scheduler
# ---------------------------------------------------------------------------


def test_build_scheduler_cron_1min() -> None:
    pytest.importorskip("apscheduler")
    tick = MagicMock()
    scheduler = build_scheduler(tick=tick)
    try:
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        job = jobs[0]
        assert job.id == "scheduler.tick"
        # O trigger cron deve rodar a cada minuto em UTC.
        trigger = job.trigger
        # Acesso interno para verificar cron — APScheduler armazena em
        # `fields` com o minuto marcado como `*`.
        minute_field = next(f for f in trigger.fields if f.name == "minute")
        assert str(minute_field) == "*"
        assert trigger.timezone.key == "UTC"
        # coalesce e max_instances configurados.
        assert job.coalesce is True
        assert job.max_instances == 1
    finally:
        # Garante que o scheduler nao fique com threads de background
        # pendentes entre testes.
        if scheduler.running:
            scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# env helpers
# ---------------------------------------------------------------------------


def test_resolve_redis_url_exige_env(monkeypatch) -> None:
    monkeypatch.delenv("API_REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="API_REDIS_URL"):
        scheduler_module._resolve_redis_url()


def test_resolve_queue_name_default(monkeypatch) -> None:
    monkeypatch.delenv("API_QUEUE_NAME", raising=False)
    assert scheduler_module._resolve_queue_name() == "nfse-executions"


def test_due_schedule_dataclass_imutavel() -> None:
    sched = _DueSchedule(
        id=uuid4(),
        tenant_id=uuid4(),
        company_id=None,
        cron_expr="* * * * *",
        timezone="UTC",
    )
    with pytest.raises(Exception):
        sched.cron_expr = "0 3 * * *"  # type: ignore[misc]
