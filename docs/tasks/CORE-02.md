# CORE-02 — Refactor: credenciais por argumento (sem disco)

- **Trilha:** worker
- **Tamanho:** M
- **Status:** blocked (aguarda CORE-01)
- **Depende de:** CORE-01

## Objetivo

`auth.py` deve aceitar `pfx_bytes: bytes` e `pfx_password: str` em vez
de path para arquivo PFX. PEM temporario deve ser criado em `tmpfs`
(`/dev/shm`) com permissao 600, dentro de um context manager que
**garante** apagamento ao sair (sucesso ou excecao).

## Entregaveis

- `worker_core/auth.py` com funcao/classe:
  ```
  with mtls_session(pfx_bytes, pfx_password) as session:
      resp = session.get(...)
  ```
- Logs nao contem senha, PEM ou bytes do PFX.
- Teste unitario com PFX de teste gerado em fixture.
- Teste: arquivo PEM e removido mesmo em excecao.

## Definition of Done

- [ ] Assinatura nova disponivel e testada.
- [ ] Caminho legado (path) ainda funciona via wrapper de compat.
- [ ] Logs revisados (grep por padroes proibidos).
