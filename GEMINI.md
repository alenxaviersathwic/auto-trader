# auto-trader Project Rules & Architecture Guidelines

This document outlines the mandatory architecture, conventions, and implementation rules for the **auto-trader** project, derived directly from [arch.md](file:///c:/Users/alenx/Desktop/Development/corevant-open-source/auto-trader/arch.md). All AI agents and developers operating in this repository must strictly adhere to these guidelines.

---

## 1. Locked Architectural Decisions

- **Project Structure**: Composed of `backend-service/` and `frontend/`.
- **Backend Stack**: Python with FastAPI running under **exactly one uvicorn worker** (single process). Schedulers, in-memory state, and future AI workflows (e.g., LangGraph) live in this single process.
- **ORM & Migrations**: SQLAlchemy 2 (async) with Alembic for all schema changes.
- **Database**: PostgreSQL. Plural `snake_case` table names and `snake_case` column names.
- **Base Entity**: Every entity extends `BaseEntity` with `id` (bigint PK), `createdAt` (datetime with timezone), and `status` (smallint).
- **Status Lifecycle & Soft Delete**: Status stored as `1` (Active) or `0` (Deleted). Mapped to `EntityStatus` enum in code. Soft delete everywhere; all queries default to `ACTIVE`. Partial unique indexes (`WHERE status = 1`) on unique constraints.
- **Naming & Casing**:
  - Database: `snake_case`
  - Backend entity attributes & schema fields: `camelCase`
  - API request & response JSON: `camelCase` (no alias generator, no conversion code)
  - Frontend types & state: `camelCase` (matches API directly, no mapping layer)
  - Python files, folders, functions & methods: `snake_case` (PEP 8)
- **Universal API Response Envelope**: Every endpoint returns `{ statusCode, data, message, error }`.
- **Search & Pagination**: Every list endpoint is a `POST /api/v1/<resource>/search` taking a `BaseFilter` body (`page`, `limit`, `sortBy`, `sortDir`, `status`, `query`, `dateFilter`) and returning `PageResult[T]` (`list`, `page`, `limit`, `totalPages`, `totalItems`).
- **Date Filtering**: `DateFilter { from, to }` filters on `createdAt`. Null means no date restriction.
- **Folder Rule**: Every architectural layer is a folder, even when holding a single file.
- **Frontend Stack**: React + Vite + TypeScript, TanStack Query, TanStack Router, TanStack Table (manual pagination), React Hook Form + Zod, and Axios.

---

## 2. Directory Layout & Module Template

```text
auto-trader/
├── arch.md
├── GEMINI.md
├── AGENTS.md
├── .agents/
│   └── rules/
├── backend-service/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config/settings.py
│       │   ├── db/ (base_entity.py, status_type.py, entity_status.py, session.py)
│       │   ├── response/ (api_response.py, response_helper.py)
│       │   ├── filter/ (base_filter.py, date_filter.py, filter_builder.py)
│       │   ├── pagination/page_result.py
│       │   ├── exception/ (app_exceptions.py, exception_handlers.py)
│       │   ├── crypto/secret_cipher.py
│       │   ├── events/event_bus.py
│       │   ├── scheduler/scheduler.py
│       │   └── logging/logger.py
│       └── modules/
│           └── <module_name>/
│               ├── entity/       <name>_entity.py (one file per entity)
│               ├── schema/       <name>_schema.py (request/response/filter)
│               ├── repository/   <name>_repository.py
│               ├── service/      <name>_service.py
│               └── controller/   <name>_controller.py
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── app/
        │   ├── router/router.tsx
        │   └── providers/AppProviders.tsx
        ├── core/
        │   ├── api/ (httpClient.ts, apiError.ts)
        │   ├── query/queryClient.ts
        │   ├── navigation/menuRegistry.ts
        │   ├── types/ (apiResponse.types.ts, filter.types.ts, pagination.types.ts, baseEntity.types.ts)
        │   └── components/ (layout/AppLayout.tsx, layout/SideMenu.tsx, filter/FilterBar.tsx)
        └── modules/
            └── <module_name>/
                ├── types/<name>.types.ts
                ├── api/<name>.api.ts
                ├── queryKeys/<name>QueryKeys.ts
                ├── hooks/use<Name>.ts
                ├── schemas/<name>Form.schema.ts
                ├── components/<Name>*.tsx
                └── pages/<Name>Page.tsx
```

---

## 3. Layering & Invocations

1. **One-Way Backend Hierarchy**:
   $$\text{controller} \longrightarrow \text{service} \longrightarrow \text{repository} \longrightarrow \text{entity}$$
   - Controllers **never** call repositories.
   - Services **never** import another module's repository (only that module's public service).
   - Entities contain **no business logic**.
   - Every backend folder must contain `__init__.py` exporting public members.
   - File suffixes must be explicit: `_entity.py`, `_repository.py`, `_service.py`, `_controller.py`, `_schema.py`.
