# SPRINT 1 — Relatório
## Infraestrutura Base — IQO Strategy Lab

**Data:** 2026-08-10
**Status:** Concluída, com uma pendência de verificação (ver seção 10).

---

## 1. Resumo

A infraestrutura base do projeto foi criada do zero: backend FastAPI com configuração centralizada, logging estruturado, SQLAlchemy 2.x + Alembic, uma abstração `DataProvider` (sem integração real), frontend React + TypeScript + Vite consumindo a API para mostrar status ao vivo, Docker Compose para PostgreSQL, testes automatizados nos dois lados, `.gitignore`/`.env.example` corretos, README completo e o primeiro commit Git.

Nenhum item das seções 34 ("não implementar nesta Sprint") foi tocado: sem IQ Option, sem sinais, sem estratégias, sem indicadores, sem backtest, sem paper trading, sem dashboard além da página de status.

**Uma decisão de infraestrutura desta máquina ficou pendente**: o PostgreSQL via Docker não pôde ser validado em execução real (detalhes na seção 10).

---

## 2. Arquivos criados

```text
iqo-strategy-lab/
├── .env.example
├── .gitignore
├── README.md
├── docker-compose.yml
│
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                  (aponta para Settings.database_url e Base.metadata)
│   │   └── versions/19745c274703_initial.py   (migration inicial, no-op)
│   ├── app/
│   │   ├── main.py                 (FastAPI + lifespan + CORS)
│   │   ├── api/
│   │   │   ├── dependencies.py
│   │   │   └── routes/system.py    (health, health/database, health/full)
│   │   ├── core/
│   │   │   ├── config.py           (Settings via pydantic-settings)
│   │   │   ├── logging.py          (loguru)
│   │   │   └── exceptions.py
│   │   ├── database/
│   │   │   ├── session.py          (engine, SessionLocal, get_db, check_database_connection)
│   │   │   └── models.py           (Base declarativo, sem tabelas ainda)
│   │   └── data/
│   │       ├── types.py            (Timeframe, Asset, Candle)
│   │       └── providers/base.py   (DataProvider abstrata)
│   └── tests/
│       ├── test_health.py
│       └── test_config.py
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx / App.css / App.test.tsx
│   │   ├── pages/HomePage.tsx
│   │   ├── components/StatusRow.tsx
│   │   ├── hooks/useSystemStatus.ts
│   │   ├── services/systemService.ts
│   │   ├── types/system.ts
│   │   └── setupTests.ts
│   └── vite.config.ts               (com bloco `test` do Vitest)
│
├── docs/
│   ├── architecture.md              (conteúdo original de doc.txt, cópia validada byte-a-byte)
│   └── sprints/SPRINT_1_REPORT.md   (este arquivo)
│
├── data/{raw,normalized,exports}/.gitkeep
└── scripts/check-dev.ps1
```

---

## 3. Dependências adicionadas

### Backend (`uv`, `pyproject.toml`)

Runtime: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `alembic`, `psycopg[binary]`, `loguru`, `httpx`.
Dev: `pytest`, `pytest-asyncio`.

Versões resolvidas relevantes (via `uv sync`): fastapi 0.141.1, sqlalchemy 2.0.51, alembic 1.19.1, pydantic 2.13.4, psycopg 3.3.4, uvicorn 0.52.1, pytest 9.1.1. Lockfile em `backend/uv.lock`.

### Frontend (`npm`, `package.json`)

Runtime: `react` 19.2.8, `react-dom` 19.2.8.
Dev: `vite` 8.2.1, `@vitejs/plugin-react`, `typescript`, `vitest` 4.1.10, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `oxlint`.

Nenhuma dependência foi adicionada além do necessário para infraestrutura + testes.

---

## 4. Serviços Docker

`docker-compose.yml` define um único serviço, conforme exigido (sem Redis, sem serviços extras):

```yaml
postgres:
  image: postgres:16-alpine
  ports: ["5432:5432"]
  healthcheck: pg_isready
```

Variáveis via `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, todas com defaults `iqolab`).

---

## 5. Endpoints

| Método | Rota | Testado | Resultado |
|---|---|---|---|
| GET | `/api/system/health` | Sim (pytest) | 200, `{"status":"healthy","service":"iqo-strategy-lab","version":"0.1.0"}` |
| GET | `/api/system/health/database` | Sim (pytest) | 503 no momento (Postgres não está no ar nesta máquina) — comportamento correto |
| GET | `/api/system/health/full` | Não coberto por teste dedicado | Implementado, mesma lógica dos dois anteriores combinada |

---

## 6. Testes executados

### Backend — `uv run pytest`

```text
tests/test_config.py::test_settings_load_with_defaults PASSED
tests/test_config.py::test_get_settings_is_cached PASSED
tests/test_health.py::test_api_starts_and_health_returns_200 PASSED
tests/test_health.py::test_health_response_shape PASSED
tests/test_health.py::test_database_health_reports_status_field PASSED

5 passed in 7.61s
```

### Frontend — `npm run test` (Vitest) e `npm run build`

```text
Test Files  1 passed (1)
     Tests  1 passed (1)
