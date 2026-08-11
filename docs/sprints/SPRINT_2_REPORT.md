# SPRINT 2 — Relatório
## Data Engine — IQO Strategy Lab

**Data:** 2026-08-11
**Status:** Concluída. Suíte completa (44 testes) passando contra PostgreSQL real.

---

## 1. Resumo

Construída a camada de dados completa: `CSVProvider → Normalizer → Validator → CandleRepository → PostgreSQL`, com detecção de qualidade (duplicados, gaps, fora de ordem, OHLC/preço/timestamp inválidos), importação idempotente em lote, histórico de importações, API REST, CLI e uma página **Data Center** no frontend.

Nenhum item proibido (indicadores, estratégias, sinais, backtest, execução) foi tocado. Nenhuma integração real com IQ Option foi implementada — apenas a abstração `DataProvider`, já existente desde a Sprint 1, agora com uma implementação concreta (`CSVProvider`).

Todos os 44 testes (11 novos de infraestrutura da Sprint 1 + 33 novos desta Sprint) passam contra o PostgreSQL real que já estava rodando desde a Sprint 1.

---

## 2. Arquitetura implementada

```text
CSV (data/raw/)
      │
      ▼
CSVProvider.read_raw_rows()          — lê o arquivo, sem interpretar nada
      │
      ▼
normalize_rows()                     — column mapping, parsing numérico/timestamp,
      │                                 ordenação, detecção de fora-de-ordem
      ▼
validate_candles()                   — OHLC, preço, timestamp/timezone/tolerância futura
      │
      ├── candles válidos ──────────► CandleRepository.bulk_insert()
      │                                 (ON CONFLICT DO NOTHING, idempotente, em lotes)
      │                                        │
      │                                        ▼
      │                                  PostgreSQL (tabela candles)
      │
      └── candles inválidos ────────► descartados, contabilizados no import job
                                        (nunca persistidos — "não inventar dados")

DataIngestionService orquestra as quatro etapas acima e grava um registro em
`data_imports` com o resultado (status, contagens, amostra de erros).
```

Rotas HTTP não executam SQL — tudo passa por `CandleRepository` / `ImportRepository`
(`API → Service → Repository → Database`, conforme exigido).

---

## 3. Providers

- **`DataProvider`** (`app/data/providers/base.py`, já existia da Sprint 1): abstração única, `get_candles(symbol, timeframe, start, end)`.
- **`CSVProvider`** (`app/data/providers/csv_provider.py`): implementação concreta. Suporta `column_mapping` configurável (ex.: `from`→`timestamp`, `max`→`high`, `min`→`low`) para lidar com datasets que não usam os nomes canônicos de coluna.
- **ParquetProvider**: **não implementado** — decisão consciente (ver seção 14) para não comprometer a qualidade do CSVProvider por causa de uma extensão opcional (seção 22 da Sprint permite isso).
- **IQOptionProvider**: intencionalmente não criado nesta Sprint, conforme exigido.

---

## 4. Modelo Candle

`app/data/types.py`:

```python
Candle(symbol, timeframe, timestamp, open, high, low, close, source, volume=None)
```

- **Timeframe**: `M1 M5 M15 M30 H1 H4 D1` (enum `str`, com `.duration` para detecção de gaps).
- **DataSource**: `CSV PARQUET IQ_OPTION OTHER`.
- **Preços**: `Decimal`, nunca `float` — evita drift de arredondamento.
- **Timestamp**: não há validação de timezone na *construção* do dataclass (decisão documentada na seção 14) — a validação real acontece em `app/data/validation.py`, o que permite testar "timezone ausente" como um caso de validação normal em vez de uma exceção na construção do objeto.

---

## 5. Database

Tabela `candles` (migration `962cfd6f7660_add_candles_and_data_imports_tables.py`, aplicada contra o Postgres real):

```text
id, symbol, timeframe, timestamp(tz-aware), open/high/low/close NUMERIC(18,8),
volume NUMERIC(18,8) nullable, source, created_at
UNIQUE(symbol, timeframe, timestamp) + índice composto na mesma chave
```

Tabela `data_imports`:

```text
id, provider, source_file, symbol, timeframe, started_at, finished_at, status,
total_rows, valid_rows, invalid_rows, duplicates, gaps, errors (amostra JSON)
```

Precisão numérica: `NUMERIC(18,8)` explícito (não `float`, não deixado implícito), documentado no código-fonte (`app/database/models.py`).

---

## 6. Ingestion

`DataIngestionService.ingest_csv()` (`app/data/ingestion.py`):