2. **One-Way Frontend Hierarchy**:
   $$\text{Component} \longrightarrow \text{Hook} \longrightarrow \text{api/ function} \longrightarrow \text{httpClient (Axios)}$$
   - Components never call `httpClient` directly.
   - `api/` functions are pure async functions (no React hooks).

---

## 4. Backend Rules & Database Design

### Base Entity (`core/db/base_entity.py`)
All models extend `BaseEntity`:
- `id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)`
- `createdAt: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True), server_default=func.now())`
- `status: Mapped[EntityStatus] = mapped_column("status", StatusType, nullable=False, default=EntityStatus.ACTIVE)`

### Status Conversion (`status_type.py`)
- Enum `EntityStatus.ACTIVE` (1) and `EntityStatus.DELETED` (0).
- `status_type.py` converts between int (`1`/`0`) in PostgreSQL and enum in Python.
- Code (services, repositories, controllers) only deals with `EntityStatus`. Never use raw `1` or `0`.
- Unknown stored values must raise an error immediately; never default silently.

### Soft Delete & Uniqueness
- Deletion sets `status = EntityStatus.DELETED`. Never issue `DELETE` statements.
- Default query filter: `status == EntityStatus.ACTIVE`.
- Unique constraints must use partial indexes: `CREATE UNIQUE INDEX ... WHERE status = 1;`.

### Exception Handling & Services
- Services raise subclasses of `AppException` (defined in `core/exception/app_exceptions.py`).
- Services never return error dicts or construct HTTP responses.
- `exception_handlers.py` transforms all exceptions into unified `ApiResponse` format.

---

## 5. API Response Envelope & Search Standard

### Universal Envelope (`ApiResponse[T]`)
Every endpoint returns:
```json
{
  "statusCode": 200,
  "data": { ... },
  "message": "Operation completed successfully",
  "error": null
}
```
- `statusCode` strictly matches the HTTP status.
- `data`: Payload on success, `null` on failure.
- `message`: Non-empty human-readable string.
- `error`: `null` on success. On 400 validation: array `[{ field, message }]`. On business conflict (409): code/object. On 500: `null` (never leak internals or stack traces).

### Search & Pagination (`POST /api/v1/<resource>/search`)
- Request body extends `BaseFilter`:
  - `page`: int $\ge 0$ (default `0`, zero-based).
  - `limit`: int between 1 and 100 (default `10`).
  - `sortBy`: string (default `"createdAt"`).
  - `sortDir`: `"asc"` or `"desc"` (default `"desc"`).
  - `status`: `"ACTIVE"` or `"DELETED"` (default `"ACTIVE"`).
  - `query`: optional substring search string.
  - `dateFilter`: optional `DateFilter { from, to }` on `createdAt`.
- Response data is `PageResult[T]` with `list`, `page`, `limit`, `totalPages`, `totalItems`.
- Logic applied centrally in `core/filter/filter_builder.py`.

---

## 6. Frontend Standards

- **No Casing Transformation**: API sends `camelCase`, components consume `camelCase`.
- **Envelope Unwrapping**: `httpClient.ts` automatically unwraps `data` and throws `ApiError(statusCode, message, error)` on failures.
- **TanStack Query**:
  - Always use query key factories (`<name>QueryKeys.ts`). Never write inline key arrays.
  - Reads use `useQuery`, mutations use `useMutation`.
  - Mutations invalidate related query keys upon success.
  - Server state lives in query cache only (no duplication into other stores).
- **List Screens**:
  - Use `useQuery` targeting POST search endpoint. Filter in query key.
  - `placeholderData: keepPreviousData` prevents layout shifts.
  - Search input is debounced. Any filter change resets `page` to `0`.
  - Use TanStack Table in `manualPagination` mode.
  - Reusable `FilterBar.tsx` across all lists.
- **Forms**: React Hook Form + Zod. Backend validation error lists mapped directly to form fields.
- **Navigation**: Modules register navigation links in `core/navigation/menuRegistry.ts`.
- **UI Theme & Visual Integrity (MANDATORY)**: All UI design must strictly observe the Zerodha Kite / Eye-Comfort Pro Trading Dark Palette theme defined in `index.css` (using `--bg-card`, `--border-subtle`, `--bullish-green`, `--bearish-red`, `--font-mono`). Never create mismatched pastel/purple styles or ad-hoc gradients. All screens must match the layout hierarchy of `StrategiesPage.tsx` with standard headers, executive metric strips, and sharp financial trading terminal components.

---

## 7. Cross-Cutting & Security Requirements

- **API Route Prefix**: All routes registered under `/api/v1`.
- **Encryption**: Secrets encrypted with AES-GCM via `core/crypto/secret_cipher.py`. Master key from environment, never database. Secrets never logged or returned over API.
- **Single Process Scheduler**: APScheduler configured with timezone `Asia/Kolkata`.
- **Event Bus**: Feature decoupling using typed event bus in `core/events/`. No circular or internal cross-imports.
