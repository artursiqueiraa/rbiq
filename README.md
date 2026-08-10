# IQO Strategy Lab

Laboratório de pesquisa e análise quantitativa para estudo de estratégias de mercado com dados históricos e em tempo real — backtest e paper trading, sem execução de operações reais.

A especificação completa do projeto está em [docs/architecture.md](docs/architecture.md).

## Arquitetura

```text
Data Provider → Data Normalizer → Market Database → Indicators → Market Structure
→ Market Regime → Strategy Engine → Signal Engine → Backtest / Paper Trading
→ Performance → Dashboard
```

Nesta Sprint (Infraestrutura Base) apenas os blocos abaixo existem:

```text
Backend FastAPI ── Frontend React ── PostgreSQL (Docker) ── Git + Testes
```

Data Engine, indicadores, estratégias, backtest, paper trading e dashboard completo entram nas Sprints seguintes.

## Requisitos

| Ferramenta | Versão mínima |
|---|---|
| Python | 3.12+ |
| [uv](https://docs.astral.sh/uv/) | qualquer versão recente |
| Node.js | 20+ |
| npm | 10+ |
| Docker Desktop (com WSL2 no Windows) | qualquer versão recente |
| Git | qualquer versão recente |

Execute `scripts/check-dev.ps1` no PowerShell para verificar se tudo está instalado.

## Instalação

```bash
git clone <repo-url>
cd iqo-strategy-lab
cp .env.example .env
```

Ajuste `.env` se necessário (os valores padrão já funcionam com o `docker-compose.yml`).

## 1. Iniciar o PostgreSQL

```bash
docker compose up -d
docker compose ps
```

O serviço `postgres` deve aparecer como `healthy`.

## 2. Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

A aplicação sobe em `http://localhost:5173` e consulta o backend automaticamente.

## Executar testes

```bash
# backend
cd backend
uv run pytest

# frontend
cd frontend
npm run test
```

## Endpoints disponíveis (Sprint 1)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/system/health` | Status geral da API |
| GET | `/api/system/health/database` | Testa a conexão real com o PostgreSQL |
| GET | `/api/system/health/full` | Status combinado (API + banco) |

## Portas

| Serviço | Porta |
|---|---|
| Backend | 8000 |
| Frontend | 5173 |
| PostgreSQL | 5432 |

## Estrutura de pastas

```text
iqo-strategy-lab/
├── backend/          # FastAPI, SQLAlchemy, Alembic
├── frontend/         # React + TypeScript + Vite
├── data/             # raw / normalized / exports (dados locais, não versionados)
├── docs/             # arquitetura e relatórios de sprint
├── scripts/          # scripts auxiliares (ex.: check-dev.ps1)
├── docker-compose.yml
└── .env.example
```

## Estado do projeto

Ver [docs/sprints/SPRINT_1_REPORT.md](docs/sprints/SPRINT_1_REPORT.md) para o relatório da Sprint atual e [SPRINT_0_AUDIT_REPORT.md](SPRINT_0_AUDIT_REPORT.md) para a auditoria inicial (projeto greenfield).