- Cria um registro `RUNNING` em `data_imports` antes de processar.
- Lê + normaliza + valida.
- Insere apenas candles **válidos**, em lotes de 5.000 (`CandleRepository.bulk_insert`), via `INSERT ... ON CONFLICT (symbol, timeframe, timestamp) DO NOTHING`.
- Fecha o registro de importação com status final: `COMPLETED` (tudo válido), `PARTIAL` (parte válida), `FAILED` (nada válido ou arquivo ilegível).
- Logs estruturados: `IMPORT_STARTED`, `CANDLE_INVALID` (limitado a 10 amostras, depois um resumo agregado — nunca milhões de linhas em log), `DATA_GAP`, `DUPLICATE_CANDLE`, `IMPORT_COMPLETED`/`IMPORT_FAILED`.

**Idempotência**: reimportar o mesmo arquivo não duplica nada — verificado por teste de integração real (seção 11).

---

## 7. Validation

`app/data/validation.py`:

| Regra | Resultado |
|---|---|
| `high < open/close/low` ou `low > open/close/high` | `INVALID_OHLC` |
| preço `<= 0`, `NaN` ou infinito | `INVALID_PRICE` |
| timestamp sem timezone | `INVALID_TIMESTAMP` |
| timestamp no futuro além da tolerância (padrão: 5s, configurável) | `FUTURE_TIMESTAMP` |

Um candle é persistido **somente se não tiver nenhum issue**. Conforme exigido: o sistema nunca inventa, interpola ou corrige dados — apenas registra o que está errado e descarta.

---

## 8. Data Quality

`app/data/quality.py`:

- `detect_gaps()`: compara timestamps consecutivos contra a duração esperada do timeframe.
- `compute_quality_score()`: `100 × (válidos/total)`, com penalidades limitadas (até 10 pontos por gaps, 5 por duplicados, 5 por fora-de-ordem) — documentado como ferramenta de triagem, não como fórmula a ser otimizada.
- `compute_quality_report()`: monta o `DataQualityReport` completo (mesmo shape do exemplo da seção 17 da Sprint, mais `last_timestamp` — adicionado para alimentar o Data Center).

Dois contextos de uso:
1. **No momento da importação** (`DataIngestionService`): reflete a qualidade do arquivo importado (inclui inválidos, duplicados, fora-de-ordem).
2. **Sob demanda** (`GET /api/candles/quality`, `CandleRepository.get_quality`): reflete a qualidade do que está *armazenado agora* — como só candles válidos e únicos chegam ao banco, `invalid_candles`/`duplicates`/`out_of_order` são sempre 0 aqui; só `gaps` é significativo. Essa diferença está documentada no código (docstring de `get_quality`).

---

## 9. API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/candles?symbol=&timeframe=&start=&end=` | Consulta candles armazenados |
| GET | `/api/candles/{symbol}?timeframe=&start=&end=` | Mesma consulta, símbolo na URL |
| GET | `/api/candles/quality?symbol=&timeframe=` | Relatório de qualidade do que está no banco |
| POST | `/api/data/import` | Importa um CSV de `data/raw/` |
| GET | `/api/data/imports?limit=` | Histórico de importações |

`POST /api/data/import` valida o caminho recebido contra path traversal: o arquivo precisa resolver para dentro de `data/raw/` (testado explicitamente com `../../etc/passwd` e com um arquivo real fora de `data/raw/` — ambos retornam 400).

---

## 10. CLI

```bash
uv run python -m app.cli import-csv --file data/raw/test/eurusd_m1_sample.csv --symbol EURUSD --timeframe M1
uv run python -m app.cli validate --symbol EURUSD --timeframe M1
```

Ambos verificados manualmente contra o Postgres real nesta sessão (símbolo de demonstração removido depois). Saída do `import-csv`:

```text
Import PARTIAL
  import_id:    12
  total_rows:   10
  valid_rows:   6
  invalid_rows: 4
  duplicates:   1
  inserted:     5
  gaps:         1
```

---

## 11. Testes

**44 testes, todos passando contra PostgreSQL real** (o mesmo container `iqolab-postgres` da Sprint 1):

```text
tests/data/test_types.py            3 testes  (Timeframe válido/inválido, duration)
tests/data/test_validation.py       8 testes  (OHLC, preço zero/negativo, timestamp naive, future tolerance)
tests/data/test_normalizer.py      10 testes  (ordenação, out-of-order, UTC, Decimal, column mapping, erros de parsing)
tests/data/test_csv_provider.py     5 testes  (arquivo válido, mapping, coluna faltando, CSV vazio, filtro de range)
tests/data/test_quality.py          7 testes  (gaps, score, report)
tests/data/integration/
  test_ingestion_idempotency.py     1 teste   (importar 2x = mesmo resultado no banco)
  test_pipeline.py                  4 testes  (pipeline completo via service + via API, path traversal)
  test_performance.py               1 teste   (100.000 candles)
tests/test_config.py + test_health.py   5 testes (Sprint 1, continuam passando)

44 passed in ~35s
```

O dataset `data/raw/test/eurusd_m1_sample.csv` (documentado em `data/raw/test/README.md`) cobre deliberadamente: válido, duplicado, gap, OHLC inválido, timestamp sem timezone, preço negativo, timestamp não-parseável e fora de ordem — os mesmos números aparecem nos testes unitários, de integração e na verificação manual da CLI, então qualquer regressão futura nesse pipeline quebra em pelo menos três lugares diferentes.

