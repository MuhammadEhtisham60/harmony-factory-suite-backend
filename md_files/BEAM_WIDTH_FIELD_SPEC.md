# Beam Model Width Field Specification & Integration Guide

> **Module:** Factory – Beam (`factory.beam`)  
> **Target Model:** `Beam(models.Model)`  
> **Field Added:** `width` (`DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`)  
> **Migration:** `factory/migrations/0024_beam_width.py`  
> **Specification Version:** 1.0.0  

---

## 1. Overview & Business Context

In the loom factory workflow, physical **Beams** possess key technical specifications such as yarn count, warp count, total ends, length, weight, and fabric/reed **width** (in inches).

The `width` field has been added to the physical `Beam` model so that:
1. Users can record and track physical beam / fabric width during beam creation and editing.
2. The width is exposed across all Beam API endpoints (`GET`, `POST`, `PUT`, `PATCH`).
3. Beams can be filtered by exact width (`width`), minimum width (`min_width`), and maximum width (`max_width`).
4. Beams can be ordered by width ascending (`ordering=width`) or descending (`ordering=-width`).
5. Nested serializers (such as `BeamMinSerializer` in Sizing Assignments and `beamDetail` in `BeamLoadingSerializer`) expose `width`.
6. When a beam is mounted onto a loom via `load_beam_onto_loom()`, the loading automatically falls back to `beam.width` if an explicit width was not specified for the loading.

---

## 2. Database Schema & Migration

### **Field Definition**
```python
width = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    null=True,
    blank=True,
    help_text="Beam / fabric width in inches"
)
```

### **Migration File**
* **File:** `factory/migrations/0024_beam_width.py`
* **Operation:** `migrations.AddField(model_name='beam', name='width', field=models.DecimalField(...))`
* **Database column:** `width NUMERIC(10, 2) NULL`

---

## 3. Files Modified & Changes Summary

| File | Changes Made |
| :--- | :--- |
| `factory/beam/models.py` | Added `width` field to `class Beam(models.Model)`. |
| `factory/migrations/0024_beam_width.py` | Django migration adding `width` to `Beam`. |
| `factory/beam/serializers.py` | Added `width` to `BeamListSerializer`, `BeamDetailSerializer`, and `get_beamDetail` in `BeamLoadingSerializer`. |
| `factory/beam/filters.py` | Added `width`, `min_width`, and `max_width` filters to `BeamFilter`. |
| `factory/beam/views.py` | Added `"width"` to `ordering_fields` in `BeamViewSet`. |
| `factory/beam/admin.py` | Added `"width"` to `list_display` and `Technical Specifications` fieldset in `BeamAdmin`. |
| `factory/yarn/sizing/serializers.py` | Added `width` to `BeamMinSerializer` for sizing assignment responses. |
| `populate_data.py` | Added `width=120.0` to sample beam generation script. |
| `factory/tests/test_beam_width.py` | Automated unit tests covering model storage, API CRUD, filters, ordering, and service integration. |
| `md_files/FACTORY_BEAM_API_SPEC.md` | Updated primary Beam API documentation. |

---

## 4. API Endpoints Reference

### **Base URL:** `/api/v1/factory/beams/`

### **4.1 List Beams with Width**
* **URL:** `GET /api/v1/factory/beams/`
* **Query Parameters for Width:**
  * `width` – exact decimal filter (e.g. `?width=68.00`)
  * `min_width` – beams with width >= value (e.g. `?min_width=60.00`)
  * `max_width` – beams with width <= value (e.g. `?max_width=120.00`)
  * `ordering` – sort by width ascending (`?ordering=width`) or descending (`?ordering=-width`)

#### **Response Sample (`200 OK`)**:
```json
{
  "success": true,
  "count": 1,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": 1,
      "beamName": "Main Beam 1",
      "beamNumber": "BN-10001",
      "yarnCount": "20/1",
      "warpCount": 2400,
      "totalEnds": 2400,
      "length": "1500.00",
      "width": "68.00",
      "weight": "250.00",
      "productionOrder": "PO-2026-001",
      "status": "Available",
      "createdBy": {
        "id": 1,
        "username": "admin",
        "fullName": "Admin User"
      },
      "updatedBy": {
        "id": 1,
        "username": "admin",
        "fullName": "Admin User"
      },
      "createdAt": "2026-10-12T07:00:00Z",
      "updatedAt": "2026-10-12T07:00:00Z"
    }
  ]
}
```

