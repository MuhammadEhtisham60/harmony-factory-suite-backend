# Yarn Name, Yarn Type, & Yarn Count Specification & Changes

## 1. Overview & Architecture

To normalize yarn attributes, improve consistency across the inventory system, and provide standardized dropdown options for users, the following three attributes have been elevated from simple text columns to full Django models with dedicated REST APIs:

1. **`YarnName`**: Stores yarn brand/material names (e.g. *"Cotton"*, *"Organic Cotton"*, *"Polyester Blend"*).
2. **`YarnType`**: Stores yarn processing/composition types (e.g. *"Carded"*, *"Combed"*, *"Ring Spun"*, *"Air Jet"*).
3. **`YarnCount`**: Stores yarn count specifications / linear density (e.g. *"20s"*, *"30/1"*, *"40s / 2"*).

These three models now serve as authoritative **`ForeignKey`** relationships in:
- **`YarnIntake`** (`factory.yarn.yarn_intake.models.YarnIntake`)
- **`YarnStock`** (`factory.yarn.yarn_stock.models.YarnStock`)

---

## 2. Model Specifications

### 2.1 `YarnName` (`factory/yarn/yarn_name/models.py`)
| Field | Type | Options | Description |
|---|---|---|---|
| `id` | `BigAutoField` | Primary Key | Auto-incrementing ID |
| `name` | `CharField` | `max_length=255`, `unique=True` | Unique yarn name |
| `description` | `TextField` | `blank=True`, `default=""` | Optional notes/remarks |
| `status` | `CharField` | Choices: `Active`, `Inactive`, default `Active` | Status flag |
| `created_at` | `DateTimeField` | `auto_now_add=True` | Creation timestamp |
| `updated_at` | `DateTimeField` | `auto_now=True` | Last modification timestamp |
| `created_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Creator audit user |
| `updated_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Updater audit user |

### 2.2 `YarnType` (`factory/yarn/yarn_type/models.py`)
| Field | Type | Options | Description |
|---|---|---|---|
| `id` | `BigAutoField` | Primary Key | Auto-incrementing ID |
| `name` | `CharField` | `max_length=100`, `unique=True` | Unique yarn type classification |
| `description` | `TextField` | `blank=True`, `default=""` | Optional notes/remarks |
| `status` | `CharField` | Choices: `Active`, `Inactive`, default `Active` | Status flag |
| `created_at` | `DateTimeField` | `auto_now_add=True` | Creation timestamp |
| `updated_at` | `DateTimeField` | `auto_now=True` | Last modification timestamp |
| `created_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Creator audit user |
| `updated_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Updater audit user |

