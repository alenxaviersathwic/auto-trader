# auto-trader — Project Architecture

> **Scope of this document:** architecture only: stack, structure, conventions and shared building blocks for backend-service and frontend.
> Feature details (users, Upstox authentication, market feed, session, suggestion, trader, autopsy and so on) are **not** described here. Each feature gets its own spec in the next schedule and plugs into the module template in section 9.

---

## 1. Stack

| Part | Technology |
|---|---|
| Backend | Python, FastAPI (one uvicorn worker) |
| ORM / migrations | SQLAlchemy 2 (async), Alembic |
| Validation | Pydantic v2 |
| Database | PostgreSQL |
| HTTP client (backend) | httpx |
| Encryption | `cryptography` (AES-GCM) |
| Scheduler | APScheduler, timezone Asia/Kolkata |
| Frontend | React + Vite + TypeScript |
| Server state | TanStack Query |
| Routing | TanStack Router |
| Tables | TanStack Table |
| Forms | React Hook Form + Zod |
| HTTP client (frontend) | Axios |
| Frontend tests | Vitest + React Testing Library (+ MSW for API mocks) |
| Lint / format | ESLint + Prettier |

One uvicorn worker only. Schedulers and in-memory state live in a single process.

---

## 2. Repository layout

```text
auto-trader/
├── arch.md
├── backend-service/
└── frontend/
```

---

## 3. Naming conventions

| Level | Style | Example |
|---|---|---|
| **Database** (tables, columns) | `snake_case` | `user_name`, `created_at`, table `order_items` |
| **Backend code** (entity attributes, schema fields) | `camelCase` | `userName`, `createdAt` |
| **API request and response bodies** | `camelCase` | `userName`, `createdAt` |
| **Frontend** (types, fields) | `camelCase` | same as the API, no mapping layer |

### How it works

- Entity attributes are camelCase in code and map to explicit snake_case column names:

```python
userName: Mapped[str] = mapped_column("user_name", String(100))
createdAt: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
```

- Pydantic schema fields are also camelCase, so request and response bodies are camelCase with **no alias generator and no conversion code**.
- Table names are plural `snake_case`.
- Python files, folders, functions and methods stay `snake_case` (PEP 8). Only data fields (entity attributes and schema fields) are camelCase.
- Configure the linter (ruff) to allow camelCase attribute names inside `entity/` and `schema/` folders only.

---

## 4. Folder rules (apply to backend and frontend)

1. **Every layer is a folder**, even when it holds a single file. Example: `entity/`, `repository/`, `service/`, `controller/`, `schema/`.
2. A module with several entities keeps all of them inside its `entity/` folder, one file per entity.
3. Backend file names carry the layer suffix: `<name>_entity.py`, `<name>_repository.py`, `<name>_service.py`, `<name>_controller.py`, `<name>_schema.py`.
4. Every backend folder has an `__init__.py` that exports its public names.
5. Layer direction is one way:

```text
controller → service → repository → entity
```

- A controller never calls a repository.
- A service never imports another module's repository, only that module's service.
- Entities contain no business logic.

---

## 5. Backend-service structure

```text
backend-service/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── tests/
└── app/
    ├── main.py                          app creation, lifespan
    │
    ├── core/                            shared building blocks, no feature logic
    │   ├── config/
    │   │   └── settings.py              env settings (DB URL, master encryption key)
    │   ├── db/
    │   │   ├── base_entity.py           BaseEntity (id, createdAt, status)
    │   │   ├── status_type.py           int (1/0) <-> EntityStatus converter
    │   │   ├── entity_status.py         EntityStatus enum
    │   │   └── session.py               async engine + session
    │   ├── response/
    │   │   ├── api_response.py          ApiResponse[T] model
    │   │   └── response_helper.py       success(...) / created(...) helpers
    │   ├── filter/
    │   │   ├── base_filter.py           BaseFilter (page, limit, sortBy, sortDir, status, query, dateFilter)
    │   │   ├── date_filter.py           DateFilter (from, to)
    │   │   └── filter_builder.py        applies a BaseFilter to a query (status, dates, text, sort, paging)
    │   ├── pagination/
    │   │   └── page_result.py           PageResult[T] (list, page, limit, totalPages, totalItems)
    │   ├── exception/
    │   │   ├── app_exceptions.py        AppException and subclasses
    │   │   └── exception_handlers.py    converts every error into ApiResponse
    │   ├── crypto/
    │   │   └── secret_cipher.py         AES-GCM encrypt / decrypt
    │   ├── events/
    │   │   └── event_bus.py             typed internal event bus
    │   ├── scheduler/
    │   │   └── scheduler.py             APScheduler instance
    │   └── logging/
    │       └── logger.py
    │
    └── modules/                         one folder per feature, see section 9
```

