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
