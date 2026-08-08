# Ambiente local completo

Esta stack sobe o SaaS inteiro no Docker Desktop, sem depender do checkout WSL
antigo nem de servicos pagos. Os dados ficam em volumes do projeto Compose
`nfse-local` e somente o proxy HTTP e publicado em `127.0.0.1`.

## Iniciar

Na raiz do repositorio, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\local\start.ps1
```

O script gera `infra/local/.env.local` com segredos aleatorios, constroi as
imagens, aplica migrations, cria o bucket MinIO, executa o seed e abre o
navegador. Em novas execucoes, os mesmos segredos e volumes sao reutilizados.
Se a porta 3000 estiver ocupada na primeira execucao, ele escolhe a primeira
porta livre ate 3099 e imprime a URL correta.

- Painel: `http://localhost:3000`
- Swagger: `http://localhost:3000/backend/docs`
- Login: `admin@demo.local`
- Senha: `demo12345`

O numero da porta pode mudar conforme explicado acima. A conta e a senha sao
exclusivas do ambiente local em `API_ENVIRONMENT=development`.

## Operacao

Os comandos abaixo devem ser executados na raiz do repositorio:

```powershell
$envFile = "infra/local/.env.local"
$compose = "infra/compose/docker-compose.local.yml"

# Estado
docker compose -p nfse-local --env-file $envFile -f $compose ps

# Logs
docker compose -p nfse-local --env-file $envFile -f $compose logs -f

# Parar preservando os dados
docker compose -p nfse-local --env-file $envFile -f $compose down

# Subir novamente e abrir o navegador
powershell -ExecutionPolicy Bypass -File .\infra\local\start.ps1
```

Para validar sem abrir o navegador automaticamente, use `-NoBrowser`.

Para definir explicitamente o ADN e o nome exibido do tenant, sem alterar o
slug nem criar outra conta, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\infra\local\start.ps1 `
  -AdnEnvironment PRODUCAO -TenantName "Vice Versa"
```

Quando esses parametros sao omitidos, o script preserva os valores existentes
em `.env.local`. Use `PRODUCAO` somente com certificados validos e autorizados.

## Limpeza total

O comando abaixo remove os containers e os volumes do ambiente local. Ele e
destrutivo e apaga tenants, usuarios, filas e objetos do MinIO:

```powershell
docker compose -p nfse-local --env-file infra/local/.env.local `
  -f infra/compose/docker-compose.local.yml down -v
```

Os containers antigos `nfse-postgres` e `nfse-redis` nao pertencem ao projeto
`nfse-local` e nao sao alterados por nenhum desses comandos.
