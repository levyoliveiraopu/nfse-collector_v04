# lib/api — cliente tipado gerado do OpenAPI (DS-09)

Estrutura:

- `generated/schema.d.ts` — tipos TypeScript gerados por
  `openapi-typescript` a partir do OpenAPI da API. **Nao editar a mao.**
- `client.ts` — factory `createApiClient` + singleton `getApiClient`
  baseados em `openapi-fetch`. Middleware de auth injeta
  `Authorization: Bearer <token>` e retenta uma unica vez em 401 com
  `tryRefresh` da APP-01; se o refresh falhar, chama `onAuthFailure`
  (default: redirect para `/login`).
- `types.ts` — re-exports tipados (`paths`, `components`, `operations`).
- `hooks.ts` — hooks react-query base (`useHealth`, `useVersion`,
  `useMe`, `useCompanies`, `useExecutions`).

## Regerar

```
# API local em :8000 (default)
pnpm --filter web-app generate-api

# URL alternativa (staging):
API_OPENAPI_URL=https://api.staging.example/openapi.json \
  pnpm --filter web-app generate-api

# Ler de arquivo:
pnpm --filter web-app generate-api --file /tmp/openapi.json
```

O script e idempotente: reexecutar sem mudancas no OpenAPI nao altera
`generated/schema.d.ts`.

## Clientes legados

Os helpers em `lib/api/companies.ts`, `lib/auth/api-client.ts`,
`lib/users/api-client.ts` e `lib/companies/credentials.ts` continuam
operando sem alteracao — a migracao para `createApiClient` sera feita
em tickets futuros por trilha.
