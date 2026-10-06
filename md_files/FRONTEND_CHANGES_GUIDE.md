# Frontend Changes & Compatibility Guide
## Factory Production & Beam Workflow Updates

> **Status:** ✅ **100% Backwards-Compatible** (No Breaking Changes)  
> **Base URL:** `http://<host>/api/v1/factory/`  
> **Target Audience:** Frontend Team  

---

## 1. Quick Summary (TL;DR)

1. **No Breaking Changes:** Your existing frontend code will **continue to work without crashing or failing**.
2. **Production Model Refactor:** In `Production`, `beam` and `loom` are now derived directly from `beam_loading`.
3. **Payload Simplification:** When creating a production record, frontend only needs to send `beam_loading` (or `beamLoadingId`). You no longer need to pass `beam` or `loom` in the POST request body.
4. **Responses Intact:** The backend still returns `beam`, `loom`, `beamDetail`, and `loomDetail` in all GET responses.
5. **Beam Loading Status:** When a beam is mounted onto a loom via `/beam-loadings/`, `Beam.status` transitions directly to **`"In Production"`**.

---

## 2. Production API Changes

### **A. Creating a Production Entry (`POST /api/v1/factory/productions/`)**

#### **What Changed:**
Previously, `beam` and `loom` were separate foreign keys. Now, the backend automatically finds the beam and loom from the `beam_loading` record.

#### **Recommended Payload (Cleaned up):**
```json
{
  "beam_loading": 12,
  "production_date": "2026-10-06",
  "meters_produced": 450.00,
  "shift": "Morning",
  "operator_name": "Aslam",
  "remarks": "Smooth weaving",
  "beam_emptied": false
}
```
*(Also accepts camelCase: `beamLoading`, `beamLoadingId`, `productionDate`, `metersProduced`, `operatorName`, `beamEmptied`)*

> **Frontend Action:**  
> - **Required:** **None.** If your frontend previously sent `"beam"` or `"loom"` in the payload, the backend will safely ignore them without throwing an error.
> - **Recommended:** Remove `beam` and `loom` from your production form state/payload if you want cleaner payloads.

---

### **B. Production Response Objects (`GET /api/v1/factory/productions/`)**

#### **What Changed:**
The response continues to provide full beam and loom details for UI tables, cards, and dropdowns.

#### **Response Data Structure:**
```json
{
  "id": 25,
  "beamLoading": 12,
  "beam": 5,
  "loom": 3,
  "beamId": 5,
  "loomId": 3,
  "beamDetail": {
    "id": 5,
    "beamNumber": "BM-101",
    "status": "In Production"
  },
  "loomDetail": {
    "id": 3,
    "loomCode": "LM-02",
    "status": "Production"
  },
  "productionDate": "2026-10-06",
  "shift": "Morning",
  "metersProduced": "450.00",
  "operatorName": "Aslam",
  "remarks": "Smooth weaving",
  "beamEmptied": false,
  "createdAt": "2026-10-06T07:00:00Z",
  "updatedAt": "2026-10-06T07:00:00Z"
}
```

> **Frontend Action:**  
> - **None required.** Your table columns mapping `production.beamDetail.beamNumber` or `production.loomDetail.loomCode` continue to render identically.

---

### **C. URL Query Parameters & Filters**

All existing filter parameters continue to function identically:

| Query Param | Example | Description |
| :--- | :--- | :--- |
| `?beam=` | `?beam=5` | Filter productions by Beam ID |
| `?loom=` | `?loom=3` | Filter productions by Loom ID |
| `?beam_loading=` | `?beam_loading=12` | Filter productions by BeamLoading ID |
| `?production_date=` | `?production_date=2026-10-06` | Filter by specific date |
| `?date_after=` | `?date_after=2026-10-01` | Filter productions on or after date |
| `?date_before=` | `?date_before=2026-10-31` | Filter productions on or before date |
| `?shift=` | `?shift=Morning` | Filter by shift name |
| `?beam_emptied=` | `?beam_emptied=true` | Filter for final beam runs |
| `?search=` | `?search=BM-101` | Search across operator name, beam number, and loom code |

> **Frontend Action:**  
> - **None required.**

---

## 3. Beam Status Transition Update

### **When Loading Beam onto Loom (`POST /api/v1/factory/beam-loadings/`):**

* **Previous Status:** `Beam.status` became `"Loaded"`.
* **Current Status:** `Beam.status` now transitions directly to **`"In Production"`**.

### **Frontend UI Check:**
If you have badge colors or chip components displaying `beam.status`:
Ensure your badge color map handles `"In Production"`:
```typescript
const getStatusBadgeVariant = (status: string) => {
  switch (status) {
    case "Available":
      return "success";
    case "Sizing":
      return "warning";
    case "Loaded":
    case "In Production":
      return "info"; // Or primary blue
    case "Completed":
      return "secondary";
    default:
      return "default";
  }
};
```

---

## 4. TypeScript Interface Updates (Recommended)

You can update your TypeScript interfaces in `types/production.ts` or similar:

```typescript
export interface ProductionDetail {
  id: number;
  beamLoading: number;
  beam: number | null;
  loom: number | null;
  beamId: number | null;
  loomId: number | null;
  beamDetail: {
    id: number;
    beamNumber: string;
    status: string;
  } | null;
  loomDetail: {
    id: number;
    loomCode: string;
    status: string;
  } | null;
  productionDate: string;
  shift: string;
  metersProduced: string;
  operatorName: string;
  remarks: string;
  beamEmptied: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface CreateProductionRequest {
  beamLoading: number; // or beam_loading
  productionDate: string; // or production_date
  metersProduced: number | string; // or meters_produced
  shift?: string;
  operatorName?: string; // or operator_name
  remarks?: string;
  beamEmptied?: boolean; // or beam_emptied
}
```

---

## 5. Checklist for Frontend Developers

- [ ] **Forms:** Ensure the "Add Production" form selects a `BeamLoading` (the active mounted beam on a loom) rather than requiring separate manual selection of loom & beam.
- [ ] **Payloads:** No need to send `beam` or `loom` in the creation payload.
- [ ] **Badge/Status:** Confirm that the UI handles Beam status `"In Production"` alongside `"Loaded"`.
- [ ] **Unload Action:** Use `POST /api/v1/factory/beam-loadings/:id/empty/` (or `"beam_emptied": true` in production) to unload the beam.