---

## 6. Base entity

Defined once in `core/db/base_entity.py`. **Every entity in every module extends it.**

| Code (camelCase) | Database column | Type | Notes |
|---|---|---|---|
| `id` | `id` | big integer, primary key | auto-generated |
| `createdAt` | `created_at` | timestamp with time zone | set by the database on insert |
| `status` | `status` | small integer | stored as `1` or `0`, used as `ACTIVE` or `DELETED` in code |

### Status conversion

```text
Database column          Backend code (entity / service)       API response
      1        <───────>        EntityStatus.ACTIVE      ───────>   "ACTIVE"
      0        <───────>        EntityStatus.DELETED     ───────>   "DELETED"
```

- `entity_status.py` defines the enum: `ACTIVE`, `DELETED`.
- `status_type.py` is a SQLAlchemy type decorator. It converts `ACTIVE → 1` and `DELETED → 0` when saving, and the reverse when loading.
- Services and controllers only ever see `EntityStatus`. They never see `1` or `0`.
- API schemas return the enum name as a string.
- An unknown stored value (anything other than 1 or 0) raises an error. It never defaults silently.

### Soft delete

- Deleting sets `status = DELETED`. Rows are not removed.
- Every repository query filters `status = ACTIVE` by default.
- Uniqueness rules use **partial unique indexes** (`WHERE status = 1`), so a deleted row never blocks a new one.

---

## 7. Standard API response

**Every endpoint returns the same envelope**, for success and for failure.

| Field | Type | Rule |
|---|---|---|
| `statusCode` | number | Always present. Equals the HTTP status code. |
| `data` | any, **nullable** | The result on success. `null` on failure. |
| `message` | string | **Always present**, never null or empty. |
| `error` | **dynamic** | `null` on success. On failure it can be a string, an object, or an array. |

### Success

```json
{
  "statusCode": 200,
  "data": { "id": 1, "name": "Sample", "status": "ACTIVE", "createdAt": "2026-10-13T10:30:00Z" },
  "message": "Fetched successfully",
  "error": null
}
```

### Failure examples

Validation (error is an array):

```json
{
  "statusCode": 400,
  "data": null,
  "message": "Validation failed",
  "error": [{ "field": "name", "message": "Name is required" }]
}
```

Business failure (error is an object):

```json
{
  "statusCode": 409,
  "data": null,
  "message": "Resource already exists",
  "error": { "code": "RESOURCE_CONFLICT" }
}
```

### Rules

- `ApiResponse[T]` in `core/response/api_response.py` is the only response model. Controllers return it through `response_helper` (`success(...)`, `created(...)`).
- `exception_handlers.py` turns **every** error into the same envelope: validation errors (400), `AppException` subclasses (404, 409, 502 and so on), and unexpected errors (500).
- A 500 never leaks internals: `message` is generic and `error` is `null`. Details go to the log only.
- `error` never contains secrets, tokens or stack traces.
- `statusCode` in the body always matches the HTTP status of the response.

### Search and pagination (every list endpoint)

Every list is a **POST search API**: `POST /api/v1/<resource>/search`. The request body extends the shared `BaseFilter`. A module adds its own filter fields by extending it (for example `<Name>SearchFilter(BaseFilter)`), and never redefines the base fields.

**BaseFilter** (`core/filter/base_filter.py`)

| Field | Type | Rule |
|---|---|---|
| `page` | number | **Zero-based.** Default `0`, minimum `0`. |
| `limit` | number | Page size. Default `10`, minimum `1`, maximum `100`. |
| `sortBy` | string, optional | One of the endpoint's allowed sort fields (camelCase). Default `createdAt`. |
| `sortDir` | `asc` or `desc`, optional | Default `desc` (newest first). |
| `status` | `ACTIVE` or `DELETED`, optional | **Default `ACTIVE`** when null or missing. |
| `query` | string, optional | Free-text search. Each module declares which fields it searches. Case-insensitive "contains". Null or empty means no text filter. |
| `dateFilter` | `DateFilter`, optional | Filters on `createdAt`. **Null means no date restriction (fetch everything).** |

