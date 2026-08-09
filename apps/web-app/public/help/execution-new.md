## Para que serve

Inicia uma coleta manual para uma ou mais empresas em um período definido.

## Antes de iniciar

Confirme que cada empresa está ativa e possui credencial válida. Períodos grandes podem demorar mais e aumentar o volume processado.

## Passo a passo

1. Selecione uma ou mais empresas.
2. Defina as datas inicial e final; ambas são incluídas na consulta.
3. Use **Simulação** apenas para validar sem executar a coleta real, quando disponível.
4. Use **Incremental** para continuar a sequência já conhecida, quando essa opção estiver disponível.
5. Revise e selecione **Iniciar execução**.

## Regras

- Owner, admin e operator iniciam coletas; viewer apenas consulta.
- A distribuição nacional avança por NSU. Evite reiniciar cursores para separar meses.
- Uma credencial inválida bloqueia a empresa antes do envio ao worker.

## Erros comuns

- **Nenhuma empresa selecionada:** marque pelo menos uma.
- **Credencial ausente ou vencida:** regularize a credencial e tente novamente.
- **Período inválido:** a data final não pode ser anterior à inicial.