Todos os testes de integração usam símbolos prefixados com `TEST_` e são limpos automaticamente após cada teste (`tests/data/integration/conftest.py`) — não deixam resíduo no banco.

---

## 12. Performance

100.000 candles sintéticos (1 arquivo CSV, sem gaps/duplicados/inválidos) importados em **30,6s** (~3.267 candles/s), medido com Postgres real via `uv run pytest tests/data/integration/test_performance.py -s`.

Não houve otimização — o objetivo desta Sprint era descobrir gargalos, não eliminá-los. Se isso se tornar um problema quando o Backtest Engine precisar de datasets maiores, os candidatos óbvios para otimizar primeiro são: parsing de `Decimal` (mais caro que `float`), e trocar `INSERT ... VALUES` em lote por `COPY`.

---

## 13. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | Comparar um timestamp *naive* (sem timezone) com um *aware* (UTC) levanta `TypeError` em Python. Isso quebraria a ordenação do Normalizer e o filtro de range do `CSVProvider.get_candles` assim que qualquer linha tivesse timestamp sem timezone — exatamente o caso que o dataset de teste foi desenhado para cobrir. | Criado `app/data/timeutils.to_comparable_utc()`, usado apenas para comparação/ordenação (nunca para persistência ou validação) — trata naive como se fosse UTC só para fins de ordenação, sem alterar o valor real do candle. |
| 2 | `Candle` como dataclass `frozen` originalmente rejeitava timestamp naive na construção (`__post_init__` lançava `ValueError`). Isso tornaria impossível testar "timezone ausente" como um *resultado* de validação (seção 31 da Sprint pede exatamente esse teste) — a exceção aconteceria antes de chegar ao Validator. | Removida a validação da construção; documentado no docstring que `Candle` é só a forma de dado, e `app.data.validation` é a única fonte de verdade sobre o que é válido. |
| 3 | Rotas FastAPI (`/api/candles`, `/api/candles/{symbol}`) colidiam potencialmente com `/api/candles/quality` se registradas na ordem errada (`{symbol}` capturaria `quality` como valor do path param). | Registrado `/quality` antes de `/{symbol}` no `APIRouter`; testado explicitamente (`test_import_and_query_via_api` faz as duas chamadas). |

Nenhum outro problema bloqueante.

---

## 14. Decisões arquiteturais

- **Candles inválidos nunca são persistidos.** A tabela `candles` só contém dados que passaram por `validate_candle`. Isso mantém a garantia "não inventar dados" simples de auditar (basta olhar o schema) em vez de precisar de uma coluna `is_valid` e filtrar em toda consulta futura.
- **Duplicidade é definida na inserção**, não como uma etapa separada de detecção: o `UNIQUE(symbol, timeframe, timestamp)` + `ON CONFLICT DO NOTHING` cobre tanto duplicatas já existentes no banco quanto duplicatas dentro do mesmo lote de importação, com uma única fonte de verdade (a constraint do banco, não lógica Python duplicada).
- **ParquetProvider não implementado.** A interface (`DataProvider`) já suporta, mas implementá-lo agora arriscava tempo/qualidade do CSVProvider por uma funcionalidade que a Sprint marca como opcional. Fica documentado como próximo passo natural quando houver um dataset Parquet real para testar contra.
- **Quality report tem dois significados dependendo de onde é chamado** (import-time vs. query-time) — documentado explicitamente em vez de forçar os dois casos a compartilhar os mesmos números artificialmente.
- **CLI usa `SessionLocal()` diretamente**, não a dependency injection do FastAPI (`get_db`) — são contextos diferentes (processo de linha de comando vs. request HTTP), então reaproveitar a mesma função faria pouco sentido; ambos usam o mesmo `SessionLocal` por baixo.
- **Frontend: Data Center sem UI de importação.** Só leitura (tabela de datasets + histórico de importações). Import continua via API/CLI, conforme a Sprint permite explicitamente quando a UI de importação aumentaria complexidade sem necessidade nesta fase.

---

## 15. Pendências

Nenhuma pendência técnica bloqueante. Duas notas de escopo, deliberadas:

1. **ParquetProvider** não implementado (ver seção 14) — pode ser adicionado como extensão pontual quando houver necessidade real.
2. **UI de importação no frontend** não criada (ver seção 14) — importação seguirá via `POST /api/data/import` ou CLI até que uma Sprint de dashboard justifique construir esse formulário.

---

## 16. Próxima Sprint

Aguardando autorização explícita para iniciar a **Sprint 3**, que segundo a ordem definida na documentação (`docs/architecture.md`, seção 49) é o **Indicators Engine** (EMA, SMA, RSI, MACD, Bollinger, ATR, Stochastic, CCI) — consumindo candles através de `CandleRepository`/`get_candles`, nunca do provider diretamente.
