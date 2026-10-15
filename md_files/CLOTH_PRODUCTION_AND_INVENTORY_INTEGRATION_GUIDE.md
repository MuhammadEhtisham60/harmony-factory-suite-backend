# Cloth Production and Stock Inventory — Frontend Integration Guide

> **Module:** Factory – Cloth Production & Inventory  
> **Backend Framework:** Django REST Framework (DRF)  
> **Base URL:** `/api/v1/` (also available via `/api/v1/factory/`)  
> **Authentication:** `Authorization: Bearer <access_token>`  
> **Precision Compliance:** Full decimal precision preserved across all intermediate and final calculations without premature rounding.

---

## 1. Workflow Architecture & Lifecycle

```
[Available Beam] ──(Load Beam onto Loom)──► [BeamLoading: "Loaded"]
                                                    │
                                         (First Patch Produced)
                                                    ▼
                                            [BeamLoading: "In Production"]
                                            [Beam: "In Production"]
                                            [Loom: "Production"]
                                                    │
                                      (Daily ClothPatches Cut)
                                                    │
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                           [Raw Stock Screen]           [Classify Stock]
                           (Individual Patches)         (Clean vs. Defected)
                                                                  │
                                                                  ├─► CleanClothStock ──► Syncs ClothStock.total_length
                                                                  └─► DefectedClothStock (Computed separately)
                                                    │
                                           (Cycle Finishes)
                                                    ▼
                                      POST /beam-loadings/{id}/dismount/
                                                    │
                                      ┌─────────────┴─────────────┐
                                      ▼                           ▼
                        [Production Reconciliation]     [Beam Status: "Available"]
                        - Expected vs. Actual Length     (Ready for reuse in new cycle!)
                        - Difference & Percentage       [Loom Status: "Active"]
                        - BeamLoading: "Completed"
```

---

## 2. API Endpoints Quick Reference

| Endpoint | Method | Purpose | Permission Code |
| :--- | :--- | :--- | :--- |
| `/api/v1/cloth-names/` | `GET`, `POST` | List & create cloth master names/qualities | `cloth.view`, `cloth.add` |
| `/api/v1/cloth-names/{id}/` | `GET`, `PATCH`, `DELETE` | Retrieve, update, delete cloth name | `cloth.view`, `cloth.edit`, `cloth.delete` |
| `/api/v1/cloth-patches/` | `GET`, `POST` | Record cloth patch, list patches | `cloth.view`, `cloth.add` |
| `/api/v1/cloth-patches/{id}/` | `GET`, `PATCH`, `DELETE` | Retrieve, update, delete patch | `cloth.view`, `cloth.edit`, `cloth.delete` |
| `/api/v1/raw-stock/` | `GET` | **Raw Stock Screen**: list all patches individually | `cloth.view` |
| `/api/v1/cloth-stock/` | `GET`, `POST` | **Cloth Stock Screen**: consolidated rows by cloth name | `stock.view`, `stock.manage` |
| `/api/v1/cloth-stock/{id}/` | `GET`, `PATCH`, `DELETE` | Retrieve, manage consolidated stock | `stock.view`, `stock.manage` |
| `/api/v1/cloth-stock/{id}/recalculate/` | `POST` | Re-sync clean total for a cloth stock row | `stock.manage` |
| `/api/v1/clean-cloth-stock/` | `GET`, `POST` | **Clean Stock Screen**: list clean records (filter by `cloth_stock`) | `stock.view`, `stock.manage` |
| `/api/v1/clean-cloth-stock/{id}/` | `GET`, `PATCH`, `DELETE` | Retrieve, update, delete clean record | `stock.view`, `stock.manage` |
| `/api/v1/defected-cloth-stock/` | `GET`, `POST` | **Defected Stock Screen**: list defect records (filter by `cloth_stock`) | `stock.view`, `stock.manage` |
| `/api/v1/defected-cloth-stock/{id}/` | `GET`, `PATCH`, `DELETE` | Retrieve, update, delete defect record | `stock.view`, `stock.manage` |
| `/api/v1/beam-loadings/{id}/dismount/` | `POST` | Dismount beam, compute & save reconciliation, set beam Available | `cloth.dismount`, `beams.assign` |
| `/api/v1/beam-loadings/{id}/dismount/` | `GET` | Retrieve authoritative reconciliation report for loading cycle | `cloth.view`, `beams.view` |
| `/api/v1/beam-loadings/{id}/reconciliation/`| `GET` | Alias for reading reconciliation report | `cloth.view`, `beams.view` |