```

`npm run build` (tsc -b && vite build) concluiu sem erros, gerando `frontend/dist/`.

---

## 7. Resultado dos testes

Todos os testes criados nesta Sprint passam. Cobertura é intencionalmente mínima (infraestrutura, não lógica de negócio), conforme escopo da Sprint 1.

---

## 8. Problemas encontrados

| # | Problema | Como foi resolvido |
|---|---|---|
| 1 | `uv` e Docker não estavam instalados na máquina | `uv` instalado via `pip install uv` (autorizado pelo usuário). Docker Desktop instalado via `winget` (autorizado pelo usuário) — ver pendência na seção 10. |
| 2 | `check_database_connection()` sem timeout de conexão fazia o teste `/health/database` levar ~4min20s para retornar 503 (timeout TCP default do SO ao tentar conectar em uma porta sem serviço) | Adicionado `connect_args={"connect_timeout": 3}` ao engine SQLAlchemy. Tempo do teste caiu de 263s para 7.6s. Isso também evita que o health check trave a API real em produção se o Postgres cair. |
| 3 | `@app.on_event("startup")` está deprecado no FastAPI atual | Substituído por `lifespan` (context manager), que é o padrão recomendado — evita misturar estilos antigo/novo conforme exigido na seção 14 da Sprint. |

Nenhum outro problema bloqueante.

---

## 9. Decisões arquiteturais

- **SQLAlchemy síncrono** (não `asyncio`) para esta Sprint: não há candles/streaming ainda, e um único padrão síncrono e consistente é mais simples de auditar do que misturar sync/async prematuramente. Pode ser revisitado na Sprint 2 se o Data Engine exigir I/O assíncrono pesado.
- **`DataProvider` como classe abstrata (`ABC`)** com um único método `get_candles`, em `app/data/providers/base.py` — nenhuma implementação concreta (CSV/Parquet/IQ Option) foi criada, conforme exigido.
- **Tipos de domínio mínimos** (`Timeframe`, `Asset`, `Candle`) em `app/data/types.py` — apenas o necessário para a assinatura do `DataProvider` fazer sentido; modelagem completa do domínio fica para sprints futuras.
- **`docs/architecture.md`** substitui `doc.txt` na raiz; conteúdo copiado e comparado byte-a-byte (`diff`) antes de remover o original.
- **Alembic com migration inicial vazia** (`19745c274703_initial.py`) apenas para validar que a cadeia `env.py → Settings.database_url → Base.metadata` importa e gera migrations sem erro. Nenhuma tabela foi criada — não há modelos de domínio nesta Sprint.

---

## 10. Pendências

1. **Verificação real de `docker compose up` + `alembic upgrade head` + health check contra Postgres vivo NÃO foi concluída nesta sessão.**
   - Docker Desktop foi instalado (via `winget install Docker.DockerDesktop`, com autorização do usuário).
   - O backend WSL2 necessário foi instalado (`wsl --install --no-distribution`), mas **exige reinício do Windows** para ativar — reinício não foi executado (encerraria esta sessão e qualquer outro trabalho aberto do usuário).
   - **Ação necessária do usuário:** reiniciar o Windows, depois rodar:
     ```bash
     docker compose up -d
     docker compose ps          # esperar "healthy"
     cd backend
     uv run alembic upgrade head
     uv run pytest              # /health/database deve retornar 200
     ```
   - Só depois disso o critério "PostgreSQL funcionando" da seção 35 estará 100% verificado ao vivo (hoje está verificado apenas por leitura de código + teste do caminho de falha).

2. `GET /api/system/health/full` não tem teste automatizado dedicado (só os outros dois endpoints têm). Baixo risco — reaproveita a mesma função `check_database_connection()` já testada.

Nenhuma outra pendência técnica.

---

## 11. Próxima Sprint

Aguardando autorização explícita para iniciar a **Sprint 2 — Data Engine**, condicionada à resolução da pendência da seção 10 (reinício do Windows + verificação do PostgreSQL ao vivo) — sem isso, o Data Engine não tem onde persistir candles.

---

## Critérios de aceitação (seção 35 da Sprint)

### Git
- [x] Git inicializado
- [x] `.gitignore` criado
- [x] nenhum segredo versionado (verificado: sem `.env`, `.venv`, `node_modules`, `dist` no commit)

### Backend
- [x] FastAPI funcionando (testado via `TestClient` + `uv run uvicorn` — ver nota abaixo)
- [x] configuração centralizada (`Settings`, sem `os.getenv()` espalhado)
- [x] logging funcionando (loguru configurado, testado no startup via lifespan)
- [x] health check funcionando
- [x] database health funcionando (retorna 503 corretamente quando banco está fora)
- [x] CORS configurado (origem única via `settings.frontend_url`, não `*`)

### Banco
- [ ] PostgreSQL funcionando **— pendente de reinício do Windows (seção 10)**
- [x] Docker Compose criado e sintaticamente correto
- [x] healthcheck definido no compose
- [x] SQLAlchemy configurado (engine, session, timeout de conexão)
- [x] Alembic configurado e migration inicial gerada

### Frontend
- [x] React funcionando
- [x] TypeScript funcionando (build `tsc -b` sem erros)
- [x] Vite funcionando (`npm run build` e `npm run test` OK)
- [x] frontend acessando backend (via `systemService` + `useSystemStatus`)
- [x] status da API exibido
- [x] status do banco exibido

### Testes
- [x] testes backend passando (5/5)
- [x] testes frontend passando (1/1)
- [x] projeto inicia sem erros — validado com `uv run uvicorn app.main:app` real (não só `TestClient`): `GET /api/system/health` respondeu 200 e `GET /api/system/health/database` respondeu 503 (correto, sem Postgres no ar), processo encerrado logo em seguida

### Documentação
- [x] README criado
- [x] arquitetura documentada (`docs/architecture.md`)
- [x] instruções de execução
- [x] instruções de testes
