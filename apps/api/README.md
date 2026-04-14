# apps/api

Servico FastAPI do SaaS NFS-e (API-01).

## Rodar local

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn api.main:app --reload
```

Endpoints:

- `GET /health`  -> `{"status": "ok"}`
- `GET /version` -> `{"version": "...", "commit": "..."}`

## Configuracao

Variaveis de ambiente (prefixo `API_`):

| Variavel          | Default        | Descricao                                   |
|-------------------|----------------|---------------------------------------------|
| `API_ENVIRONMENT` | `development`  | `development` / `staging` / `production`.   |
| `API_LOG_LEVEL`   | `INFO`         | Nivel do root logger.                        |
| `API_VERSION`     | `0.1.0`        | Sobrescreve versao reportada em `/version`.  |
| `API_GIT_COMMIT`  | `unknown`      | Commit SHA; injetado no build Docker.        |
| `API_DATABASE_URL`| `""`           | URL Postgres (`postgresql+psycopg://...`).   |

`.env` na raiz do repo e lido automaticamente.

## Migrations (Alembic) — DATA-01

Estrutura em `apps/api/alembic/`:

- `alembic.ini` — configuracao base (URL e resolvida em `env.py`).
- `alembic/env.py` — le `API_DATABASE_URL` via `Settings`.
- `alembic/versions/0001_initial_identity.py` — tabelas `tenants`,
  `users`, `tenant_users`, roles `app_admin` / `app_user`, RLS com
  GUC `app.current_tenant`.
- `alembic/versions/0002_companies.py` — tabela `companies`
  (CNPJs por tenant) com unique `(tenant_id, cnpj)` e RLS (DATA-02).
- `alembic/versions/0003_company_credentials.py` — tabela
  `company_credentials` (PFX A1 cifrado) com FK composta para
  `companies(tenant_id, id)`, indice em `cert_not_after` para alerta
  de vencimento e RLS (DATA-02).
- `alembic/versions/0011_files.py` — tabela `files` (id, tenant_id,
  kind, object_key, bytes, checksum_sha256, source_execution_id,
  expires_at) sem `storage_tier` (ADR-003), com RLS. Tambem faz o
  **merge dos dois heads** Alembic (`0003_company_credentials` e
  `0010_auth_refresh_tokens`) — a partir daqui a arvore e linear
  novamente (DATA-05).
- `alembic/versions/0012_schedules.py` — tabela `schedules` (cron
  por tenant/company) com FK composta para `companies(tenant_id, id)`,
  indice `(enabled, next_run_at)` e RLS (DATA-05).
- `alembic/versions/0013_audit_logs.py` — tabela `audit_logs`
  (bigserial, metadata jsonb) com indices `(tenant_id, created_at
  DESC)` e `(resource_type, resource_id)` e RLS (DATA-05).
- `alembic/versions/0014_plans_subscriptions.py` — tabelas `plans`
  (catalogo global, sem RLS) e `subscriptions` (uma por tenant, com
  RLS); promove `tenants.plan_id` a FK -> `plans.code` (DATA-05).
- `alembic/versions/0004_executions.py` — tabela `executions`
  (uma corrida de coleta por tenant+company) com FK composta para
  `companies(tenant_id, id)`, indice `(tenant_id, company_id,
  started_at DESC)` para listagem por periodo, CHECKs de
  `trigger`/`status`/ordem do periodo/soma de itens e RLS (DATA-03).
- `alembic/versions/0005_execution_items.py` — tabela
  `execution_items` (um item por NFS-e processada) com FK composta
  para `executions(tenant_id, id)`, indice `(execution_id)`, indice
  `(tenant_id, data_emissao)` e indice unico parcial
  `(tenant_id, chave_nfse) WHERE chave_nfse IS NOT NULL`; RLS
  (DATA-03).

### Comandos

Rodar a partir de `apps/api/`:

```bash
# Sobe para a ultima revisao.
alembic upgrade head

# Reverte uma revisao.
alembic downgrade -1

# Override pontual da URL (testes/sandbox).
alembic -x url=postgresql+psycopg://app_admin:***@localhost:5432/nfse upgrade head
```

A URL precisa apontar para uma role com permissao de criar extensoes,
roles e policies (ex.: `postgres` ou o `app_admin` com privilegio). A
API em runtime deve usar `app_user`, que **nao** e `BYPASSRLS`.