---

## 3. Screen 1: Raw Stock Screen

The **Raw Stock** screen displays every cloth patch individually (never grouped or merged).

### Endpoint
`GET /api/v1/raw-stock/` (or `GET /api/v1/cloth-patches/`)

### Supported Query Parameters
- `page` & `page_size` (pagination)
- `search` (searches `patch_number`, `cloth_name__name`, `loom__loom_code`, `beam__beam_number`)
- `cloth_name` / `cloth_name_id` (filter by cloth name ID)
- `loom` / `loom_id` (filter by loom)
- `beam` / `beam_id` (filter by physical beam)
- `beam_loading` / `beam_loading_id` (filter by loading cycle)
- `patch_date` / `date_from` / `date_to` (date filters)
- `ordering` (e.g. `-patch_date`, `patch_number`, `productive_length`)

### Example Response: HTTP 200 OK
```json
{
  "success": true,
  "count": 25,
  "totalPages": 3,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": 101,
      "patchNumber": "PATCH-2026-0045",
      "patch_number": "PATCH-2026-0045",
      "clothName": {
        "id": 4,
        "name": "Cotton 40/40"
      },
      "cloth_name": 4,
      "loomDetail": {
        "id": 5,
        "loomCode": "L-101",
        "loom_code": "L-101",
        "loomName": "Airjet Loom 101",
        "status": "Production"
      },
      "beamDetail": {
        "id": 12,
        "beamNumber": "BEAM-01",
        "beam_number": "BEAM-01",
        "beamName": "Warp Beam 1",
        "status": "In Production"
      },
      "beamLoading": 18,
      "patchDate": "2026-10-14",
      "bundleCount": 1,
      "productiveLength": "120.500000",
      "cleanAllocatedLength": "100.000000",
      "defectedAllocatedLength": "20.500000",
      "classifiedLength": "120.500000",
      "unallocatedLength": "0.000000",
      "remarks": "Smooth weaving, zero breaks.",
      "createdAt": "2026-10-14T10:15:00Z"
    }
  ]
}
```

### Creating a Patch (When cloth is removed from Loom)
`POST /api/v1/cloth-patches/`

```json
{
  "beam_loading": 18,
  "patch_number": "PATCH-2026-0046",
  "cloth_name": 4,
  "patch_date": "2026-10-14",
  "bundle_count": 1,
  "productive_length": "125.000000",
  "remarks": "Morning shift roll cut"
}
```

> **Note:** `loom` and `beam` are automatically derived from the active `beam_loading` cycle if omitted, or strictly validated if provided.

---

## 4. Screen 2: Cloth Stock Screen (Consolidated Stock)

Displays one consolidated row per Cloth Name.

### Endpoint
`GET /api/v1/cloth-stock/`

### Important Stock Rules:
1. `total_length` (`totalLength`) represents **Clean Stock ONLY**.
2. Defective stock is returned in `defected_total_length` (`defectedTotalLength`) as a separate column.
3. Defective stock is **never** added into `total_length`.

### Supported Query Parameters
- `search` (searches cloth name)
- `name` (filter by cloth name title)
- `page` & `page_size`

