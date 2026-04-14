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