### 2.3 `YarnCount` (`factory/yarn/yarn_count/models.py`)
| Field | Type | Options | Description |
|---|---|---|---|
| `id` | `BigAutoField` | Primary Key | Auto-incrementing ID |
| `name` | `CharField` | `max_length=100`, `unique=True` | Unique count specification |
| `description` | `TextField` | `blank=True`, `default=""` | Optional notes/remarks |
| `status` | `CharField` | Choices: `Active`, `Inactive`, default `Active` | Status flag |
| `created_at` | `DateTimeField` | `auto_now_add=True` | Creation timestamp |
| `updated_at` | `DateTimeField` | `auto_now=True` | Last modification timestamp |
| `created_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Creator audit user |
| `updated_by` | `ForeignKey` | `AUTH_USER_MODEL`, `SET_NULL`, nullable | Updater audit user |

---

## 3. Foreign Key Integrations

### 3.1 `YarnIntake` (`factory/yarn/yarn_intake/models.py`)
`yarn_name`, `yarn_type`, and `yarn_count` were changed from `CharField` to:
```python
yarn_name = models.ForeignKey(
    YarnName,
    on_delete=models.PROTECT,
    related_name="yarn_intakes",
    help_text="Yarn Name reference"
)
yarn_type = models.ForeignKey(
    YarnType,
    on_delete=models.PROTECT,
    related_name="yarn_intakes",
    help_text="Yarn Type reference"
)
yarn_count = models.ForeignKey(
    YarnCount,
    on_delete=models.PROTECT,
    related_name="yarn_intakes",
    help_text="Yarn Count reference"
)
```

### 3.2 `YarnStock` (`factory/yarn/yarn_stock/models.py`)
```python
yarn_name = models.ForeignKey(
    YarnName,
    on_delete=models.PROTECT,
    related_name="yarn_stocks",
    help_text="Yarn Name reference"
)
yarn_type = models.ForeignKey(
    YarnType,
    on_delete=models.PROTECT,
    related_name="yarn_stocks",
    help_text="Yarn Type reference"
)
yarn_count = models.ForeignKey(
    YarnCount,
    on_delete=models.PROTECT,
    related_name="yarn_stocks",
    help_text="Yarn Count reference"
)
```

**Constraints & Indexes on `YarnStock`**:
```python
constraints = [
    models.UniqueConstraint(
        fields=["yarn_name", "yarn_type", "yarn_count", "production_type"],
        name="unique_yarn_stock_pool",
    )
]
indexes = [
    models.Index(
        fields=["yarn_name", "yarn_type", "yarn_count", "production_type"],
        name="idx_yarn_stock_pool",
    ),
]
```

### 3.3 Seamless Backward Compatibility & Resolution
1. **Model `__init__` resolution**:
   Both `YarnIntake` and `YarnStock` support receiving either model instances, integer IDs (`yarnNameId`, `yarn_name_id`), or string names (`yarnName`, `yarn_name`). String names are automatically resolved to `get_or_create()` model instances.
2. **Custom QuerySets (`YarnIntakeQuerySet`, `YarnStockQuerySet`)**:
   Calling `.filter(yarn_name="Cotton")` or `.get(yarn_count="20/1")` dynamically transparently redirects string lookups to `yarn_name__name="Cotton"`, preventing integer-lookup casting errors.
3. **Stock Service (`normalize_stock_fields`, `get_or_create_yarn_stock`)**:
   Accepts strings, integer IDs, or model instances and resolves them atomically.

---

## 4. REST API Endpoints

The endpoints are registered in `config/urls.py` under `/api/v1/`:

### 4.1 Yarn Names (`/api/v1/yarn-names/`)
- `GET /api/v1/yarn-names/` - List yarn names (paginated, filterable by `name`, `status`, `search`).
- `POST /api/v1/yarn-names/` - Create a yarn name.
- `GET /api/v1/yarn-names/{id}/` - Retrieve yarn name details.
- `PUT /api/v1/yarn-names/{id}/` - Full update.
- `PATCH /api/v1/yarn-names/{id}/` - Partial update.
- `DELETE /api/v1/yarn-names/{id}/` - Delete.
- `GET /api/v1/yarn-names/choices/` - Compact list of active yarn names (`[{"id": 1, "name": "Cotton"}]`) for frontend select dropdowns.

### 4.2 Yarn Types (`/api/v1/yarn-types/`)
- `GET /api/v1/yarn-types/` - List yarn types (paginated, filterable by `name`, `status`, `search`).
- `POST /api/v1/yarn-types/` - Create a yarn type.
- `GET /api/v1/yarn-types/{id}/` - Retrieve yarn type details.
- `PUT /api/v1/yarn-types/{id}/` - Full update.
- `PATCH /api/v1/yarn-types/{id}/` - Partial update.
- `DELETE /api/v1/yarn-types/{id}/` - Delete.
- `GET /api/v1/yarn-types/choices/` - Compact list of active yarn types for dropdowns.

### 4.3 Yarn Counts (`/api/v1/yarn-counts/`)
- `GET /api/v1/yarn-counts/` - List yarn counts (paginated, filterable by `name`, `status`, `search`).
- `POST /api/v1/yarn-counts/` - Create a yarn count.
- `GET /api/v1/yarn-counts/{id}/` - Retrieve yarn count details.
- `PUT /api/v1/yarn-counts/{id}/` - Full update.
- `PATCH /api/v1/yarn-counts/{id}/` - Partial update.
- `DELETE /api/v1/yarn-counts/{id}/` - Delete.
- `GET /api/v1/yarn-counts/choices/` - Compact list of active yarn counts for dropdowns.

---

## 5. Serializer Payloads & Output Structure

Both `YarnIntake` and `YarnStock` APIs return rich, backwards-compatible payloads containing both IDs, string names, and detailed objects:

```json
{
  "id": 1,
  "yarnName": "Cotton",
  "yarnType": "Carded",
  "yarnCount": "20s",
  "yarnNameId": 1,
  "yarnTypeId": 2,
  "yarnCountId": 3,
  "yarnNameDetail": {
    "id": 1,
    "name": "Cotton"
  },
  "yarnTypeDetail": {
    "id": 2,
    "name": "Carded"
  },
  "yarnCountDetail": {
    "id": 3,
    "name": "20s"
  }
}
```

### Supported Writable Inputs on `POST /api/v1/yarn-intakes/`:
Clients can provide either:
- Foreign key IDs: `yarnNameId: 1`, `yarnTypeId: 2`, `yarnCountId: 3` (or `yarn_name_id`, etc.)
- String names: `yarnName: "Cotton"`, `yarnType: "Carded"`, `yarnCount: "20s"` (auto-creates if missing)

---

## 6. Database Migration Strategy

### Migration `0026_create_yarn_name_type_count_and_convert_fks.py`
A multi-stage, zero-data-loss migration was executed:
1. Created tables for `YarnName`, `YarnType`, `YarnCount`.
2. Added temporary nullable columns `yarn_name_fk`, `yarn_type_fk`, `yarn_count_fk` to `YarnIntake` and `YarnStock`.
3. Extracted all existing distinct string values from existing database rows and inserted them into `YarnName`, `YarnType`, and `YarnCount`.
4. Populated the new foreign key columns with the corresponding IDs for all existing records.
5. Dropped old unique constraints, indexes, and CharField columns.
6. Renamed the temporary FK columns to `yarn_name`, `yarn_type`, and `yarn_count`.
7. Enforced `null=False` on the foreign keys.
8. Re-established the composite unique constraint and composite index on `YarnStock`.

---

## 7. Automated Test Suite Results

All test suites were executed with `--keepdb` and verified passing:
- `factory.tests.test_yarn_attributes` (6 tests - **PASSED**)
- `factory.tests.test_shared_yarn_stock` (14 tests - **PASSED**)
- `factory.tests.test_yarn_intake_set_no` (6 tests - **PASSED**)
- `factory.tests.test_beam_width` (6 tests - **PASSED**)

**Total: 32 tests passed with zero errors.**