**DateFilter** (`core/filter/date_filter.py`)

| Field | Type | Rule |
|---|---|---|
| `from` | ISO 8601 date-time, nullable | Inclusive lower bound. Null means no lower bound. |
| `to` | ISO 8601 date-time, nullable | Inclusive upper bound. Null means no upper bound. |

In Python, `from` is a reserved word, so the attribute is `from_` with the JSON alias `from`. The JSON body always uses `from` and `to`.

**Example request**

```json
{
  "page": 0,
  "limit": 10,
  "status": "ACTIVE",
  "query": "sample",
  "dateFilter": { "from": "2026-10-01T00:00:00Z", "to": null }
}
```

**Response:** `data` is a page object. The outer envelope (`statusCode`, `message`, `error`) is unchanged.

```json
{
  "statusCode": 200,
  "data": {
    "list": [],
    "page": 0,
    "limit": 10,
    "totalPages": 10,
    "totalItems": 97
  },
  "message": "Fetched successfully",
  "error": null
}
```

| Field | Meaning |
|---|---|
| `list` | The items on this page. Empty array when there are none, never `null`. |
| `page` | The zero-based page returned. |
| `limit` | The page size used. |
| `totalPages` | `ceil(totalItems / limit)`. `0` when there are no items. |
| `totalItems` | Total rows matching the filter, across all pages. |

**Rules**

- The filter is applied in one place, `core/filter/filter_builder.py`, in this order: status, `createdAt` range, text query, sort, then offset (`page × limit`) and limit. The item query and the total count use the same filter.
- `status` defaults to `ACTIVE`, so soft-deleted rows are returned only when a request asks for `DELETED`.
- `dateFilter` null, or both `from` and `to` null, means no date restriction.
- `from` later than `to` returns `400`.
- A page beyond the last page returns `200` with an empty `list` and the correct `totalPages`, not an error.
- Invalid values (negative page, limit above 100, unknown `sortBy` or `status`) return `400` in the standard envelope with field errors.
- `BaseFilter` and `DateFilter` live in `core/filter/`, and `PageResult[T]` lives in `core/pagination/`. The controller takes the filter as the request body and passes it to the service. The service passes it to the repository, which returns the items plus the total count. The service builds the `PageResult`. No endpoint builds its own paging, status or date logic.

---

## 8. Cross-cutting rules

- **API prefix:** every route is under `/api/v1`.
- **Application lifecycle:** `main.py` uses a FastAPI lifespan. On startup it connects the database, registers event handlers and starts the scheduler. Feature modules hook into startup through the event bus and the scheduler, never by editing `main.py` logic.
- **Events:** modules communicate through the typed event bus in `core/events/`. A module does not import another module's internals.
- **Security:** secrets are encrypted with `core/crypto/secret_cipher.py` (AES-GCM) before saving. The master key comes from the environment, never from the database. Secrets are never logged and never returned by the API.
- **Migrations:** schema changes go through Alembic only.
- **Errors:** services raise `AppException` subclasses. They never return error values and never build responses.

---

## 9. Module template

Every feature is a folder under `modules/` and follows the same shape. Feature-specific subfolders (for example an external client or a scheduler job) are defined in that feature's own spec, and they follow the folder rule too.

### Backend

```text
modules/
└── <module_name>/
    ├── entity/          <name>_entity.py, one file per entity (extends BaseEntity)
    ├── schema/          <name>_schema.py, request and response models, plus the module's search filter (extends BaseFilter)
    ├── repository/      <name>_repository.py
    ├── service/         <name>_service.py
    └── controller/      <name>_controller.py
```

### Frontend

```text
modules/
└── <module_name>/
    ├── types/           <name>.types.ts
    ├── api/             <name>.api.ts, plain request functions, no React
    ├── queryKeys/       <name>QueryKeys.ts, key factory
    ├── hooks/           use<Name>.ts (useQuery / useMutation)
    ├── schemas/         <name>Form.schema.ts, Zod schemas
    ├── components/      <Name>*.tsx
    └── pages/           <Name>Page.tsx
```

---

## 10. Frontend structure

