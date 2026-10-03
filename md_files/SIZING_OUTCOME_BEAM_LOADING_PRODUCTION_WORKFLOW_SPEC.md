# Sizing Outcome, Beam Loading & Production Workflow
## Frontend Developer Integration Guide & Complete API Specification

> **Base URL:** `http://<host>/api/v1/`  
> **Auth:** Every request requires an HTTP header: `Authorization: Bearer <access_jwt_token>`  
> **Content-Type:** `application/json`  
> **Accept:** `application/json`  

---

## 1. Executive Business Workflow & Architecture

In our power loom textile manufacturing system, **Beams** and **Looms** are persistent, physical assets in the factory. 

```
Yarn Intake (Warehouse Stock)
      │
      ▼
Yarn Outcome (outcome_type = 'Sizing')
      │
      ▼
Sizing Unit (Process Managed by Sizing Mill)
      │
      ▼
Sizing Outcome (Return of the Set from Sizing)
      │
      ├── (One Sizing Outcome loaded onto 1 or MANY Beams)
      ▼
Beam Loading ──► Connects: SizingOutcome + Existing Beam + Existing Loom
      │          (Beam.status: AVAILABLE ──► LOADED)
      │          (Loom.status: ACTIVE ──► PRODUCTION)
      ▼
Production (Cloth weaving / daily meters logged)
      │          (Beam.status: LOADED ──► IN_PRODUCTION)
      ▼
Beam Becomes Empty (beam_emptied = true OR POST /beam-loadings/:id/empty/)
      │
      ├─────────────────────────────────────────┐
      ▼                                         ▼
Beam.status = AVAILABLE                   Loom.status = ACTIVE
(Ready for reuse in next Sizing Set!)      (Ready for next loaded beam)
      │
      ▼
Next Sizing Outcome (Set B)
      │
      ▼
New BeamLoading (Reusing SAME Beam #1!)
(Old BeamLoading history for Set A is permanently preserved)
```

### Core Tenets for Frontend Developers:
1. **Physical Asset Reuse:** A `Beam` is a physical piece of machinery hardware. **NEVER** create a new Beam when a new Sizing Outcome arrives. The same Beam record in the database is reused across dozens of sizing cycles.
2. **Permanent Audit Trail:** The junction model `BeamLoading` stores every cycle in history (`SizingOutcome` ↔ `Beam` ↔ `Loom`). Past history is never deleted or overwritten.
3. **Beam Status Lifecycle:**
   - `Available` → Beam is empty in the warehouse, ready to receive yarn.
   - `Loaded` → Sizing yarn has been wound onto the beam and mounted on a Loom via `BeamLoading`.
   - `In Production` → Loom is actively weaving fabric from this beam.
   - `Completed` / `Empty` → Yarn on the beam is finished. Beam status immediately resets to `Available`.
4. **Dual Case Tolerance:** The backend API accepts **both** `camelCase` and `snake_case` in request payloads (e.g. `set_no` and `setNo`, `warp_count` and `warpCount`, `beam_id` and `beamId`, `meters_produced` and `metersProduced`). Responses are formatted in standard JSON with camelCase aliases and nested detail objects.

---

## 2. API Endpoints Quick Reference