### Example Response: HTTP 200 OK
```json
{
  "success": true,
  "count": 2,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": 1,
      "cloth_name": {
        "id": 4,
        "name": "Cotton 40/40"
      },
      "clothName": {
        "id": 4,
        "name": "Cotton 40/40"
      },
      "cloth_name_id": 4,
      "clothNameId": 4,
      "total_length": "275.000000",
      "totalLength": "275.000000",
      "defected_total_length": "15.000000",
      "defectedTotalLength": "15.000000",
      "clean_record_count": 3,
      "cleanRecordCount": 3,
      "defected_record_count": 2,
      "defectedRecordCount": 2,
      "createdAt": "2026-10-14T09:00:00Z",
      "updatedAt": "2026-10-14T11:20:00Z"
    }
  ]
}
```

---

## 5. Screen 3: Clean Stock Detail Screen

Opened when clicking the **"View Clean Stock"** action button for a cloth quality row.

### Endpoint
`GET /api/v1/clean-cloth-stock/?cloth_stock={cloth_stock_id}`

### Supported Filters:
- `cloth_stock` / `clothStock` (Filter by ClothStock ID)
- `cloth_patch` / `clothPatch` (Filter by ClothPatch ID)
- `patch_number` / `patchNumber` (Filter by patch number)
- `stock_date` / `date_from` / `date_to`

### Example Response: HTTP 200 OK
```json
{
  "success": true,
  "count": 3,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": 51,
      "clothStock": 1,
      "cloth_stock": 1,
      "clothName": { "id": 4, "name": "Cotton 40/40" },
      "clothPatch": 101,
      "cloth_patch": 101,
      "patchNumber": "PATCH-2026-0045",
      "patch_number": "PATCH-2026-0045",
      "patchProductiveLength": "120.500000",
      "totalLength": "100.000000",
      "total_length": "100.000000",
      "stockDate": "2026-10-14",
      "remarks": "Grade A clean fabric",
      "createdAt": "2026-10-14T10:30:00Z"
    }
  ]
}
```

### Allocating Clean Stock
`POST /api/v1/clean-cloth-stock/`

```json
{
  "cloth_stock": 1,
  "cloth_patch": 101,
  "total_length": "100.000000",
  "stock_date": "2026-10-14",
  "remarks": "Passed A-grade inspection"
}
```

---

## 6. Screen 4: Defected Stock Detail Screen

Opened when clicking the **"View Defected Stock"** action button for a cloth quality row.

### Endpoint
`GET /api/v1/defected-cloth-stock/?cloth_stock={cloth_stock_id}`

### Supported Filters:
- `cloth_stock` / `clothStock` (Filter by ClothStock ID)
- `cloth_patch` / `clothPatch` (Filter by ClothPatch ID)
- `defect_type` / `defectType` (Filter by defect type: Oil Stain, Warp Break, etc.)
- `patch_number` / `patchNumber`
- `stock_date` / `date_from` / `date_to`

### Example Response: HTTP 200 OK
```json
{
  "success": true,
  "count": 2,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": 31,
      "clothStock": 1,
      "cloth_stock": 1,
      "clothName": { "id": 4, "name": "Cotton 40/40" },
      "clothPatch": 101,
      "cloth_patch": 101,
      "patchNumber": "PATCH-2026-0045",
      "patch_number": "PATCH-2026-0045",
      "patchProductiveLength": "120.500000",
      "defectType": "Oil Stain",
      "defect_type": "Oil Stain",
      "defectDescription": "Minor oil drops near selvedge",
      "defect_description": "Minor oil drops near selvedge",
      "totalLength": "20.500000",
      "total_length": "20.500000",
      "stockDate": "2026-10-14",
      "remarks": "Downgraded to B-grade",
      "createdAt": "2026-10-14T10:35:00Z"
    }
  ]
}
```

### Allocating Defective Stock
`POST /api/v1/defected-cloth-stock/`

```json
{
  "cloth_stock": 1,
  "cloth_patch": 101,
  "defect_type": "Oil Stain",
  "defect_description": "Selvedge oil spots",
  "total_length": "20.500000",
  "stock_date": "2026-10-14",
  "remarks": "Marked for stain removal"
}
```

---

## 7. Allocation Invariant & Validation Rules