```text
frontend/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── app/
    │   ├── router/
    │   │   └── router.tsx                 TanStack Router route tree
    │   └── providers/
    │       └── AppProviders.tsx           QueryClientProvider, RouterProvider
    │
    ├── core/
    │   ├── api/
    │   │   ├── httpClient.ts              Axios instance, envelope unwrapping
    │   │   └── apiError.ts                ApiError (statusCode, message, error)
    │   ├── query/
    │   │   └── queryClient.ts             QueryClient defaults + global error handling
    │   ├── navigation/
    │   │   └── menuRegistry.ts            menu items registered by each module
    │   ├── types/
    │   │   ├── apiResponse.types.ts       ApiResponse<T>
    │   │   ├── filter.types.ts            BaseFilter, DateFilter
    │   │   ├── pagination.types.ts        PageResult<T>
    │   │   └── baseEntity.types.ts        BaseEntity, EntityStatus ('ACTIVE' | 'DELETED')
    │   └── components/
    │       ├── layout/
    │       │   ├── AppLayout.tsx              sidebar menu + top bar + content area
    │       │   └── SideMenu.tsx               renders items from the menu registry
    │       └── filter/
    │           └── FilterBar.tsx              search text, status, date range (reused by every list)
    │
    └── modules/                           one folder per feature, see section 9
```

### Frontend standards

1. **Same folder rule as the backend:** every layer is a folder, even with one file. Each module mirrors the backend module name.
2. **No casing conversion.** The API is camelCase, so types and fields are used as received.
3. **One envelope type.** `ApiResponse<T> = { statusCode: number; data: T | null; message: string; error: unknown }`.
4. **`httpClient` (Axios)** unwraps the envelope. It returns `data` on success and throws `ApiError(statusCode, message, error)` on any failure, so hooks never inspect `statusCode` themselves.
5. **Layering:** components use hooks, hooks use the `api/` functions, `api/` functions use `httpClient`. Components never call `httpClient` directly.
6. **TanStack Query**
   - Query keys come from a per-module key factory, never from inline arrays.
   - Reads use `useQuery`. Create, update, delete and action calls use `useMutation`.
   - Mutations invalidate the related keys on success.
   - Global defaults (stale time, retry rules) and a global error handler that shows `ApiError.message` live in `core/query/queryClient.ts`.
   - Server data stays in the query cache. It is not copied into other state stores.
7. **TanStack Router** for routes, **TanStack Table** for tables.
8. **Forms** use React Hook Form with a Zod schema. Server validation errors (`error` array) are mapped back onto form fields.
9. **Secrets** are never shown. Edit forms show masked values and send a secret field only when the user changes it.
10. **Strict TypeScript**, ESLint and Prettier.
11. **Search and pagination**
    - Types: `DateFilter = { from: string | null; to: string | null }`, `BaseFilter = { page: number; limit: number; sortBy?: string; sortDir?: 'asc' | 'desc'; status?: 'ACTIVE' | 'DELETED'; query?: string; dateFilter?: DateFilter | null }` (page is zero-based), and `PageResult<T> = { list: T[]; page: number; limit: number; totalPages: number; totalItems: number }`. A module's filter type extends `BaseFilter`.
    - A search is a read, so it uses `useQuery` with a `queryFn` that calls the POST search endpoint. The full filter object is part of the query key, so every filter and page combination is cached separately.
    - Page changes use `placeholderData: keepPreviousData`, so the table does not flash empty between pages.
    - The text search box is debounced. Changing any filter resets `page` to `0`.
    - TanStack Table runs in `manualPagination` mode. `pageIndex` maps directly to the API `page`, and `pageCount` is `totalPages`.
    - Every list screen uses the shared `FilterBar` (search text, status select defaulting to Active, created-from and created-to dates, Reset). An empty date means `null`, which fetches everything. A module adds its own extra filter controls beside it.
12. **Navigation**
    - The app shell is `AppLayout`: a side menu, a top bar and a content area.
    - Menu items are not hardcoded in the shell. Each module registers its own item (label, icon, route) in `core/navigation/menuRegistry.ts`, so adding a feature adds a menu entry without editing the shell.
    - Pages with several sections (for example Settings) use a section list beside the content, and each section is its own route.

---

## 11. Decisions locked in this document

