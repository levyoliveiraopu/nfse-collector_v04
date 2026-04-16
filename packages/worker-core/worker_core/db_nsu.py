"""`NsuSource` DB-backed para o worker SaaS (API-13).

Implementa o protocolo `NsuSource` (CORE-03) persistindo o valor em
``companies.last_nsu`` para uma dada `(tenant_id, company_id)`. Cada
`set()` abre uma transacao curta com `SET LOCAL app.current_tenant`
(RLS) e faz UPDATE only-if-greater para preservar o invariante "NSU
nunca regride".

Contrato da interface:
- `get(cnpj)` devolve o NSU atual da company cujo `cnpj` bate. Cross-
  CNPJ (uma company diferente chamando get com outro CNPJ) devolve 0 —
  o chamador nao deveria reusar um `DbNsuSource` para varias companies
  no mesmo lote.
- `set(cnpj, nsu)` so escreve se `nsu > last_nsu` (UPDATE WHERE
  condicional). Silencioso quando o valor nao progride.

Por que escopado por `(tenant_id, company_id)`: `fetch_nfse` chama
`source.get(cnpj)`/`source.set(cnpj, ...)` com um unico CNPJ por lote.
O handler `run_execution` cria uma instancia nova por execucao, evitando
confusao multi-company no mesmo Source.
"""

from __future__ import annotations

import logging
from typing import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("worker_core.db_nsu")


class DbNsuSource:
    """`NsuSource` que le/escreve `companies.last_nsu`.

    Args:
        tenant_id:       Tenant ID para o RLS GUC.
        company_id:      Company concreta cujo `last_nsu` sera manipulado.
        session_factory: Callable que devolve uma `Session` ja com
                         `SET LOCAL app.current_tenant` setado. Se None,
                         o caller deve fornecer `open_session` com o mesmo
                         contrato (factory sem argumentos retornando um
                         context manager).
    """

    def __init__(
        self,
        *,
        tenant_id: UUID | str,
        company_id: UUID | str,
        session_factory: Callable[[UUID | str], object],
    ) -> None:
        self._tenant_id = str(UUID(str(tenant_id)))
        self._company_id = str(UUID(str(company_id)))
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # NsuSource protocol
    # ------------------------------------------------------------------

    def get(self, cnpj: str) -> int:
        """Le `companies.last_nsu` para a company configurada.

        `cnpj` e aceito por compat com o protocolo mas nao e usado no
        filtro — a selecao ja vem por `company_id`. Se os dois nao
        baterem, devolve 0 (invariante: uma company = um CNPJ).
        """
        with self._open_session() as session:
            row = session.execute(
                text(
                    """
                    SELECT last_nsu, cnpj
                      FROM companies
                     WHERE id = :cid
                    """
                ),
                {"cid": self._company_id},
            ).one_or_none()
            if row is None:
                logger.warning(
                    "db_nsu.get.company_missing",
                    extra={
                        "tenant_id": self._tenant_id,
                        "company_id": self._company_id,
                    },
                )
                return 0
            if str(row.cnpj) != _digits(cnpj):
                logger.warning(
                    "db_nsu.get.cnpj_mismatch",
                    extra={
                        "company_id": self._company_id,
                        "company_cnpj_prefix": str(row.cnpj)[:8],
                        "requested_cnpj_prefix": _digits(cnpj)[:8],
                    },
                )
                return 0
            return int(row.last_nsu or 0)

    def set(self, cnpj: str, nsu: int) -> None:
        """UPDATE only-if-greater em `companies.last_nsu`.

        Silencioso quando `nsu` nao progride. Nao cria audit log — o
        handler registra em `executions`/`audit_logs` no fim.
        """
        if not isinstance(nsu, int) or isinstance(nsu, bool) or nsu < 0:
            raise ValueError(f"nsu deve ser int >= 0, recebido {nsu!r}")
        with self._open_session() as session:
            result = session.execute(
                text(
                    """
                    UPDATE companies
                       SET last_nsu = :nsu, updated_at = now()
                     WHERE id = :cid
                       AND cnpj = :cnpj
                       AND (last_nsu IS NULL OR last_nsu < :nsu)
                    """
                ),
                {
                    "cid": self._company_id,
                    "cnpj": _digits(cnpj),
                    "nsu": int(nsu),
                },
            )
            if result.rowcount:
                logger.info(
                    "db_nsu.set.updated",
                    extra={
                        "tenant_id": self._tenant_id,
                        "company_id": self._company_id,
                        "nsu": int(nsu),
                    },
                )
            else:
                logger.debug(
                    "db_nsu.set.noop",
                    extra={
                        "tenant_id": self._tenant_id,
                        "company_id": self._company_id,
                        "nsu": int(nsu),
                    },
                )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _open_session(self) -> Session:
        """Abre uma sessao nova escopada ao tenant. Usado em `get`/`set`."""
        return self._session_factory(self._tenant_id)  # type: ignore[return-value]


def _digits(value: str) -> str:
    """Normaliza CNPJ para somente digitos."""
    return "".join(ch for ch in str(value or "") if ch.isdigit())