For every individual `ClothPatch`:

$$\text{classified\_length} = \sum \text{clean\_length} + \sum \text{defected\_length}$$
$$\text{classified\_length} \le \text{patch.productive\_length}$$

### Validation Behavior:
- **Valid:** Patch productive length = `100m`. Clean allocation = `90m`, Defect allocation = `10m`. Total classified = `100m`. (Accepted)
- **Over-allocation Rejected:** If user tries to allocate an additional `1m` on the above patch, backend returns **HTTP 400 Bad Request**:
  ```json
  {
    "total_length": [
      "Proposed allocation of 1.000000m exceeds available patch productive length. Patch productive length: 100.000000m. Already classified: 100.000000m (Clean: 90.000000m, Defected: 10.000000m). Remaining unallocated: 0.000000m."
    ]
  }
  ```
- **Partial Allocation Allowed:** If only `60m` is classified, the remaining `40m` remains unallocated. The backend **never** assumes or auto-allocates remaining fabric.

---

## 8. Beam Dismount & Production Reconciliation

When a beam finishes its production run on a loom:

### Dismount Endpoint
`POST /api/v1/beam-loadings/{id}/dismount/`

### Request Payload (Optional parameters)
```json
{
  "dismount_date": "2026-10-14",
  "remarks": "Beam cycle completed normally",
  "expected_length": "5000.000000"
}
```
*(If `expected_length` is not provided in payload, the backend automatically calculates it using the verified formula).*

### Expected Production Length Formula:
$$\text{expected\_length} = \text{yarn\_length} \times \left(1 - \frac{\text{shortage}}{100}\right)$$

Where:
- `yarn_length`: Retrieved from `SizingBeamAssignment.beam_yarn_length[beam_id]` (or `Beam.length` / `sizing_outcome.set_length_meter`).
- `shortage`: Shortage percentage from `BeamLoading.shortage` (or `sizing_outcome.total_set_shortage`).

### Actual Production Length Formula:
$$\text{actual\_length} = \sum \text{ClothPatch.productive\_length (for this BeamLoading cycle)}$$

### Reconciliation Formulas:
$$\text{difference} = \text{actual\_length} - \text{expected\_length}$$
$$\text{production\_percentage} = \left(\frac{\text{actual\_length}}{\text{expected\_length}}\right) \times 100$$

- **Difference > 0:** Actual production exceeded expected length.
- **Difference < 0:** Actual production fell short of expected length.
- **Difference = 0:** Actual production matched expected length exactly.

### Response Payload: HTTP 200 OK
```json
{
  "success": true,
  "message": "Beam 'BEAM-01' successfully dismounted from Loom 'L-101'. Reconciliation: Actual 4950.000000m vs Expected 5000.000000m (-50.000000m).",
  "data": {
    "id": 1,
    "loadingId": 18,
    "loading_id": 18,
    "beam": {
      "id": 12,
      "beamNumber": "BEAM-01",
      "beam_number": "BEAM-01",
      "beamName": "Warp Beam 1",
      "status": "Available"
    },
    "loom": {
      "id": 5,
      "loomCode": "L-101",
      "loom_code": "L-101",
      "loomName": "Airjet Loom 101",
      "status": "Active"
    },
    "expectedLength": "5000.000000",
    "expected_length": "5000.000000",
    "actualLength": "4950.000000",
    "actual_length": "4950.000000",
    "difference": "-50.000000",
    "productionPercentage": "99.0000",
    "production_percentage": "99.0000",
    "dismountDate": "2026-10-14",
    "dismount_date": "2026-10-14",
    "loadingStatus": "Completed",
    "loading_status": "Completed",
    "remarks": "Beam cycle completed normally",
    "dismountedBy": {
      "id": 2,
      "username": "operator"
    },
    "createdAt": "2026-10-14T11:45:00Z",
    "updatedAt": "2026-10-14T11:45:00Z"
  }
}
```