### Teste manual de isolamento RLS (DoD)

Com `alembic upgrade head` aplicado, abra dois `psql` conectados como
`app_user` e valide:

```sql
-- Sessao 1
BEGIN;
INSERT INTO tenants (name, slug) VALUES ('Acme', 'acme')
  RETURNING id;
-- anote o UUID retornado como :t1

SET LOCAL app.current_tenant = ':t1';
SELECT id, slug FROM tenants;           -- deve listar apenas Acme
INSERT INTO users (email, name)
  VALUES ('ana@acme.test', 'Ana') RETURNING id;
-- anote :u1
INSERT INTO tenant_users (tenant_id, user_id, role)
  VALUES (':t1', ':u1', 'owner');
SELECT * FROM tenant_users;             -- ve a associacao
COMMIT;

-- Sessao 2 (novo tenant)
BEGIN;
INSERT INTO tenants (name, slug) VALUES ('Beta', 'beta')
  RETURNING id;                         -- :t2
SET LOCAL app.current_tenant = ':t2';
SELECT * FROM tenants;                  -- ve apenas Beta
SELECT * FROM tenant_users;             -- vazio
COMMIT;
```

Sem `SET LOCAL app.current_tenant`, qualquer `SELECT` em `tenants` /
`tenant_users` pelo `app_user` retorna vazio (fail-closed).

## Auth — API-02

Endpoints em `/auth/*`:

| Metodo | Rota            | Descricao                                               |
|--------|-----------------|---------------------------------------------------------|
| POST   | `/auth/signup`  | Cria tenant + user (role `owner`) e devolve tokens.     |
| POST   | `/auth/login`   | Autentica por email/senha. Rate-limit 5/min/IP.         |
| POST   | `/auth/refresh` | Rotaciona o refresh (detecta reuso de token revogado).  |
| POST   | `/auth/logout`  | Revoga o refresh apresentado.                           |

Detalhes:

- **Hash de senha**: argon2id (`argon2-cffi`) com parametros OWASP 2024
  (m=19 MiB, t=2, p=1). O hash embute os parametros — rotacao futura
  sem invalidar hashes antigos.
- **Access token**: JWT HS256, TTL default 15 min (claims `sub`, `tid`,
  `role`, `jti`, `iss`, `aud`).
- **Refresh token**: opaco (`secrets.token_urlsafe(32)`), TTL default
  7 dias, armazenado como SHA-256 hex em `refresh_tokens`. Rotacao
  marca `revoked_at` no antigo e grava `replaced_by` apontando para o
  novo. Reuso de refresh ja revogado invalida toda a cadeia
  (`WITH RECURSIVE`).
- **RLS**: a tabela `refresh_tokens` tem RLS por `tenant_id` via GUC
  `app.current_tenant` (mesmo padrao DATA-01). Os endpoints de auth
  rodam com `get_admin_session()` (BYPASSRLS pelo role do cluster)
  porque `/signup` e `/login` nao tem tenant_id definido no request.
- **Rate limit**: slowapi + `get_remote_address` — in-memory. Em prod
  multi-worker vamos precisar de backend Redis (TODO).
- **JWT secret**: `API_JWT_SECRET` obrigatorio em `staging`/`production`
  (validator em `Settings` derruba a startup se vazio). Em
  `development` cai para um fallback explicito e inseguro.

### Variaveis de ambiente

| Variavel                        | Default       | Descricao                             |
|---------------------------------|---------------|---------------------------------------|
| `API_JWT_SECRET`                | `""`          | Obrigatorio em staging/production.    |
| `API_JWT_ISSUER`                | `nfse-api`    | Claim `iss`.                          |
| `API_JWT_AUDIENCE`              | `nfse-web`    | Claim `aud`.                          |
| `API_ACCESS_TOKEN_TTL_MINUTES`  | `15`          | TTL do JWT.                           |
| `API_REFRESH_TOKEN_TTL_DAYS`    | `7`           | TTL do refresh.                       |
| `API_LOGIN_RATE_LIMIT`          | `5/minute`    | Formato slowapi.                      |

### Fluxo E2E com curl (DoD)