- Project name is **auto-trader**, with `backend-service/` and `frontend/`.
- Backend is FastAPI. AI workflow code (LangGraph) will run inside the same app as later feature modules.
- All entities extend `BaseEntity` with `id`, `createdAt` and `status`.
- Status is stored as `1`/`0` and converted to `ACTIVE`/`DELETED` in the backend.
- Database uses `snake_case`. Backend code fields and API bodies use `camelCase`.
- Every endpoint returns `{ statusCode, data (nullable), message (always a string), error (dynamic) }`.
- Every list is a `POST /<resource>/search` that takes a `BaseFilter` body (`page`, `limit`, `sortBy`, `sortDir`, `status` defaulting to `ACTIVE`, `query`, `dateFilter`) and returns `data: { list, page, limit, totalPages, totalItems }`.
- `DateFilter { from, to }` filters on `createdAt`. Null means no date restriction.
- Soft delete everywhere, with partial unique indexes.
- Every layer is a folder, even for a single file.
- Frontend uses TanStack Query, Router and Table, React Hook Form with Zod, and Axios.
- Feature details are specified separately, one feature at a time.

---

## 12. Research Engine Module Architecture & Flow

### Overview & Core Philosophy
The Research Engine performs deterministic market intelligence, news sentiment clearance, catalyst categorization, synthesized blog generation, and thesis evaluation for Indian market trading underlyings across two distinct scopes: **Indices** and **Commodities**.

Rather than bloating database storage with thousands of transient vector chunks and document rows, the module operates with an **in-memory extraction pipeline** and a **single upserted entity** (`ResearchEntity`), maintaining fresh, actionable evaluation data and structured news categories in PostgreSQL.

---

### Backend Architecture

#### 1. Single Primary Entity (`modules/research/entity/research_entity.py`)
- Maps to table `research_candidates` and extends `BaseEntity`.
- Key fields:
  - `scope` (stored as `underlying_type`): `"INDEX"` | `"COMMODITY"`
  - `item` (stored as `underlying_code`, unique per item): e.g. `"NIFTY"`, `"BANKNIFTY"`, `"SENSEX"`, `"CRUDEOIL"`, `"GOLD"`, `"SILVER"`
  - `latestScore` (stored as `score`): numeric ranking score (0 to 100)
  - `status` (stored as `news_status`): `"CLEAR_POSITIVE"`, `"BEARISH_WATCH"`, `"MIXED"`, `"HAS_NEGATIVE"`, `"NO_COVERAGE"`
  - `suggested`: boolean clearance flag
  - `direction`: `"BULLISH"` | `"BEARISH"` | `null`
  - `thesis`: 1-2 sentence clearance or risk rationale
  - `supportingPoints`: JSONB array of verified bullish drivers
  - `watchItems`: JSONB array of risk monitoring items
  - `latestNews`: JSONB array of today's latest scraped news articles (`title`, `url`, `source`, `snippet`, `publishedAt`)
  - `affectNews`: JSONB array of market-moving catalyst news items with extracted catalyst type (e.g. `EARNINGS`, `MACRO_POLICY`, `SUPPLY_DEMAND`, `INFLATION_RATES`, `GEOPOLITICAL`) and direction (`BULLISH` / `BEARISH`)
  - `neutralNews`: JSONB array of neutral market commentary and sector wrap-ups
  - `blogSummary`: Synthesized daily financial intelligence blog briefing providing narrative market pulse, drivers, and publisher citations
  - `briefEmbedding`: `vector(768)` indexed with HNSW cosine distance (`idx_research_candidates_brief_embedding`), selectively populated for top-ranked underlyings
- **In-Place Upsert**: When the pipeline finishes, it checks if `underlying_code` already exists in PostgreSQL. If it exists, it **updates that existing record in-place with latest scores, news categories, blog summary, and vector embeddings** rather than inserting duplicate candidate rows.

#### 2. Selective Vector Memory Storage (Top 5 Indices & Top 3 Commodities)
- For every research run, candidates are ranked by score within their respective underlying types:
  - **Top 5 Index items** (e.g. `NIFTY`, `SENSEX`, `BANKNIFTY`, `FINNIFTY`, `MIDCPNIFTY`)
  - **Top 3 Commodity items** (e.g. `GOLD`, `CRUDEOIL`, `NATURALGAS`)
- The pipeline generates a 768-dimensional dense vector embedding from the instrument's `blogSummary` and `thesis`, and stores it into `brief_embedding vector(768)`. All other underlyings receive `NULL`.
- **Architectural Constraint (No Vector Retrieval Flow)**: Per design, vector memory retrieval endpoints and query loops are explicitly **not implemented**. Vector embeddings are write-only / reserved for persistence and ranking without retrieval runtime overhead.

