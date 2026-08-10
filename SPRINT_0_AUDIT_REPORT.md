# SPRINT 0 — Relatório de Auditoria
## IQO Strategy Lab

**Data:** 2026-08-10
**Raiz do projeto:** `c:\Users\STI- NTBK\Documents\RB IQ`
**Conclusão principal:** Projeto **greenfield** — não existe código legado para auditar.

---

## 1. Resumo executivo

A pasta do projeto contém **apenas um arquivo**: `doc.txt`, que é a própria especificação técnica completa do IQO Strategy Lab (a documentação de destino, não código implementado).

Não existe backend, frontend, banco de dados, scripts, testes, configuração, dependências, integração com IQ Option, nem repositório Git. Não há nada para "reaproveitar", "refatorar" ou "remover" — porque nada foi implementado ainda.

Confirmado com o usuário: **não há projeto legado em outro local**. Este é um início do zero.

Isso significa que a Sprint 0, tal como desenhada (auditoria de legado), não se aplica em sua forma completa. O que segue é a auditoria adaptada à realidade encontrada, mais a preparação necessária para a Sprint 1.

---

## 2. Estado atual

| Item | Estado |
|---|---|
| Projeto inicia | NÃO EXISTE |
| Compila | NÃO EXISTE |
| Instala dependências | NÃO EXISTE |
| Erros/Warnings | NÃO EXISTE (nada para compilar) |
| Testes | NÃO EXISTE |
| Banco de dados | NÃO EXISTE |
| Migrations | NÃO EXISTE |
| Conexão com fonte de dados | NÃO EXISTE |
| Integração com IQ Option | NÃO EXISTE |
| Geração de sinais | NÃO EXISTE |
| Estratégias | NÃO EXISTE |
| Backtest | NÃO EXISTE |
| Paper trading | NÃO EXISTE |
| Dashboard | NÃO EXISTE |
| Git | NÃO EXISTE (pasta não é repositório) |

---

## 3. Stack encontrada

Nenhuma. Nenhum arquivo de configuração (`package.json`, `requirements.txt`, `pyproject.toml`, `docker-compose.yml`, `.env`) está presente.

A stack descrita no `doc.txt` (Python 3.11+/FastAPI no backend, React+TypeScript+Vite no frontend, PostgreSQL) é uma **recomendação de destino**, ainda não implementada.

---

## 4. Arquitetura atual

Não aplicável — não há arquitetura implementada, apenas a arquitetura-alvo descrita na documentação (seção 4 e 7 do `doc.txt`).

---

## 5. Arquitetura recomendada

Adotar integralmente a arquitetura já especificada em `doc.txt`:

```text
Data Provider → Data Normalizer → Market Database → Indicators → Market Structure
→ Market Regime → Strategy Engine → Signal Engine → Backtest / Paper Trading
→ Performance → Dashboard
```

Princípios a preservar (já corretos na documentação, não precisam ser revisados):
- estratégias nunca acessam o provider diretamente;
- backtester desacoplado de estratégias específicas (via `StrategyRegistry`);
- dashboard sem lógica de negócio;
- interface comum de estratégia (`prepare/evaluate/get_parameters`);
- proibição de look-ahead bias;
- separação train/validation/test/live.

---

## 6. Estratégias encontradas

Nenhuma implementada. Seis estratégias estão **especificadas** (não codificadas):

| Nome | Estado | Decisão |
|---|---|---|
| Trend Following | NÃO EXISTE | IMPLEMENTAR (Sprint 5, conforme fases) |
| Pullback | NÃO EXISTE | IMPLEMENTAR |
| Breakout | NÃO EXISTE | IMPLEMENTAR |
| Mean Reversion | NÃO EXISTE | IMPLEMENTAR |
| Price Action | NÃO EXISTE | IMPLEMENTAR |
| Divergence | NÃO EXISTE | IMPLEMENTAR |

---

## 7. Backtest encontrado

NÃO EXISTE. Requisitos (walk-forward, out-of-sample, Monte Carlo, proibição de look-ahead) estão documentados, nada implementado.

---

## 8. Banco de dados

NÃO EXISTE. Nenhuma instância, schema ou migration presente. Recomendação da documentação (PostgreSQL em produção, SQLite permitido em dev local) é razoável e será adotada na Sprint 1/2.

---

## 9. Frontend

NÃO EXISTE. Nenhum `package.json`, código React ou build tool presente.

---

## 10. Problemas críticos

Nenhum. Não há código com defeitos porque não há código.

## 11. Problemas altos

Nenhum problema de código. Ponto de atenção operacional: a pasta do projeto ainda não é um repositório Git — recomenda-se inicializar Git antes de começar a Sprint 1, para rastrear todo o histórico de implementação desde o início.

## 12. Problemas médios

Nenhum.

## 13. Problemas baixos

Nenhum.

---

## 14. Dependências

Nenhuma instalada ou declarada. A lista de dependências-alvo (pandas, numpy, pydantic, SQLAlchemy, Alembic, httpx, websockets, pytest, pytest-asyncio, loguru, scipy, scikit-learn no backend; React/TS/Vite no frontend) está descrita no `doc.txt` e será a base para o `pyproject.toml`/`package.json` da Sprint 1.