| Method | Endpoint | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| **Sizing Outcomes** | | | |
| `GET` | `/api/v1/sizing-outcomes/` | List sizing outcome sets (paginated, filterable) | `sizing.view` |
| `POST` | `/api/v1/sizing-outcomes/` | Create return set from sizing (all 24 spec fields) | `sizing.add` |
| `GET` | `/api/v1/sizing-outcomes/:id/` | Retrieve single sizing outcome set details | `sizing.view` |
| `PUT/PATCH` | `/api/v1/sizing-outcomes/:id/` | Update sizing outcome record | `sizing.edit` |
| `DELETE` | `/api/v1/sizing-outcomes/:id/` | Delete sizing outcome | `sizing.delete` |
| **Beam Loading (Mounting Beams onto Looms)** | | | |
| `GET` | `/api/v1/factory/beam-loadings/` | List all beam loadings (filterable by beam, loom, outcome, status) | `beams.view` |
| `POST` | `/api/v1/factory/beam-loadings/` | Load 1 existing Beam onto a Loom for a Sizing Outcome | `beams.assign` |
| `POST` | `/api/v1/factory/beam-loadings/batch/` | Load multiple Beams in one atomic API request | `beams.assign` |
| `GET` | `/api/v1/factory/beam-loadings/:id/` | Retrieve beam loading details | `beams.view` |
| `PATCH` | `/api/v1/factory/beam-loadings/:id/` | Update technical specifications on loading | `beams.edit` |
| `DELETE` | `/api/v1/factory/beam-loadings/:id/` | Delete loading (only allowed if not yet in production) | `beams.delete` |
| `POST` | `/api/v1/factory/beam-loadings/:id/empty/` | Mark beam empty manually ➔ Beam becomes `Available` | `beams.assign` |
| `GET` | `/api/v1/factory/beam-loadings/active/` | List all currently active loadings (`Loaded` or `In Production`) | `beams.view` |
| **Production (Daily Meters Logged)** | | | |
| `GET` | `/api/v1/factory/productions/` | List daily production entries (filterable by beam, loom, date) | `looms.view` |
| `POST` | `/api/v1/factory/productions/` | Log daily fabric meters produced (if emptied, auto-releases beam) | `looms.production` |
| `GET` | `/api/v1/factory/productions/:id/` | Retrieve single production entry | `looms.view` |
| `PATCH` | `/api/v1/factory/productions/:id/` | Update production entry | `looms.production` |
| `DELETE` | `/api/v1/factory/productions/:id/` | Delete production entry | `looms.delete` |
| `GET` | `/api/v1/factory/productions/stats/` | Summary metrics: total meters produced, entries, emptied beams | `looms.view` |
| **Beams & History** | | | |
| `GET` | `/api/v1/factory/beams/available/` | Dropdown list: Beams currently `Available` for loading | `beams.view` |
| `GET` | `/api/v1/factory/beams/:id/loading-history/` | Full multi-cycle history of all loadings and looms for a beam | `beams.view` |

*(Note: Endpoints under `/api/v1/factory/beam-loadings/` and `/api/v1/factory/productions/` are also aliased at `/api/v1/beam-loadings/` and `/api/v1/productions/`)*

---

## 3. Sizing Outcome API Specifications

`SizingOutcome` represents: **"Return of the Set from Sizing"**. It answers: *"What Set came back from Sizing?"*

### All 24 Required Fields:

| Field Name (JSON) | Alternative (snake_case) | Type | Description |
| :--- | :--- | :--- | :--- |
| `sizingId` / `sizing` | `sizing_id` / `sizing` | `integer` | Sizing Mill / Unit ID *(Required)* |
| `outcomeDate` | `outcome_date` | `string (YYYY-MM-DD)` | Date set returned from sizing *(Required)* |
| `setNo` | `set_no` | `string` | Sizing set number (e.g. `"SET-2026-001"`) |
| `sizingName` | `sizing_name` | `string` | Name of sizing party / mill |
| `totalBagsOnSizing` | `total_bags_on_sizing` | `integer` | Total bags sent to sizing |
| `bagPackingCone` | `bag_packing_cone` | `integer` | Cones per bag |
| `totalCones` | `total_cones` | `integer` | Total cones |
| `remainingBagsOnSizingStock`| `remaining_bags_on_sizing_stock` | `integer` | Remaining bags in sizing stock |
| `remainingConesOnSizingStock`| `remaining_cones_on_sizing_stock` | `integer` | Remaining cones in sizing stock |
| `lagatBags` | `lagat_bags` | `decimal` | Lagat (consumed) bags |
| `lagatCones` | `lagat_cones` | `decimal` | Lagat (consumed) cones |
| `brand` | `brand` | `string` | Yarn brand name |
| `width` | `width` | `decimal` | Width in inches |
| `setLengthMeter` | `set_length_meter` | `decimal` | Length of set in meters |
| `setLengthGaz` | `set_length_gaz` | `decimal` | Length of set in gaz (yards) |
| `totalTarr` | `total_tarr` | `decimal` | Total ends / tarr |
| `yarnBeam` | `yarn_beam` | `string` | Yarn beam identifier |
| `backBeam` | `back_beam` | `string` | Back beam identifier |
| `count` | `count` | `string` | Yarn count (e.g. `"40/1"`) |
| `totalSetLumbai` | `total_set_lumbai` | `decimal` | Total set lumbai (length) |
| `totalSetShortage` | `total_set_shortage` | `decimal` | Total set shortage percentage / meters |
| `remarks` | `remarks` | `string` | Free text remarks |
| `createdAt` | `created_at` | `timestamp` | Auto audit timestamp (Read-only) |
| `updatedAt` | `updated_at` | `timestamp` | Auto audit timestamp (Read-only) |
| `createdBy` | `created_by` | `object` | User `{ id, username }` (Read-only) |
| `updatedBy` | `updated_by` | `object` | User `{ id, username }` (Read-only) |