---

### **4.2 Create Beam with Width**
* **URL:** `POST /api/v1/factory/beams/`

#### **Request Body**:
```json
{
  "beamNumber": "BN-10002",
  "beamName": "Wide Fabric Beam",
  "yarnCount": "30/1",
  "warpCount": 2800,
  "totalEnds": 2800,
  "length": 2000.00,
  "width": 72.50,
  "weight": 310.00,
  "productionOrder": "PO-2026-002",
  "status": "Available",
  "notes": "72.5 inch beam for twill weave"
}
```

#### **Response Sample (`201 Created`)**:
```json
{
  "success": true,
  "message": "Beam created successfully.",
  "data": {
    "id": 2,
    "beamNumber": "BN-10002",
    "beamName": "Wide Fabric Beam",
    "yarnCount": "30/1",
    "warpCount": 2800,
    "totalEnds": 2800,
    "length": "2000.00",
    "width": "72.50",
    "weight": "310.00",
    "productionOrder": "PO-2026-002",
    "status": "Available",
    "notes": "72.5 inch beam for twill weave",
    "createdBy": { "id": 1, "username": "admin" },
    "updatedBy": { "id": 1, "username": "admin" },
    "createdAt": "2026-10-12T07:15:00Z",
    "updatedAt": "2026-10-12T07:15:00Z"
  }
}
```

---

### **4.3 Partial Update (PATCH) Width**
* **URL:** `PATCH /api/v1/factory/beams/:id/`

#### **Request Body**:
```json
{
  "width": 74.00
}
```

#### **Response Sample (`200 OK`)**:
```json
{
  "success": true,
  "message": "Beam updated successfully.",
  "data": {
    "id": 2,
    "beamNumber": "BN-10002",
    "width": "74.00",
    "status": "Available"
  }
}
```

---

## 5. TypeScript Definitions

```typescript
export interface Beam {
  id?: number;
  beamNumber: string;         // Unique identifier
  beamName?: string;
  yarnCount?: string;         // e.g. "20/1", "40/1"
  warpCount?: number | null;
  totalEnds?: number | null;
  length?: number | string | null;  // Decimal, e.g. 1500.00
  width?: number | string | null;   // Decimal, e.g. 68.00 (in inches)
  weight?: number | string | null;  // Decimal, e.g. 250.00
  productionOrder?: string;
  status?: string;            // "Available" | "Sizing" | "Loaded" | ...
  notes?: string;
  createdBy?: { id: number; username: string; fullName?: string };
  updatedBy?: { id: number; username: string; fullName?: string };
  createdAt?: string;
  updatedAt?: string;
}
```

---

## 6. Verification & Automated Test Coverage

The test suite in `factory/tests/test_beam_width.py` validates all aspects of the new field:

1. **`test_model_width_field`**: Verifies ORM storage and nullability of `width`.
2. **`test_create_beam_with_width_api`**: Verifies `POST /api/v1/factory/beams/` with `width`.
3. **`test_update_beam_width_api`**: Verifies `PATCH /api/v1/factory/beams/:id/` updates `width`.
4. **`test_filter_beams_by_width`**: Tests `width`, `min_width`, and `max_width` filter queries.
5. **`test_ordering_by_width`**: Tests `ordering=width` and `ordering=-width`.
6. **`test_beam_min_serializer_includes_width`**: Verifies `BeamMinSerializer` includes `width`.
7. **`test_beam_loading_inherits_beam_width`**: Verifies `load_beam_onto_loom()` automatically inherits `beam.width` when loading width is omitted.

Run the test suite with:
```bash
python manage.py test factory.tests.test_beam_width --keepdb
```
Result: **`OK (7 tests passed)`**
