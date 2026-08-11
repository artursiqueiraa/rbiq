# Dataset de teste do Data Engine

Uso exclusivo para testar o pipeline `CSVProvider → Normalizer → Validator → Repository`.
Não usar para avaliar desempenho de estratégia — os valores são arbitrários.

## `eurusd_m1_sample.csv`

10 linhas, símbolo `EURUSD`, timeframe `M1`, cobrindo os casos exigidos pela Sprint 2:

| Linha | Timestamp (arquivo) | Caso |
|---|---|---|
| 1 | 10:00:00Z | válida |
| 2 | 10:01:00Z | válida |
| 3 | 10:02:00Z | válida |
| 4 | 10:02:00Z | duplicada de #3 (mesma chave symbol+timeframe+timestamp) |
| 5 | 10:05:00Z | válida — gap antes dela (faltam 10:03 e 10:04) |
| 6 | 10:06:00Z | OHLC inválido (high 1.0500 < low 1.0900) |
| 7 | 10:07:00 (sem `Z`) | timestamp sem timezone → `INVALID_TIMESTAMP` |
| 8 | 10:08:00Z | preço inválido (open negativo) |
| 9 | `not-a-timestamp` | erro de parsing no Normalizer (linha descartada antes de virar Candle) |
| 10 | 09:59:00Z | válida, mas fora de ordem no arquivo (aparece depois da linha 5, cronologicamente antes) |

Resultado esperado ao importar este arquivo pela primeira vez:

```text
total_rows:     10
valid_rows:      6   (#1, #2, #3, #4, #5, #10)
invalid_rows:    4   (#6, #7, #8, #9)
duplicates:      1   (a segunda ocorrência de 10:02:00Z, na inserção)
inserted:        5
gaps:            1   (entre 10:02:00Z e 10:05:00Z)
out_of_order:    1   (linha #10 chega depois de #5 no arquivo)
```

Importar o mesmo arquivo uma segunda vez deve inserir `0` novos candles (idempotência) —
`duplicates` na segunda rodada será `5` (todos os válidos já existem).

## `mapped_columns.csv`

Mesmo formato lógico, mas com colunas renomeadas (`from`, `max`, `min`) — usado para testar
o `column_mapping` do `CSVProvider`.

## `empty.csv`

Só o cabeçalho, sem linhas — usado para testar o caso "CSV vazio".

## `missing_column.csv`

Sem a coluna `close` — usado para testar o caso "coluna faltando".