#### 3. Consolidated Controller (1 Path Per Function)
All endpoints live in [`research_controller.py`](file:///Users/user/Documents/Tests/auto-trader/backend-service/app/modules/research/controller/research_controller.py) under prefix `/api/v1`:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/research/run` | Triggers the pipeline across in-scope underlyings. No parameter IDs required. |
| `GET` | `/research/run-status` | Lightweight status polling. Returns strictly `isRunning`, `state`, `progressPct`, `currentNode`, `startedAt`, `finishedAt`. |
| `POST` | `/research/cancel` | Cancels any currently executing research run. |
| `POST` | `/research/search` | Search & pagination taking `BaseFilter` (`page`, `limit`, etc.). Returns candidate entities sorted by `score` descending (`nulls_last`). |
| `GET` | `/research/candidates/{id}` | Retrieves full candidate clearance thesis, blog summary, categorized news (`latestNews`, `affectNews`, `neutralNews`), supporting points, and verified quotes. |
| `GET` | `/research/results/latest` | Returns latest evaluated candidates grouped by underlying type. |

#### 4. Pipeline Execution Nodes
1. **Load Context**: Loads built-in underlyings (`INDEX`: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX, BANKEX; `COMMODITY`: CRUDEOIL, NATURALGAS, GOLD, SILVER, COPPER, ZINC), active RSS feeds, and risk terms into state memory.
2. **Search & Fetch**: Concurrently fetches fresh financial RSS feeds and plain-text market intelligence.
3. **Clean & Dedupe**: Deduplicates articles in memory by URL and content hash within the freshness window.
4. **Embed Chunks**: Splits article text into token chunks and computes embeddings in memory.
5. **Extract Claims**: Uses alias matching and heuristic assertion extraction in memory.
6. **Verify Claims & Negative Sweep**: Cross-references assertions against source texts and detects risk catalysts in memory.
7. **Score & Rank**: Computes scores and clearance status (`CLEAR_POSITIVE`, `BEARISH_WATCH`, etc.).
8. **Write Briefs & Intelligence Categorization**:
   - Categorizes matching articles into `latestNews`, `affectNews` (catalysts & impact), and `neutralNews`.
   - Synthesizes `blogSummary` (Daily Intelligence Briefing with Market Pulse, Drivers, and Publisher citations).
9. **Persist & Vector Indexing**:
   - Identifies top 5 indices and top 3 commodities by score.
   - Computes 768-d vector embeddings for top 5 index and top 3 commodity items; stores them into `brief_embedding`.
   - Upserts the evaluated results, news categories, and blog summary directly into `ResearchEntity` in PostgreSQL.

---

### Frontend Architecture (`frontend/src/modules/research/`)

- **Page**: Single dedicated screen at `/research` ([`ResearchEnginePage.tsx`](file:///Users/user/Documents/Tests/auto-trader/frontend/src/modules/research/pages/ResearchEnginePage.tsx)).
- **Theme**: Strict adherence to the Zerodha Kite / Eye-Comfort Pro Trading Dark Palette (`--bg-card: #161b26`, `--bg-app: #0e1117`, subtle borders `#232d3f`, JetBrains Mono typography).
- **Header**: Clean, minimalist trading terminal header:
  - Title: **"Research Engine"** with live progress tag during execution.
  - Action: **"Run Research Engine"** button with loading spinner when active.
  - **No Redundant Metric Cards**: Top metric strips are omitted to preserve vertical space and focus immediately on trading instruments.
- **Two Tabs**: Exactly 2 tabs: **Index** and **Commodity**:
  - The client issues a single query to `POST /api/v1/research/search` (which returns evaluated underlyings sorted by score).
  - The UI filters locally by `scope === "INDEX"` or `scope === "COMMODITY"`.
- **Candidate Trading Cards**: Each underlying is rendered in a compact dark-palette card showing:
  - Name and symbol (e.g. `BSE SENSEX`, `NIFTY 50`, `GOLD`, `CRUDE OIL`)
  - Scope badge (`INDEX` or `COMMODITY`)
  - Status badge:
    - `CLEARED FOR TRADE` (emerald green)
    - `BEARISH WATCH` (rose red)
    - `MIXED SENTIMENT` (amber)
    - `LOW COVERAGE` (muted slate)
  - Numeric score, source count, and sentiment ratio (`+bullish / -bearish`)
  - 1-line clearance reason
- **Detail Drawer (`CandidateDrawer.tsx`)**:
  - Clicking any card opens a side drawer displaying:
    - **Vector Memory Pill**: Displayed in header for instruments indexed in pgvector (top 5 index / top 3 commodity).
    - **Daily Intelligence Blog Summary**: Cleanly styled market narrative section.
    - **Clearance Thesis & Metrics Strip**: Final score, bullish/bearish weights, negative share.
    - **Categorized News Tabs**:
      - **Market Affecting**: Catalysts tagged with direction (`BULLISH`/`BEARISH`), catalyst category, domain, and snippet.
      - **Today's Latest**: Chronological fresh news items with time badges and direct external publisher links.
      - **Neutral Commentary**: Market wrap-ups and digests.
    - **Verified Source Quotes & Drivers**: Supporting bullish points and risk watch signals with verified quotations.

---

## 13. MCP Architecture & AI Master Research Connection

### Overview
Auto-Trader employs the Model Context Protocol (MCP) to decouple LLM copilots from raw database mutations and feature internals. The **Research Engine** exposes an open MCP server interface that connects directly into **AI Master**, enabling AI Master to inspect live market intelligence, query scraped news categories, read synthesized blog briefings, and control research runs with audited governance.

### Research Engine MCP Server (`/mcp/research`)
- **Prefix**: `/mcp/research`
- **Class**: `ResearchMcpServer` (`modules/research/mcp/research_mcp_server.py`)
- **Standard Endpoints**:
  - `GET /mcp/research/tools`: Returns the catalog of 10 available research tools and their JSON schemas.
  - `POST /mcp/research/call`: Standardized MCP JSON-RPC call handler (`{ "tool": tool_name, "arguments": args }`).
  - Individual REST compatibility routes: `POST /mcp/research/tools/{tool_name}`.
- **Tool Catalog (`RESEARCH_MCP_TOOLS`)**:

| Tool Name | Tier | Description |
|---|---|---|
| `get_latest_results` | `READ` | Returns latest evaluated research candidates (scores, clearance status, bullish/bearish weights) for `INDEX` or `COMMODITY`. |
| `get_candidate` | `READ` | Detailed intelligence for an instrument (`SENSEX`, `NIFTY`, `GOLD`, etc.), including blog summary, market-affecting news, latest news, and vector memory status. |
| `search_claims` | `READ` | Searches verified source quotes and driver claims filtered by stance (`BULLISH` or `BEARISH`). |
| `list_underlyings` | `READ` | Lists all supported underlyings across Indices and Commodities with evaluation scores. |
| `semantic_search` | `READ` | Searches candidate theses and intelligence summaries. |
| `get_run_status` | `READ` | Returns progress and state of the latest or specific research run. |
| `search_runs` | `READ` | Searches historical research runs with state filtering. |
| `list_sources` | `READ` | Lists monitored market publishers and RSS feeds. |
| `run_research` | `OPERATE` | Triggers a fresh pipeline run across scopes. Gated by HMAC confirmation token. |
| `cancel_research_run` | `OPERATE` | Cancels an active pipeline run. Gated by HMAC confirmation token. |

### AI Master Connection & Governance
1. **Server Registry (`modules/master/mcp/server_registry.py`)**:
   - Automatically registers the `research-engine` server in the `master_tool_servers` table (`url="/mcp/research"`, `transport="HTTP"`, `tierCap="OPERATE"`).
   - Seeds tool policies in `master_tool_policies` with auto-approval for `READ` tools and confirmation tokens for `OPERATE` tools.
2. **Tool Gateway (`modules/master/service/tool_gateway.py`)**:
   - Dynamically resolves tool policies across registered MCP servers.
   - Enforces tier caps (`READ`, `ANALYZE`, `PROPOSE`, `OPERATE`).
   - Audits every research tool invocation in `master_tool_calls` table with execution duration and result summaries.
3. **McpClient (`modules/master/mcp/mcp_client.py`)**:
   - Supports **in-process direct dispatch** (`research_mcp_instance.execute_tool`) for sub-millisecond execution and shared database sessions.
   - Supports HTTP transport fallback for external MCP servers.
4. **LangGraph Agent Nodes (`modules/master/graph/nodes/master_nodes.py`)**:
   - Classifies research queries (`RESEARCH` intent) using fast heuristics and LLM intent classification.
   - Automatically invokes `get_candidate` or `get_latest_results` via `ToolGateway`.
   - Streams formatted intelligence responses to user conversations with status badges, blog summaries, and catalyst news.



