## Para que serve

Execuções registram cada tentativa de coleta, seja manual, agendada ou de reprocessamento.

## Como acompanhar

1. Filtre pelo status desejado.
2. Confira empresa, período, quantidade de itens e início.
3. Abra a execução para analisar o resultado completo.
4. Use Ocorrências quando houver um erro que exija ação humana.

## Significado dos status

- **Na fila:** aguardando um worker.
- **Em execução:** processamento ativo.
- **Concluída:** processamento terminou sem falhas conhecidas.
- **Parcial:** terminou com itens que falharam ou exigem conferência.
- **Falhou:** a execução não conseguiu concluir.
- **Cancelada:** foi interrompida antes do fim.

## Quando escalar

Escale quando várias empresas falharem com o mesmo erro, a fila não avançar ou o portal continuar indisponível após novas tentativas controladas.