### Example Request: Create Sizing Outcome
`POST /api/v1/sizing-outcomes/`

```json
{
  "sizing_id": 1,
  "outcome_date": "2026-10-03",
  "set_no": "SET-2026-001",
  "sizing_name": "Standard Sizing Mills",
  "total_bags_on_sizing": 50,
  "bag_packing_cone": 24,
  "total_cones": 1200,
  "remaining_bags_on_sizing_stock": 5,
  "remaining_cones_on_sizing_stock": 120,
  "lagat_bags": "45.00",
  "lagat_cones": "1080.00",
  "brand": "Diamond Yarn",
  "width": "63.00",
  "set_length_meter": "12500.00",
  "set_length_gaz": "13670.17",
  "total_tarr": "4800.00",
  "yarn_beam": "YB-SetA",
  "back_beam": "BB-SetA",
  "count": "40/1",
  "total_set_lumbai": "12500.00",
  "total_set_shortage": "2.50",
  "remarks": "Sizing set returned in excellent quality."
}
```

### Example Response: HTTP 201 Created
```json
{
  "success": true,
  "message": "Sizing outcome recorded successfully.",
  "data": {
    "id": 10,
    "sizing": 1,
    "sizingDetail": {
      "id": 1,
      "sizingName": "Standard Sizing Mills",
      "contactPerson": "Ali Khan",
      "phoneNo": "0300-1234567"
    },
    "setNo": "SET-2026-001",
    "sizingName": "Standard Sizing Mills",
    "totalBagsOnSizing": 50,
    "bagPackingCone": 24,
    "totalCones": 1200,
    "remainingBagsOnSizingStock": 5,
    "remainingConesOnSizingStock": 120,
    "lagatBags": "45.00",
    "lagatCones": "1080.00",
    "brand": "Diamond Yarn",
    "width": "63.00",
    "setLengthMeter": "12500.00",
    "setLengthGaz": "13670.17",
    "totalTarr": "4800.00",
    "yarnBeam": "YB-SetA",
    "backBeam": "BB-SetA",
    "count": "40/1",
    "totalSetLumbai": "12500.00",
    "totalSetShortage": "2.50",
    "outcomeDate": "2026-10-03",
    "remarks": "Sizing set returned in excellent quality.",
    "totalBeams": 0,
    "beamAssignments": [],
    "createdBy": { "id": 2, "username": "operator" },
    "createdAt": "2026-10-03T10:30:00Z"
  }
}
```

---

## 4. Beam Loading API Specifications

`BeamLoading` represents: **"Loading the returned Sizing Set onto an existing Beam and installing that Beam onto a Loom."**

### Fields:
- `sizingOutcome` / `sizing_outcome` *(ID, Required)*
- `beam` / `beam_id` *(ID, Required)*: Must refer to an existing Beam whose status is `Available`.
- `loom` / `loom_id` *(ID, Required)*: Must refer to an existing Loom that is not Inactive/Breakdown.
- `warpCount` / `warp_count` *(string)*: Warp yarn count.
- `weftCount` / `weft_count` *(string)*: Weft yarn count.
- `reedWidth` / `reed_width` *(decimal)*: Reed width in inches.
- `pick` / `pick` *(decimal)*: Picks per inch.
- `reedCount` / `reed_count` *(decimal)*: Reed count.
- `pickCount` / `pick_count` *(decimal)*: Pick count.
- `shortage` / `shortage` *(decimal)*: Expected or observed shortage.
- `width` / `width` *(decimal)*: Fabric width in inches.
- `lakhai` / `lakhai` *(decimal)*: Drafting / drawing-in cost.
- `installationDate` / `installation_date` *(YYYY-MM-DD)*: Date beam was mounted on loom.

### 4.1 Load Single Beam
`POST /api/v1/factory/beam-loadings/`

#### Request Payload:
```json
{
  "sizing_outcome": 10,
  "beam": 1,
  "loom": 5,
  "warp_count": "40/1",
  "weft_count": "40/1",
  "reed_width": "63.00",
  "pick": "68.00",
  "reed_count": "72.00",
  "pick_count": "68.00",
  "shortage": "2.50",
  "width": "63.00",
  "lakhai": "450.00",
  "installation_date": "2026-10-03"
}
```

