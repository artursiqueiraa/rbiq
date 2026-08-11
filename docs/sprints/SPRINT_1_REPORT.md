# SPRINT 1 — Relatório
## Infraestrutura Base — IQO Strategy Lab

**Data:** 2026-08-10 (infraestrutura) / 2026-08-11 (verificação final pós-reinício)
**Status:** Concluída. Todos os critérios de aceitação verificados, incluindo PostgreSQL real (seção 10).

---

## 1. Resumo

A infraestrutura base do projeto foi criada do zero: backend FastAPI com configuração centralizada, logging estruturado, SQLAlchemy 2.x + Alembic, uma abstração `DataProvider` (sem integração real), frontend React + TypeScript + Vite consumindo a API para mostrar status ao vivo, Docker Compose para PostgreSQL, testes automatizados nos dois lados, `.gitignore`/`.env.example` corretos, README completo e commits Git.

Nenhum item das seções 34 ("não implementar nesta Sprint") foi tocado: sem IQ Option, sem sinais, sem estratégias, sem indicadores, sem backtest, sem paper trading, sem dashboard além da página de status.

**Atualização de 2026-08-11:** após o usuário reiniciar o Windows (para ativar o WSL2 exigido pelo Docker Desktop) e logar no Docker, a verificação completa foi concluída: `docker compose up -d` subiu o PostgreSQL real (`healthy`), `alembic upgrade head` aplicou a migration inicial contra o banco, e os três endpoints de health (`/health`, `/health/database`, `/health/full`) responderam 200 com o banco de verdade no ar. Backend e frontend também foram subidos lado a lado e o CORS entre eles foi confirmado. Não há mais pendências desta Sprint.

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
| GET | `/api/system/health` | Sim (pytest + curl real) | 200, `{"status":"healthy","service":"iqo-strategy-lab","version":"0.1.0"}` |
| GET | `/api/system/health/database` | Sim (pytest + curl real, com e sem Postgres no ar) | 503 sem banco / **200 `{"status":"healthy","database":"postgresql"}` com Postgres real rodando** |
| GET | `/api/system/health/full` | Verificado manualmente via curl contra o servidor real (sem teste pytest dedicado) | 200, `{"status":"healthy","api":"healthy","database":"healthy"}` com Postgres no ar |

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
| 4 | `Settings.model_config.env_file=".env"` era resolvido relativo ao diretório de execução (`backend/`), não à raiz do projeto onde `.env.example`/README instruem criar o `.env`. Rodar `uv run uvicorn` de dentro de `backend/` não encontraria um `.env` na raiz. Descoberto durante a verificação real pós-reinício. | `app/core/config.py` agora resolve `_PROJECT_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"` — um único `.env` na raiz funciona independente de onde o comando é executado. |

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

**Resolvida em 2026-08-11.** O usuário reiniciou o Windows e autenticou no Docker Desktop. Sequência completa executada e verificada nesta máquina:

```text
docker compose up -d          → Postgres 16-alpine baixado e iniciado
docker compose ps             → iqolab-postgres: healthy
uv run alembic upgrade head   → aplicou 19745c274703_initial contra o banco real
uv run pytest                 → 5 passed in 1.33s (contra Postgres real)
uv run uvicorn ...            → GET /health = 200, /health/database = 200 (healthy),
                                 /health/full = 200
curl OPTIONS (CORS preflight) → access-control-allow-origin: http://localhost:5173
npm run dev                   → frontend serve HTTP 200 em http://localhost:5173
```

Todos os processos de verificação (`uvicorn`, `vite`) foram encerrados ao final; nenhum ficou rodando em segundo plano.

Restam apenas dois itens de baixo risco, sem bloquear a conclusão da Sprint:

1. `GET /api/system/health/full` não tem teste `pytest` dedicado (só verificação manual via curl). Reaproveita a mesma função `check_database_connection()` já coberta pelos outros testes.
2. A renderização do frontend no navegador (React efetivamente mostrando "conectado"/"conectado" na tela) não foi verificada visualmente nesta sessão não-interativa — apenas via teste automatizado (`App.test.tsx`, que mocka o fetch) e via verificação de que o HTML/JS é servido e os endpoints que o hook consome respondem corretamente. Recomenda-se uma checagem visual rápida no navegador antes da Sprint 2.

---

## 11. Próxima Sprint

Todos os bloqueadores foram resolvidos. Aguardando autorização explícita do usuário para iniciar a **Sprint 2 — Data Engine**.

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
- [x] PostgreSQL funcionando — verificado ao vivo em 2026-08-11 (`docker compose ps` → healthy; `/health/database` → 200)
- [x] Docker Compose criado e sintaticamente correto
- [x] healthcheck definido no compose (confirmado `healthy` na prática)
- [x] SQLAlchemy configurado (engine, session, timeout de conexão)
- [x] Alembic configurado e migration inicial aplicada contra o banco real (`alembic upgrade head`)

### Frontend
- [x] React funcionando
- [x] TypeScript funcionando (build `tsc -b` sem erros)
- [x] Vite funcionando (`npm run build` e `npm run test` OK)
- [x] frontend acessando backend (via `systemService` + `useSystemStatus`); CORS confirmado ao vivo entre `localhost:5173` e `localhost:8000`
- [x] status da API exibido (lógica testada; checagem visual no navegador ainda recomendada — ver seção 10)
- [x] status do banco exibido (lógica testada; checagem visual no navegador ainda recomendada — ver seção 10)

### Testes
- [x] testes backend passando (5/5)
- [x] testes frontend passando (1/1)
- [x] projeto inicia sem erros — validado com `uv run uvicorn app.main:app` real (não só `TestClient`): `GET /api/system/health` respondeu 200 e `GET /api/system/health/database` respondeu 503 (correto, sem Postgres no ar), processo encerrado logo em seguida

### Documentação
- [x] README criado
- [x] arquitetura documentada (`docs/architecture.md`)
- [x] instruções de execução
- [x] instruções de testes
