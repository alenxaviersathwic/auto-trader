# Naming, Casing & Coding Standards

All code in `auto-trader` must adhere to the naming, casing, and style rules documented below.

## 1. Naming Conventions

| Layer / Target | Casing Convention | Examples |
|---|---|---|
| **Database Tables** | Plural `snake_case` | `users`, `order_items`, `trade_executions` |
| **Database Columns** | `snake_case` | `user_name`, `created_at`, `status` |
| **Backend Entity Attributes** | `camelCase` | `userName`, `createdAt`, `status` |
| **Backend Schema Fields** | `camelCase` | `userName`, `createdAt`, `orderId` |
| **API Request / Response Payloads** | `camelCase` | `{"userName": "Alen", "createdAt": "..."}` |
| **Frontend Types & Fields** | `camelCase` | `userName: string; createdAt: string;` |
| **Python Files, Folders, Functions** | `snake_case` (PEP 8) | `filter_builder.py`, `calculate_drawdown()` |
| **TypeScript Files (non-components)**| `camelCase` | `httpClient.ts`, `apiError.ts`, `menuRegistry.ts` |
| **React Components & Pages** | `PascalCase` | `FilterBar.tsx`, `AppLayout.tsx`, `OrdersPage.tsx` |
| **React Hooks** | `camelCase` (prefixed with `use`) | `useOrders.ts`, `useDebounce.ts` |

## 2. Backend Casing & Linter Integration
- Entity attributes are `camelCase` in Python code and explicitly mapped to `snake_case` DB columns:
  ```python
  userName: Mapped[str] = mapped_column("user_name", String(100))
  createdAt: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
  ```
- Pydantic schema fields are defined in `camelCase` directly, allowing serialization and deserialization without requiring alias generators or conversion middleware.
- Configure `ruff` / linters to allow `camelCase` attribute names **only** within `entity/` and `schema/` packages. All other Python methods, functions, and variables must remain standard `snake_case`.

## 3. Layer Suffix Rules
Backend files must always end with their architectural layer:
- `<feature>_entity.py`
- `<feature>_repository.py`
- `<feature>_service.py`
- `<feature>_controller.py`
- `<feature>_schema.py`

Frontend files must strictly mirror module conventions:
- `<feature>.types.ts`
- `<feature>.api.ts`
- `<feature>QueryKeys.ts`
- `use<Feature>.ts`
- `<feature>Form.schema.ts`
- `<Feature>*.tsx`
- `<Feature>Page.tsx`

## 4. Documentation & Integrity
- Maintain all existing type hints, comments, and docstrings.
- Ensure strict TypeScript typing (`noImplicitAny`, strict null checks).
- Never disable lint rules globally; any necessary suppression must be localized and justified.