#### Response: HTTP 201 Created
```json
{
  "success": true,
  "message": "Beam 'BEAM-01' loaded successfully onto Loom 'L-101'.",
  "data": {
    "id": 1,
    "sizingOutcome": 10,
    "sizingOutcomeDetail": {
      "id": 10,
      "setNo": "SET-2026-001",
      "sizingName": "Standard Sizing Mills",
      "outcomeDate": "2026-10-03"
    },
    "beam": 1,
    "beamCode": "BEAM-01",
    "beamNumber": "B-101",
    "beamDetail": {
      "id": 1,
      "beamCode": "BEAM-01",
      "beamName": "Warp Beam 1",
      "beamNumber": "B-101",
      "status": "Loaded"
    },
    "loom": 5,
    "loomCode": "L-101",
    "loomNumber": "L-101",
    "loomDetail": {
      "id": 5,
      "loomCode": "L-101",
      "loomName": "Airjet Loom 101",
      "status": "Production"
    },
    "setNo": "SET-2026-001",
    "warpCount": "40/1",
    "weftCount": "40/1",
    "reedWidth": "63.00",
    "pick": "68.00",
    "reedCount": "72.00",
    "pickCount": "68.00",
    "shortage": "2.50",
    "width": "63.00",
    "lakhai": "450.00",
    "installationDate": "2026-10-03",
    "status": "Loaded",
    "totalMetersProduced": "0.00",
    "createdBy": { "id": 2, "username": "operator" },
    "createdAt": "2026-10-03T10:35:00Z"
  }
}
```

### 4.2 Batch Load Multiple Beams for One Sizing Outcome
`POST /api/v1/factory/beam-loadings/batch/`

#### Request Payload:
```json
{
  "sizing_outcome": 10,
  "loadings": [
    {
      "beam_id": 1,
      "loom_id": 1,
      "installation_date": "2026-10-03",
      "warp_count": "40/1",
      "weft_count": "40/1",
      "reed_width": "63.00",
      "pick": "68.00"
    },
    {
      "beam_id": 2,
      "loom_id": 2,
      "installation_date": "2026-10-03",
      "warp_count": "40/1",
      "weft_count": "40/1",
      "reed_width": "63.00",
      "pick": "68.00"
    },
    {
      "beam_id": 3,
      "loom_id": 3,
      "installation_date": "2026-10-03",
      "warp_count": "40/1",
      "weft_count": "40/1",
      "reed_width": "63.00",
      "pick": "68.00"
    }
  ]
}
```

#### Response: HTTP 201 Created
```json
{
  "success": true,
  "message": "Successfully loaded 3 beams for Sizing Set 'SET-2026-001'.",
  "data": [
    { "id": 1, "beamCode": "BEAM-01", "loomCode": "L-101", "status": "Loaded" },
    { "id": 2, "beamCode": "BEAM-02", "loomCode": "L-102", "status": "Loaded" },
    { "id": 3, "beamCode": "BEAM-03", "loomCode": "L-103", "status": "Loaded" }
  ]
}
```

### 4.3 Mark Beam as Empty & Available
`POST /api/v1/factory/beam-loadings/:id/empty/`

When a production cycle completes and the beam is emptied:
1. `Beam.status` automatically updates to `Available`.
2. `BeamLoading.status` updates to `Completed`.
3. `Loom.status` resets to `Active`.
4. The physical Beam is now immediately available in the dropdown for the next Sizing Set.

---

## 5. Production API Specifications

`Production` records cloth/fabric woven daily from a loaded Beam on a Loom.

### Fields:
- `beamLoading` / `beam_loading` *(ID, Required)*: The active BeamLoading record ID.
- `productionDate` / `production_date` *(YYYY-MM-DD, Required)*: Date cloth was woven.
- `metersProduced` / `meters_produced` *(decimal, Required)*: Fabric meters woven.
- `shift` *(string, Optional, default: `"General"`)*: E.g., `"Morning"`, `"Night"`.
- `operatorName` / `operator_name` *(string, Optional)*: Weaver / Loom Master name.
- `remarks` *(string, Optional)*: Quality or break remarks.
- `beamEmptied` / `beam_emptied` *(boolean, Optional, default: `false`)*: Set to `true` on the final cut when the beam is physically empty.

### 5.1 Log Production Entry
`POST /api/v1/factory/productions/`

#### Request Payload:
```json
{
  "beam_loading": 1,
  "production_date": "2026-10-04",
  "meters_produced": "620.50",
  "shift": "Morning",
  "operator_name": "Akram Weaver",
  "remarks": "Smooth weaving, zero warp breaks.",
  "beam_emptied": false
}
```