### Reading Existing Reconciliation Report:
`GET /api/v1/beam-loadings/{id}/dismount/`  
*(or `GET /api/v1/beam-loadings/{id}/reconciliation/`)*

### Multi-Cycle Beam Reusability:
- Dismounting automatically sets `Beam.status = "Available"`.
- The beam can now be remounted on any loom in a brand-new `BeamLoading` cycle.
- All historical loading cycles and their respective patches and reconciliations remain permanently untouched.

---

## 9. TypeScript Type Definitions

```typescript
export interface ClothName {
  id: number;
  name: string;
  description?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface ClothPatch {
  id: number;
  patchNumber: string;
  patch_number?: string;
  clothName: {
    id: number;
    name: string;
  };
  cloth_name?: number;
  loomDetail: {
    id: number;
    loomCode: string;
    loomName?: string;
    status?: string;
  };
  beamDetail: {
    id: number;
    beamNumber: string;
    beamName?: string;
    status?: string;
  };
  beamLoading: number;
  patchDate: string;
  bundleCount: number;
  productiveLength: string;
  cleanAllocatedLength?: string;
  defectedAllocatedLength?: string;
  classifiedLength?: string;
  unallocatedLength?: string;
  remarks?: string;
  createdAt?: string;
}

export interface ClothStock {
  id: number;
  clothName: {
    id: number;
    name: string;
  };
  cloth_name?: {
    id: number;
    name: string;
  };
  clothNameId: number;
  cloth_name_id?: number;
  totalLength: string; // Clean stock ONLY
  total_length?: string;
  defectedTotalLength: string; // Separate Defective stock
  defected_total_length?: string;
  cleanRecordCount: number;
  defectedRecordCount: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface CleanClothStock {
  id: number;
  clothStock: number;
  clothName: {
    id: number;
    name: string;
  };
  clothPatch: number;
  patchNumber: string;
  patchProductiveLength: string;
  totalLength: string;
  stockDate: string;
  remarks?: string;
  createdAt?: string;
}

export interface DefectedClothStock {
  id: number;
  clothStock: number;
  clothName: {
    id: number;
    name: string;
  };
  clothPatch: number;
  patchNumber: string;
  patchProductiveLength: string;
  defectType: string;
  defectDescription?: string;
  totalLength: string;
  stockDate: string;
  remarks?: string;
  createdAt?: string;
}

export interface BeamDismountReconciliation {
  id: number;
  loadingId: number;
  beam: {
    id: number;
    beamNumber: string;
    beamName?: string;
    status: string;
  };
  loom: {
    id: number;
    loomCode: string;
    loomName?: string;
    status: string;
  };
  expectedLength: string;
  actualLength: string;
  difference: string;
  productionPercentage: string | null;
  dismountDate: string;
  loadingStatus: string;
  remarks?: string;
  dismountedBy?: {
    id: number;
    username: string;
  };
}
```

---

## 10. Frontend Action & Button Mapping Summary

| Screen | Action Button | API Call Triggered |
| :--- | :--- | :--- |
| **Looms / Production** | "Cut / Record Patch" | `POST /api/v1/cloth-patches/` |
| **Looms / Production** | "Dismount Beam" | `POST /api/v1/beam-loadings/{id}/dismount/` |
| **Looms / Production** | "View Reconciliation" | `GET /api/v1/beam-loadings/{id}/dismount/` |
| **Raw Stock** | Screen initial load | `GET /api/v1/raw-stock/` |
| **Cloth Stock** | Screen initial load | `GET /api/v1/cloth-stock/` |
| **Cloth Stock** | "View Clean Stock" | `GET /api/v1/clean-cloth-stock/?cloth_stock={id}` |
| **Cloth Stock** | "View Defected Stock"| `GET /api/v1/defected-cloth-stock/?cloth_stock={id}` |
| **Cloth Stock** | "Classify Clean" | `POST /api/v1/clean-cloth-stock/` |
| **Cloth Stock** | "Classify Defect" | `POST /api/v1/defected-cloth-stock/` |
