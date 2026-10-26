# Frontend Architecture & Implementation Rules

All frontend code in `frontend/` must strictly observe these standards.

## 1. Directory Structure
```text
frontend/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── app/
    │   ├── router/router.tsx
    │   └── providers/AppProviders.tsx
    ├── core/
    │   ├── api/
    │   │   ├── httpClient.ts
    │   │   └── apiError.ts
    │   ├── query/
    │   │   └── queryClient.ts
    │   ├── navigation/
    │   │   └── menuRegistry.ts
    │   ├── types/
    │   │   ├── apiResponse.types.ts
    │   │   ├── filter.types.ts
    │   │   ├── pagination.types.ts
    │   │   └── baseEntity.types.ts
    │   └── components/
    │       ├── layout/
    │       │   ├── AppLayout.tsx
    │       │   └── SideMenu.tsx
    │       └── filter/
    │           └── FilterBar.tsx
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

## 2. Layering & Invocations
- Every architectural layer is its own folder (even if holding 1 file).
- Call chain is strictly:
  $$\text{Component} \longrightarrow \text{Hook (useQuery/useMutation)} \longrightarrow \text{Module API function} \longrightarrow \text{httpClient (Axios)}$$
- Components **must never** call `httpClient` directly.
- API functions (`<name>.api.ts`) are pure async TypeScript functions containing no React hooks.

## 3. Data Flow & Envelope Unwrapping
- **No Casing Conversion**: The backend API exchanges `camelCase` payloads. Frontend types and models must match exactly; never introduce casing transformation layers.
- **Envelope Model**: `ApiResponse<T> = { statusCode: number; data: T | null; message: string; error: unknown }`.
- **`httpClient`**:
  - Automatically unwraps successful envelopes and returns `data: T`.
  - On non-2xx status or envelope error, throws `ApiError(statusCode, message, error)`.
  - Hooks and components **never** manually inspect `statusCode`.

## 4. TanStack Query Standards
- **Query Keys**: Query keys must **never** be defined inline. Always construct and use a module-level key factory (`<name>QueryKeys.ts`):
  ```typescript
  export const orderKeys = {
    all: ['orders'] as const,
    lists: () => [...orderKeys.all, 'list'] as const,
    list: (filter: OrderSearchFilter) => [...orderKeys.lists(), filter] as const,
    details: () => [...orderKeys.all, 'detail'] as const,
    detail: (id: number) => [...orderKeys.details(), id] as const,
  };
  ```
- **Reads vs Mutations**:
  - Reads use `useQuery`.
  - Creates, Updates, Deletions, and Actions use `useMutation`.
  - Successful mutations must invalidate the associated query keys.
- **Single Source of Truth**: Server data stays in TanStack Query's cache. Never copy API data into redundant state stores.
- Global error toasts and query defaults are configured in `core/query/queryClient.ts`.

## 5. Search, Table & Pagination
- Search operations are queries (reads), so use `useQuery` invoking the backend `POST /api/v1/<resource>/search` endpoint.
- Include the complete filter object in the query key so each filter state and page is cached independently.
- Use `placeholderData: keepPreviousData` to prevent table flickering between page changes.
- **Debounce** text search input. Any filter change (status, date, text) must reset `page` to `0`.
- Use **TanStack Table** with `manualPagination: true`:
  - `pageIndex` maps directly to zero-based API `page`.
  - `pageCount` maps directly to API `totalPages`.
- Reusable `FilterBar.tsx` must be used across all listing screens (search query, status filter defaulting to `ACTIVE`, created date range, Reset). Extra filters are plugged alongside it.

## 6. Forms & Validation
- Build forms with **React Hook Form** + **Zod** (`<name>Form.schema.ts`).
- Server validation error arrays (`[{ field, message }]`) must be mapped directly onto form field errors via `setError`.
- **Secrets & Sensitive Values**: Never display secret tokens or passwords in plain text. Show masked inputs and only transmit secret attributes if altered by the user.

## 7. Routing & Navigation
- Routes managed through **TanStack Router**.
- App shell is `AppLayout.tsx` (top bar, side menu, content viewport).
- Feature modules register menu items (label, route, icon) in `core/navigation/menuRegistry.ts` rather than hardcoding entries inside layout components.

## 8. UI Theme & Visual Design System Integrity (MANDATORY)
All UI pages, views, and components must strictly adhere to the project's established design theme (**Zerodha Kite / Eye-Comfort Pro Trading Dark Palette**):
- **Strict Theme Uniformity**: Never introduce ad-hoc color schemes, random pastel or purple gradients, or mismatched aesthetics that depart from the rest of the application.
- **Design Tokens**: Always utilize standard CSS variables from `index.css`:
  - Backgrounds: `--bg-app` (`#0e1117`), `--bg-card` (`#161b26`), `--bg-panel` (`#121620`), `--bg-card-hover` (`#1c2230`).
  - Borders: `--border-subtle` (`#232b3b`), `--border-medium` (`#2e384d`), `--border-focus` (`#3b82f6`).
  - Trading Highlights: `--bullish-green` (`#00e676`), `--bearish-red` (`#ff5252`), `--warning-amber` (`#ff9800`), `--kite-blue` (`#3b82f6`).
  - Typography: Inter (`var(--font-sans)`) for UI text; JetBrains Mono (`var(--font-mono)`) for all metrics, numbers, timestamps, scores, and ranks.
- **Consistent Layout Hierarchy**:
  - **Page Header**: Page title, total count badge (`#18202e` with border `#283449`), descriptive subtitle, and top-right action buttons (primary button in `#00e676` with black bold text, secondary buttons in `#18202e` with border `#283449`).
  - **Executive Metric Strip**: Use `.dashboard-metrics` and `.dashboard-metric` cards with structured mini-icons and bold mono counters.
  - **Tab Navigation**: Clean segmented trading tabs matching `trading-tabs` with sharp active indicators.
  - **Cards & Grids**: Sharp corners (`border-radius: 8px` to `10px`), subtle `#232b3b` borders, high-contrast typography, and clean status chips (`.status-chip`, `.chip-ok`, `.chip-warn`, `.chip-err`).
  - **Tables**: Use standard table layout with `--bg-table-header` (`#111520`) and sticky headers.