#### Response: HTTP 201 Created
```json
{
  "success": true,
  "message": "Recorded 620.50 meters of production successfully.",
  "data": {
    "id": 1,
    "beamLoading": 1,
    "beamDetail": {
      "id": 1,
      "beamCode": "BEAM-01",
      "status": "In Production"
    },
    "loomDetail": {
      "id": 5,
      "loomCode": "L-101",
      "status": "Production"
    },
    "productionDate": "2026-10-04",
    "shift": "Morning",
    "metersProduced": "620.50",
    "operatorName": "Akram Weaver",
    "remarks": "Smooth weaving, zero warp breaks.",
    "beamEmptied": false,
    "createdBy": { "id": 2, "username": "operator" },
    "createdAt": "2026-10-04T18:00:00Z"
  }
}
```

> **Automated Lifecycle Trigger:** When `beam_emptied: true` is sent in a production entry, the backend atomically:
> 1. Sets `Beam.status = "Available"` (re-enabled for future sizing sets).
> 2. Sets `BeamLoading.status = "Completed"`.
> 3. Sets `Loom.status = "Active"`.

---

## 6. Beam Reusability & Multi-Cycle History

To view the complete historical log of every sizing set and loom a beam has been loaded onto:

`GET /api/v1/factory/beams/:id/loading-history/`

### Example Response:
```json
{
  "success": true,
  "data": {
    "beamId": 1,
    "beamCode": "BEAM-01",
    "beamNumber": "B-101",
    "currentStatus": "Available",
    "totalLoadings": 2,
    "history": [
      {
        "id": 8,
        "sizingOutcome": 25,
        "setNo": "SET-2026-008",
        "loomCode": "L-104",
        "installationDate": "2026-06-15",
        "status": "Completed",
        "totalMetersProduced": "3200.00"
      },
      {
        "id": 1,
        "sizingOutcome": 10,
        "setNo": "SET-2026-001",
        "loomCode": "L-101",
        "installationDate": "2026-01-10",
        "status": "Completed",
        "totalMetersProduced": "2850.00"
      }
    ]
  }
}
```

---

## 7. Frontend UI Integration Guide (React / TypeScript)

### 7.1 Fetching Available Beams for Sizing Load Form
```typescript
import axios from 'axios';

export interface BeamOption {
  id: number;
  beamCode: string;
  beamNumber: string;
  status: string;
}

export const fetchAvailableBeams = async (): Promise<BeamOption[]> => {
  const token = localStorage.getItem('access_token');
  const response = await axios.get('/api/v1/factory/beams/available/', {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data.data;
};
```

### 7.2 Submitting a Beam Loading
```typescript
export interface LoadBeamPayload {
  sizing_outcome: number;
  beam: number;
  loom: number;
  warp_count?: string;
  weft_count?: string;
  reed_width?: string;
  pick?: string;
  shortage?: string;
  installation_date?: string;
}

export const loadBeamOntoLoom = async (payload: LoadBeamPayload) => {
  const token = localStorage.getItem('access_token');
  const response = await axios.post('/api/v1/factory/beam-loadings/', payload, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data;
};
```

### 7.3 Logging Production with Beam Empty Checkbox
```typescript
export interface ProductionPayload {
  beam_loading: number;
  production_date: string;
  meters_produced: string;
  shift: string;
  operator_name?: string;
  remarks?: string;
  beam_emptied: boolean;
}

export const recordProduction = async (payload: ProductionPayload) => {
  const token = localStorage.getItem('access_token');
  const response = await axios.post('/api/v1/factory/productions/', payload, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.data;
};
```

---

## 8. Common HTTP Error Codes & Resolutions

| HTTP Status | Error Scenario | Resolution |
| :--- | :--- | :--- |
| `400 Bad Request` | `"Beam '...' cannot be loaded because its status is 'Loaded'"` | The beam is currently assigned. Wait until it is emptied, or select a beam whose status is `Available`. |
| `400 Bad Request` | `"Loom '...' already has an active beam mounted on it"` | Dismount / empty the existing beam before loading a new beam on this loom. |
| `400 Bad Request` | `"Duplicate beam IDs detected in the batch loading list"` | Each loading item in a batch must specify a distinct beam ID. |
| `403 Forbidden` | `"You do not have permission to assign beams."` | Current user lacks `beams.assign` permission in ERP RBAC. |
| `403 Forbidden` | `"You do not have permission to log daily production."` | Current user lacks `looms.production` permission in ERP RBAC. |
