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

## Build Docker

```bash
docker build \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  -t nfse-api:dev \
  apps/api
docker run --rm -p 8000:8000 nfse-api:dev
curl http://localhost:8000/health
```