---

## 15. Segurança

Nenhuma credencial, arquivo `.env` ou segredo encontrado no diretório — não há superfície de risco ainda. Ponto a garantir desde o primeiro commit: `.env` deve entrar no `.gitignore` e nunca ser versionado, conforme já exigido na seção 40 da documentação.

---

## 16. Código aproveitável

N/A — nenhum código existe para ser aproveitado.

---

## 17. Código para reescrever

N/A.

---

## 18. Código para remover

N/A.

---

## 19. Dívida técnica

Nenhuma dívida técnica de código. Dívida "documental/organizacional" existente:
- projeto ainda não versionado em Git;
- `doc.txt` está solto na raiz — poderia ser movido para `docs/architecture.md` (ou similar) quando a estrutura de pastas da Sprint 1 for criada, preservando-o como referência viva.

---

## 20. Plano recomendado de reconstrução

Não há "reconstrução" — é construção do zero, seguindo exatamente a ordem de fases já definida em `doc.txt` (seção 49):

1. **Fase 1 — Infraestrutura**: backend, frontend, PostgreSQL, Docker, config, logging, health check.
2. **Fase 2 — Data Engine**: provider, normalização, candles, armazenamento, validação.
3. **Fase 3 — Indicators Engine**: EMA, SMA, RSI, MACD, Bollinger, ATR, Stochastic, CCI + testes.
4. **Fase 4 — Market Structure**: swings, suporte/resistência, regime.
5. **Fase 5 — Strategy Engine**: as 6 estratégias.
6. **Fase 6 — Backtest**: engine, simulator, métricas, walk-forward, out-of-sample.
7. **Fase 7 — Paper Trading**.
8. **Fase 8 — Dashboard**.
9. **Fase 9 — Robustez**.

Nenhuma fase deve avançar sem testes da fase anterior, conforme já determinado na documentação.

---

## 21. Bloqueadores da Sprint 1

1. **Confirmar ausência de legado** — feito nesta Sprint (confirmado com o usuário: greenfield).
2. **Inicializar Git** no diretório do projeto antes do primeiro código, para rastreabilidade desde a Fase 1.
3. **Decidir gerenciador de dependências Python** (pip+venv, Poetry ou pipenv) — não especificado no `doc.txt`, precisa de decisão antes da Sprint 1.
4. **Decidir se PostgreSQL será via Docker local desde já ou SQLite inicialmente** — a documentação permite ambos, mas a Sprint 1 precisa de uma escolha concreta.
5. **Definir fonte de dados históricos para desenvolvimento/backtest** (arquivos CSV/Parquet locais vs. integração real com IQ Option desde o início) — a documentação não define a origem dos primeiros candles usados nos testes.

Nenhum bloqueador é técnico/crítico — são decisões de configuração inicial, esperadas em uma Sprint 0/1 de projeto novo.

---

## Matriz de problemas

| ID | Problema | Severidade | Arquivo | Impacto | Solução |
|---|---|---|---|---|---|
| — | Nenhum problema de código identificado — projeto ainda não implementado | — | — | — | — |

**Não há problemas críticos, altos, médios ou baixos de código a reportar.**

---

## Matriz de aproveitamento

| Componente | Estado | Decisão |
|---|---|---|
| Connector | Não existe | Implementar na Fase 2 |
| Candle Engine | Não existe | Implementar na Fase 2 |
| Indicators | Não existe | Implementar na Fase 3 |
| Strategies | Não existe | Implementar na Fase 5 |
| Backtest | Não existe | Implementar na Fase 6 |
| Database | Não existe | Implementar na Fase 1 (schema) |
| Frontend | Não existe | Implementar na Fase 1 (scaffold) / Fase 8 (dashboard completo) |
| Documentação (`doc.txt`) | Completa e coerente | Manter como referência; mover para `docs/` na Fase 1 |

---

## Critério de conclusão

- [x] projeto identificado (greenfield, sem legado);
- [x] stack identificada (nenhuma implementada; stack-alvo já definida no `doc.txt`);
- [x] arquitetura atual documentada (inexistente);
- [x] dependências identificadas (nenhuma instalada; lista-alvo mapeada);
- [x] estratégias identificadas (nenhuma implementada; 6 especificadas);
- [x] backtest auditado (inexistente);
- [x] banco auditado (inexistente);
- [x] frontend auditado (inexistente);
- [x] segurança auditada (nenhum segredo exposto);
- [x] problemas classificados (nenhum encontrado);
- [x] código aproveitável identificado (N/A);
- [x] código a reescrever identificado (N/A);
- [x] arquitetura futura definida (a do `doc.txt`, validada);
- [x] relatório criado.

**Sprint 0 concluída.**

---

## Próximo passo

Aguardando autorização explícita para iniciar a **Sprint 1 — Infraestrutura Base**, que deve resolver primeiro os 5 bloqueadores listados na seção 21 (Git, gerenciador de dependências, Postgres vs SQLite local, fonte de dados de desenvolvimento) antes de escrever código.
