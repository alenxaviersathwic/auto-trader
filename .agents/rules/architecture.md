# auto-trader: Architecture & System Rules

These rules govern the entire `auto-trader` project and must be strictly followed.

## 1. High-Level Architecture & Stack

| Component | Technology | Constraints |
|---|---|---|
| **Backend** | Python, FastAPI | Single uvicorn worker only. Single-process architecture. |
| **ORM & Migrations** | SQLAlchemy 2 (async), Alembic | All schema changes via Alembic. Async sessions. |
| **Data Validation** | Pydantic v2 | camelCase fields matching DB entity attributes and API payloads. |
| **Database** | PostgreSQL | `snake_case` column names, plural `snake_case` table names. |
| **HTTP Client (Backend)**| `httpx` | Async client for third-party calls. |
| **Encryption** | `cryptography` (AES-GCM) | Master key from environment, never DB. |
| **Scheduler** | APScheduler | Timezone `Asia/Kolkata`. Single in-memory scheduler. |
| **Frontend** | React, Vite, TypeScript | Strict TypeScript mode, ESLint, Prettier. |
| **Server State** | TanStack Query | Query key factories, no state duplication. |
| **Routing** | TanStack Router | File-based / type-safe route tree. |
| **Tables** | TanStack Table | Manual pagination mode matching backend search APIs. |
| **Forms** | React Hook Form + Zod | Field validation with backend error mapping. |
| **HTTP Client (Frontend)**| Axios (`httpClient`) | Automatically unwraps standard envelope. |
| **Frontend Testing** | Vitest + React Testing Library + MSW | Mock Service Worker for API mocking. |

## 2. Repository Layout

```text
auto-trader/
├── arch.md
├── GEMINI.md
├── AGENTS.md
├── .agents/
│   └── rules/
├── backend-service/
└── frontend/
```

- Any AI workflow engine (e.g., LangGraph) must run inside `backend-service` as modular feature components, not as a detached rogue service.
- Never place shared cross-boundary code outside `backend-service/` or `frontend/`. Both services communicate strictly via HTTP API over `/api/v1`.

## 3. Strict Folder & Layering Rules

1. **Every layer is a folder**, even when it contains a single file:
   - Backend: `entity/`, `repository/`, `service/`, `controller/`, `schema/`.
   - Frontend: `types/`, `api/`, `queryKeys/`, `hooks/`, `schemas/`, `components/`, `pages/`.
2. **Layer direction is strictly one-way**:
   $$\text{controller} \longrightarrow \text{service} \longrightarrow \text{repository} \longrightarrow \text{entity}$$
   - A controller **never** calls a repository directly.
   - A service **never** imports another module's repository; it may only import that module's public service.
   - Entities contain **no** business logic.
   - Frontend: `components` $\rightarrow$ `hooks` $\rightarrow$ `api/` $\rightarrow$ `httpClient`. Components never invoke `httpClient` directly.
3. **Module Isolation**:
   - Each feature is encapsulated in `modules/<module_name>/`.
   - Backend modules hook into application lifecycle via the internal event bus (`core/events/`) and scheduler (`core/scheduler/`), never by directly modifying `main.py`.
   - Frontend modules register navigation in `core/navigation/menuRegistry.ts` rather than modifying `AppLayout.tsx`.