```bash
BASE=http://localhost:8000

# 1) Signup — cria tenant + user owner + par de tokens.
curl -sS -X POST "$BASE/auth/signup" \
  -H 'content-type: application/json' \
  -d '{
        "tenant_name": "Acme Contabil",
        "tenant_slug": "acme",
        "name": "Ana Silva",
        "email": "ana@acme.test",
        "password": "super-senha-123"
      }' | tee /tmp/signup.json

ACCESS=$(jq -r .access_token /tmp/signup.json)
REFRESH=$(jq -r .refresh_token /tmp/signup.json)

# 2) Login — valida argon2id e emite novo par.
curl -sS -X POST "$BASE/auth/login" \
  -H 'content-type: application/json' \
  -d '{"email":"ana@acme.test","password":"super-senha-123"}' \
  | tee /tmp/login.json

REFRESH=$(jq -r .refresh_token /tmp/login.json)

# 3) Refresh — rotaciona.
curl -sS -X POST "$BASE/auth/refresh" \
  -H 'content-type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}" | tee /tmp/refresh.json

NEW_REFRESH=$(jq -r .refresh_token /tmp/refresh.json)

# 4) Refresh antigo reusado — 401 (e cadeia invalidada).
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/auth/refresh" \
  -H 'content-type: application/json' \
  -d "{\"refresh_token\":\"$REFRESH\"}"

# 5) Logout — revoga o refresh atual.
curl -sS -X POST "$BASE/auth/logout" \
  -H 'content-type: application/json' \
  -d "{\"refresh_token\":\"$NEW_REFRESH\"}"
```

### Testes

Testes unitarios (argon2, JWT, entropia do refresh, migration estatica):

```bash
cd apps/api
PYTHONPATH=. pytest tests/test_auth_password.py tests/test_auth_jwt.py \
  tests/test_auth_tokens_unit.py tests/test_migration_0010.py -v
```

Testes de integracao (E2E contra Postgres real) — pulam se
`TEST_DATABASE_URL` nao estiver setada:

```bash
# 1) suba um Postgres vazio e aplique as migrations
export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
alembic -x url="$TEST_DATABASE_URL" upgrade head

# 2) rode os testes — o banco e TRUNCADO a cada teste
PYTHONPATH=. pytest tests/test_auth_routes_integration.py -v
### Teste manual de isolamento RLS — companies/credentials (DATA-02 DoD)

Com `alembic upgrade head` aplicado, conectado como `app_user`:

```sql
-- Sessao 1 (tenant Acme)
BEGIN;
SET LOCAL app.current_tenant = ':t1';
INSERT INTO companies (tenant_id, cnpj, razao_social, municipio_ibge, uf)
  VALUES (':t1', '00000000000191', 'Acme LTDA', '3550308', 'SP')
  RETURNING id;                        -- :c1
INSERT INTO company_credentials
  (tenant_id, company_id, pfx_object_key, pfx_password_ciphertext)
  VALUES (':t1', ':c1', 'tenants/:t1/:c1/cert.pfx', decode('deadbeef','hex'));
SELECT COUNT(*) FROM companies;            -- 1
SELECT COUNT(*) FROM company_credentials;  -- 1
COMMIT;

-- Sessao 2 (tenant Beta) — nao deve enxergar nada da sessao 1
BEGIN;
SET LOCAL app.current_tenant = ':t2';
SELECT * FROM companies;             -- vazio
SELECT * FROM company_credentials;   -- vazio
-- Tentativa de inserir credencial apontando para company de outro tenant
-- (com tenant_id correto) falha na FK composta (:t2, :c1):
INSERT INTO company_credentials
  (tenant_id, company_id, pfx_object_key, pfx_password_ciphertext)
  VALUES (':t2', ':c1', 'x', decode('00','hex'));
