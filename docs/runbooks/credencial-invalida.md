# Runbook — credencial invalida

## Escopo

Use este runbook para ocorrencias com os codigos:

- `CERT_EXPIRED`
- `CRED_INVALID`
- `CERT_REVOKED`

## Sintomas

- Coletas falham no inicio da autenticacao mTLS.
- Mensagens de erro sobre certificado invalido, expirado ou revogado.
- Reprocessamentos repetem a falha sem avancar para consulta de notas.

## Causas comuns

1. **Certificado expirado** (`CERT_EXPIRED`): data de validade (`notAfter`) ja passou.
2. **Certificado revogado** (`CERT_REVOKED`): certificado revogado pela AC.
3. **Senha do PFX alterada** (`CRED_INVALID`): senha informada nao corresponde ao arquivo.
4. **CN incorreto para o tenant** (`CRED_INVALID`): certificado pertence a outro CNPJ/entidade.

## Acoes do cliente

1. Gerar ou exportar novo arquivo PFX A1 valido no emissor/AC.
2. Confirmar senha atual do PFX com quem gerou o certificado.
3. Enviar o novo PFX pelo fluxo de credenciais da plataforma.
4. Validar se o certificado enviado corresponde ao CNPJ da empresa correta.
5. Solicitar novo processamento apos atualizacao da credencial.

## Acoes do suporte

1. Confirmar o codigo da ocorrencia e o tenant impactado.
2. Validar metadados do certificado (validade e subject/CN) sem expor segredos.
3. Se expirado/revogado, orientar troca imediata do certificado.
4. Se senha invalida, solicitar novo upload com senha confirmada.
5. Registrar no historico da ocorrencia as acoes tomadas e proximo passo.

## Como verificar localmente (OpenSSL)

> Nao compartilhe senha ou arquivo PFX em canais publicos.

### 1) Ler validade e subject

```bash
openssl pkcs12 -in certificado.pfx -nokeys -clcerts -passin pass:'SENHA_DO_PFX' \
  | openssl x509 -noout -subject -issuer -dates -serial
```

Conferir especialmente:

- `notAfter` (nao pode estar no passado).
- `subject` (CN/CNPJ deve bater com o tenant).

### 2) Verificar se a senha do PFX esta correta

```bash
openssl pkcs12 -info -in certificado.pfx -noout -passin pass:'SENHA_DO_PFX'
```

Se a senha estiver incorreta, o comando retorna erro de MAC/decrypt.

### 3) Exportar certificado para analise adicional (opcional)

```bash
openssl pkcs12 -in certificado.pfx -nokeys -clcerts -passin pass:'SENHA_DO_PFX' -out cert.pem
openssl x509 -in cert.pem -noout -text
```

Use a saida para revisar cadeia, EKU e dados de subject quando necessario.
