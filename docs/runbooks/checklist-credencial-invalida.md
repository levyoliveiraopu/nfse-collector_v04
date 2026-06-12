# Checklist de suporte — Credencial invalida / certificado vencido

Use pelo suporte quando o cliente reportar falha de coleta associada a
`CRED_INVALID`, `CERT_EXPIRED`, `CERT_EXPIRING` ou autenticação mTLS.

## Perguntas para o cliente

- O certificado e A1 em formato `.pfx`/`.p12`?
- A senha foi testada recentemente no emissor/contador?
- O CNPJ do certificado corresponde ao CNPJ cadastrado na empresa?
- O certificado esta dentro da validade?
- Houve troca recente de certificado ou senha?

## Conferencias internas

1. Abrir a company no painel e conferir CNPJ cadastrado.
2. Verificar occurrence mais recente e codigo operacional.
3. Conferir `cert_not_after` da credencial cadastrada.
4. Confirmar se a credencial ativa e a mais recente.
5. Nunca pedir senha por chat aberto; orientar upload pelo fluxo seguro do app.

## Resposta padrao

- Se expirado: solicitar renovacao do certificado A1 e novo upload.
- Se senha incorreta: solicitar novo upload informando a senha correta no campo seguro.
- Se CNPJ divergente: orientar cadastro da empresa correta ou certificado correspondente.
- Se portal indisponivel: usar `docs/runbooks/portal-indisponivel.md` em vez deste checklist.

## Fechamento

- Confirmar nova coleta `succeeded` ou `partial` sem occurrence de credencial.
- Registrar no ticket qual codigo foi resolvido.
- Nao armazenar PFX, senha ou prints contendo dados sensiveis fora do sistema.