-- ERROR: insert or update on table "company_credentials" violates
-- foreign key constraint "fk_company_credentials_tenant_company"
ROLLBACK;
```

## DATA-05 — tabelas de suporte

Criadas em 4 migrations (`0011_files`, `0012_schedules`, `0013_audit_logs`,
`0014_plans_subscriptions`):

- **`files`**: referencias de objetos no S3 (INFRA-06). `kind` aceita
  `nfse_xml`, `export`, `pfx`, `report`, `other`. Sem `storage_tier`
  (ADR-003). Unique `(tenant_id, object_key)`, indice partial em
  `expires_at` para o cron de purga 90d.
- **`schedules`**: cron por tenant (com `company_id` opcional). FK
  composta `(tenant_id, company_id) -> companies` como defesa em
  profundidade. Indice `(enabled, next_run_at)` para o scheduler.
- **`audit_logs`**: append-only. `id bigint IDENTITY`, `actor_user_id`
  nullable (`ON DELETE SET NULL`), `metadata jsonb` default `'{}'`.
  Indices `(tenant_id, created_at DESC)` e `(resource_type,
  resource_id)`.
- **`plans`** (catalogo global, sem RLS): `code` PK TEXT, `limits jsonb`,
  `price_cents int`, `active bool`. `app_user` tem apenas `SELECT`.
- **`subscriptions`** (RLS): unica por tenant (`UNIQUE(tenant_id)`),
  FK -> `plans(code)` com `ON DELETE RESTRICT`. Status `trialing` |
  `active` | `past_due` | `canceled` | `paused`. Billing adiado
  (ADR-004) — os campos `gateway*` ficam NULL ate a integracao real.
- **Promocao** da coluna `tenants.plan_id` a FK `-> plans(code)`
  (mantida `NULL`-able para tenants em trial).

### Merge de heads Alembic (nota operacional)

Ate DATA-02/API-02 a arvore tinha dois heads (`0003_company_credentials`
e `0010_auth_refresh_tokens`). A migration `0011_files` declara
`down_revision = ("0003_company_credentials", "0010_auth_refresh_tokens")`,
funcionando como ponto de merge explicito. Apos `alembic upgrade head`
a arvore volta a ser linear.

### Teste manual de insercao massiva (DoD audit_logs 10k rows)

Com `TEST_DATABASE_URL` apontando para um Postgres isolado e
`alembic upgrade head` aplicado:

```bash
export TEST_DATABASE_URL="postgresql+psycopg://app_admin:***@localhost:5432/nfse_test"
alembic -x url="$TEST_DATABASE_URL" upgrade head
PYTHONPATH=. pytest tests/test_audit_logs_bulk.py -v
```

O teste insere 10k linhas em batch num tenant ficticio e valida
timeline com `EXPLAIN`.
### Teste manual de isolamento RLS — executions/execution_items (DATA-03 DoD)

Com `alembic upgrade head` aplicado, conectado como `app_user`
(assume tenants/companies criados na secao DATA-02 acima):

```sql
-- Sessao 1 (tenant Acme)
BEGIN;
SET LOCAL app.current_tenant = ':t1';
INSERT INTO executions
  (tenant_id, company_id, trigger, period_start, period_end,
   status, started_at, nsu_from, nsu_to, items_total, items_ok, items_fail)
  VALUES (':t1', ':c1', 'manual', '2026-03-01', '2026-03-31',
          'running', now(), 1000, 1050, 50, 0, 0)
  RETURNING id;                             -- :e1
INSERT INTO execution_items
  (execution_id, tenant_id, nsu, chave_nfse, cnpj_emitente,
   data_emissao, valor, status)
  VALUES (':e1', ':t1', 1001, 'chv-0000001', '00000000000191',
          '2026-03-15T10:00:00-03', 123.45, 'ok');
SELECT COUNT(*) FROM executions;            -- 1
SELECT COUNT(*) FROM execution_items;       -- 1
COMMIT;

-- Sessao 2 (tenant Beta) — nao deve enxergar nada da sessao 1
BEGIN;
SET LOCAL app.current_tenant = ':t2';
SELECT * FROM executions;            -- vazio
SELECT * FROM execution_items;       -- vazio
-- Tentativa de inserir item apontando para execucao de outro tenant
-- falha na FK composta (:t2, :e1):
INSERT INTO execution_items (execution_id, tenant_id, status)
  VALUES (':e1', ':t2', 'pending');
-- ERROR: insert or update on table "execution_items" violates
-- foreign key constraint "fk_execution_items_tenant_execution"
ROLLBACK;
```

Duplicata por chave dentro do mesmo tenant deve falhar no indice unico
parcial:

```sql
BEGIN;
SET LOCAL app.current_tenant = ':t1';
INSERT INTO execution_items (execution_id, tenant_id, chave_nfse, status)
  VALUES (':e1', ':t1', 'chv-0000001', 'ok');
