# API & Pagination Standards

All REST endpoints in `auto-trader` must conform strictly to these specifications.

## 1. Route Prefix
- Every endpoint route must be nested under `/api/v1`.
- Example: `/api/v1/orders/search`, `/api/v1/orders/{id}`.

## 2. Universal API Envelope
Every single response (success, client error, business exception, or server error) **must** use the identical outer envelope model (`ApiResponse[T]`):

```json
{
  "statusCode": 200,
  "data": { ... },
  "message": "Fetched successfully",
  "error": null
}
```

### Envelope Contract
| Field | Type | Description / Constraints |
|---|---|---|
| `statusCode` | integer | **Mandatory**. Must strictly equal the HTTP status code. |
| `data` | `T` or `null` | The payload on success. **Must be `null` on failure**. |
| `message` | string | **Mandatory**. Concise, human-readable summary. Never null or empty string. |
| `error` | dynamic (`null` \| string \| object \| array) | `null` on success. On failure, details of the error. |

### Failure Envelope Formats
- **Validation Failure (400)**: `error` is an array of field errors:
  ```json
  {
    "statusCode": 400,
    "data": null,
    "message": "Validation failed",
    "error": [{ "field": "name", "message": "Name is required" }]
  }
  ```
- **Business Logic Conflict (409)**: `error` is a structured error object or string:
  ```json
  {
    "statusCode": 409,
    "data": null,
    "message": "Resource already exists",
    "error": { "code": "RESOURCE_CONFLICT" }
  }
  ```
- **Internal Server Error (500)**:
  - `message`: Generic error message (e.g., `"Internal server error"`).
  - `error`: **Must be `null`**. Never leak stack traces, internal paths, SQL queries, or tokens. Log details internally only.

## 3. Controllers & Helpers
- Controllers must return responses through `core/response/response_helper.py` (`success(...)`, `created(...)`).
- Never build ad-hoc dict responses in controllers.
- `exception_handlers.py` converts all unhandled exceptions and `AppException` subclasses into the standard `ApiResponse` envelope.

## 4. Search and Pagination Standard (All List Endpoints)
**All list endpoints must be POST search endpoints:**
`POST /api/v1/<resource>/search`

Endpoints must take a request body extending `BaseFilter` and return `ApiResponse[PageResult[T]]`.

### Request Body: `BaseFilter` (`core/filter/base_filter.py`)
| Field | Type | Constraints & Defaults |
|---|---|---|
| `page` | integer | **Zero-based index**. Default `0`, minimum `0`. |
| `limit` | integer | Items per page. Default `10`, min `1`, max `100`. |
| `sortBy` | string, optional | Sort column in `camelCase`. Default `"createdAt"`. |
| `sortDir` | `"asc"` \| `"desc"`, optional | Sort direction. Default `"desc"` (newest first). |
| `status` | `"ACTIVE"` \| `"DELETED"`, optional | Default `"ACTIVE"`. Soft-deleted rows returned only if requested. |
| `query` | string, optional | Free-text search (case-insensitive substring). Null/empty means no text filter. |
| `dateFilter` | `DateFilter`, optional | Date window on `createdAt`. **Null means fetch all dates**. |

### `DateFilter` (`core/filter/date_filter.py`)
| Field | JSON Key | Python Attribute | Details |
|---|---|---|---|
| `from` | `"from"` | `from_` | ISO 8601 date-time, nullable. Lower bound. |
| `to` | `"to"` | `to` | ISO 8601 date-time, nullable. Upper bound. |

- `from` and `to` are inclusive.
- If `from` is chronologically after `to`, return `400 Bad Request`.
- If `dateFilter` is null, or both `from` and `to` are null, do not apply date filtering.

### Response Data: `PageResult[T]` (`core/pagination/page_result.py`)
```json
{
  "statusCode": 200,
  "data": {
    "list": [ ... ],
    "page": 0,
    "limit": 10,
    "totalPages": 5,
    "totalItems": 48
  },
  "message": "Fetched successfully",
  "error": null
}
```
- `list`: Array of items. Empty array `[]` when no items match; **never `null`**.
- `totalPages`: `ceil(totalItems / limit)` or `0` when empty.
- Requesting a page beyond `totalPages` returns `200 OK` with `list: []` and correct `totalPages`, not an error.

### Filter Pipeline Execution
All filtering must be applied centrally in `core/filter/filter_builder.py` in this exact order:
1. `status` filter (defaults to `ACTIVE`)
2. `createdAt` date range
3. Substring text search (`query`) on module-declared fields
4. Order by `sortBy` and `sortDir`
5. Paging: `offset(page * limit).limit(limit)`
Item query and total count query must use the exact same filter conditions.
