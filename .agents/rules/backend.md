# Backend Architecture & Implementation Rules

All backend code under `backend-service/` must adhere to these rules.

## 1. Process & Runtime Model
- **Worker Concurrency**: Exactly **one uvicorn worker**.
- Schedulers (APScheduler, timezone: `Asia/Kolkata`) and in-memory state reside within a single process.
- **Application Lifespan**: `main.py` uses FastAPI lifespan. On startup, it connects database sessions, registers event handlers, and starts the scheduler. Feature modules hook via `core/events/` and `core/scheduler/`, never by adding hardcoded module logic into `main.py`.

## 2. Directory Layout & Module Structure
```text
backend-service/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── tests/
└── app/
    ├── main.py
    ├── core/
    │   ├── config/settings.py
    │   ├── db/
    │   │   ├── base_entity.py
    │   │   ├── status_type.py
    │   │   ├── entity_status.py
    │   │   └── session.py
    │   ├── response/
    │   │   ├── api_response.py
    │   │   └── response_helper.py
    │   ├── filter/
    │   │   ├── base_filter.py
    │   │   ├── date_filter.py
    │   │   └── filter_builder.py
    │   ├── pagination/page_result.py
    │   ├── exception/
    │   │   ├── app_exceptions.py
    │   │   └── exception_handlers.py
    │   ├── crypto/secret_cipher.py
    │   ├── events/event_bus.py
    │   ├── scheduler/scheduler.py
    │   └── logging/logger.py
    └── modules/
        └── <module_name>/
            ├── entity/
            │   ├── __init__.py
            │   └── <name>_entity.py
            ├── schema/
            │   ├── __init__.py
            │   └── <name>_schema.py
            ├── repository/
            │   ├── __init__.py
            │   └── <name>_repository.py
            ├── service/
            │   ├── __init__.py
            │   └── <name>_service.py
            └── controller/
                ├── __init__.py
                └── <name>_controller.py
```

## 3. Strict Suffix & Layer Export Rules
- Every folder **must** have an `__init__.py` exporting public members.
- File names strictly follow layer suffixes:
  - `<name>_entity.py`
  - `<name>_repository.py`
  - `<name>_service.py`
  - `<name>_controller.py`
  - `<name>_schema.py`
- Strict dependency hierarchy:
  $$\text{controller} \longrightarrow \text{service} \longrightarrow \text{repository} \longrightarrow \text{entity}$$
- Controllers **never** access repositories.
- Services **never** import another module's repository; use the foreign module's public service instead.
- Entities are pure persistence mappings with **no business logic**.

## 4. BaseEntity & Status Lifecycle
- **BaseEntity**: Defined in `core/db/base_entity.py`. Every entity in every module **must** inherit from `BaseEntity`.
  - `id`: BigInteger primary key (auto-generated).
  - `createdAt`: `DateTime(timezone=True)`, populated by DB on insert (`server_default=func.now()`).
  - `status`: Stored as smallint (`1` or `0`), mapped to `EntityStatus` via `status_type.py`.
- **Status Conversion**:
  - Enum: `EntityStatus.ACTIVE` and `EntityStatus.DELETED` in `core/db/entity_status.py`.
  - TypeDecorator (`status_type.py`): Converts `ACTIVE <-> 1` and `DELETED <-> 0`.
  - Code (entities, repositories, services, controllers) only deals with `EntityStatus`. Never reference raw integers `1` or `0`.
  - Unknown stored integer raises a `ValueError`/exception; it must **never** default silently.
- **Soft Delete**:
  - Deletion sets `entity.status = EntityStatus.DELETED`. Records are never physically deleted (`DELETE` SQL statements are forbidden).
  - All repository select queries **must filter `status == EntityStatus.ACTIVE` by default**.
  - Uniqueness constraints must be implemented as **partial unique indexes** in PostgreSQL (`WHERE status = 1`), so soft-deleted rows never block re-creation.

## 5. Error Handling & Exceptions
- Services must raise subclasses of `AppException` (defined in `core/exception/app_exceptions.py`).
- Services **must never** return error tuples/dicts, and must **never** assemble HTTP response objects directly.
- `exception_handlers.py` catches all exceptions and converts them into the unified `ApiResponse` format.

## 6. Migrations & Database Changes
- All schema alterations must be scripted via **Alembic** (`alembic/versions/`).
- Tables must use plural `snake_case` names (e.g., `order_items`, `users`).
- Column definitions in SQLAlchemy must explicitly specify the `snake_case` DB column name while using `camelCase` Python attribute names:
  ```python
  userName: Mapped[str] = mapped_column("user_name", String(100))
  createdAt: Mapped[datetime] = mapped_column("created_at", DateTime(timezone=True))
  ```

## 7. Security & Secrets
- Sensitive credentials (tokens, API secrets) must be encrypted using `core/crypto/secret_cipher.py` (AES-GCM).
- Master encryption key is read from environment settings, never stored in the database.
- Secrets must never be logged or serialized in API responses.