-- ERROR: duplicate key value violates unique constraint
-- "uq_execution_items_tenant_chave"
ROLLBACK;
```

**EXPLAIN de listagem por periodo (DoD).** A query abaixo precisa
usar o indice composto `ix_executions_tenant_company_started`:

```sql
EXPLAIN
SELECT id, status, started_at, items_total, items_ok, items_fail
FROM executions
WHERE tenant_id = ':t1'
  AND company_id = ':c1'
  AND started_at BETWEEN '2026-03-01' AND '2026-03-31'
ORDER BY started_at DESC
LIMIT 50;
-- Espera: Index Scan using ix_executions_tenant_company_started
## Middleware de tenant — API-03

Toda request protegida passa por tres dependencies encadeadas
(`apps/api/api/deps.py`), que materializam o "middleware de tenant":

1. `get_current_claims` — le `Authorization: Bearer <jwt>`, valida via
   `decode_access_token`. Ausencia de header, esquema != Bearer ou JWT
   invalido/expirado -> **401** com `WWW-Authenticate: Bearer`.
2. `assert_tenant_active` — consulta `tenants.status` via
   `get_admin_session` (BYPASSRLS). Tenant inexistente, `suspended` ou
   `canceled` -> **403**.
3. `get_tenant_db` — abre sessao com `SET LOCAL app.current_tenant = :tid`
   dentro da transacao (via `get_tenant_session` do `api.db`). No
   commit/rollback o escopo do `SET LOCAL` morre, portanto a conexao
   devolvida ao pool **nao vaza** GUC entre requests.

Handlers protegidos declaram:

```python
from api.deps import assert_tenant_active, get_tenant_db

@router.get("/rota-privada")
def handler(
    claims: AccessClaims = Depends(assert_tenant_active),
    db: Session = Depends(get_tenant_db),
): ...
```

Rotas publicas (`/health`, `/version`, `/auth/signup`, `/auth/login`,
`/auth/refresh`, `/auth/logout`) nao declaram essas dependencies e
seguem como antes.

### `GET /auth/me` (prova de vida)

Responde 200 com `{tenant_id, user_id, role, memberships_visible}`. A
contagem em `tenant_users` e RLS-gated: se o middleware nao tivesse
setado `app.current_tenant`, a query retornaria `0`.

```bash
ACCESS=$(jq -r .access_token /tmp/login.json)

curl -sS "$BASE/auth/me" \
  -H "Authorization: Bearer $ACCESS"
# {"tenant_id":"...","user_id":"...","role":"owner","memberships_visible":1}

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/auth/me"
# 401 (sem token)

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/auth/me" \
  -H "Authorization: Bearer not-a-jwt"
# 401
```

### Runbook manual de isolamento cross-tenant

Com `alembic upgrade head` e a API subida, crie dois tenants via signup
e valide que cada token so enxerga o proprio tenant:

```bash
# Tenant A
curl -sS -X POST "$BASE/auth/signup" \
  -H 'content-type: application/json' \
  -d '{"tenant_name":"Acme","tenant_slug":"acme","name":"Ana",
       "email":"a@acme.test","password":"super-senha-123"}' | tee /tmp/a.json
AT=$(jq -r .access_token /tmp/a.json)

# Tenant B
curl -sS -X POST "$BASE/auth/signup" \
  -H 'content-type: application/json' \
  -d '{"tenant_name":"Beta","tenant_slug":"beta","name":"Bia",
       "email":"b@beta.test","password":"super-senha-456"}' | tee /tmp/b.json
BT=$(jq -r .access_token /tmp/b.json)

# Cada /auth/me deve reportar memberships_visible == 1 (so a propria).
curl -sS "$BASE/auth/me" -H "Authorization: Bearer $AT" | jq
curl -sS "$BASE/auth/me" -H "Authorization: Bearer $BT" | jq

# Suspender tenant A via SQL e validar 403:
psql "$API_DATABASE_URL" -c \
  "UPDATE tenants SET status='suspended' WHERE slug='acme';"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/auth/me" \
  -H "Authorization: Bearer $AT"
# 403
```

### Testes

Unitarios (sem DB):

```bash
cd apps/api
PYTHONPATH=. pytest tests/test_tenant_middleware.py -v
```

E2E (gated por `TEST_DATABASE_URL`, mesmo padrao do API-02):

```bash
PYTHONPATH=. pytest tests/test_tenant_middleware_integration.py -v
```

## Build Docker

```bash
docker build \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t nfse-api:dev \
  apps/api
docker run --rm -p 8000:8000 nfse-api:dev
curl http://localhost:8000/health
```
