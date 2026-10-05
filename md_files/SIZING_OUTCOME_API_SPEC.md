# Sizing Outcome Module – Frontend Developer Integration Guide & API Specification

> **Module:** Yarn – Sizing Management  
> **Base URL:** `http://<host>/api/v1/sizing-outcomes/`  
> **Auth Header:** `Authorization: Bearer <access_jwt_token>`  
> **Content-Type:** `application/json`  
> **Accept:** `application/json`  

---

## 1. Executive Summary & Business Workflow

In the Harmony Factory Suite, the **Sizing Outcome** represents **the return of a completed warp set from the sizing process**.

```
┌─────────────────────────┐
│       Yarn Intake       │ (Raw yarn received from supplier)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       Yarn Outcome      │ (outcome_type = "Sizing", dispatched to Sizing Unit)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      Sizing Outcome     │ (The Set returned from sizing with set_no & set_bill)
└────────────┬────────────┘
             │
             ├── (Assigns 1 or more physical Beams: B-101, B-102...)
             ▼
┌─────────────────────────┐
│  SizingBeamAssignment   │ (Physical Beam status updated to "Sizing")
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│       Beam Loading      │ (Mounting the sized Beam onto a Loom)
└─────────────────────────┘
```

### Key Principles for Frontend Developers:
1. **Direct Link to `YarnOutcome`:** Every `SizingOutcome` is connected to a parent `YarnOutcome` (`yarn_outcome_id` or `yarnOutcomeId`). The Sizing Unit details (`sizingName`, `sizingDetail`) are automatically resolved via this link.
2. **`set_bill` Field:** Captures the Bill / Invoice Number issued by the Sizing Mill for this specific set (e.g. `"SB-1002"`, `"INV-8841"`).
3. **Physical Beam Reuse:** Beams are persistent physical hardware. During creation, the frontend can pass a list of existing available beam IDs in `beam_ids` (or `beamIds`). Beams will automatically transition to status `"Sizing"`.
4. **Dual Case Tolerance:** The backend accepts both `camelCase` and `snake_case` in all request payloads (e.g., `set_bill` or `setBill`, `yarn_outcome_id` or `yarnOutcomeId`, `beam_ids` or `beamIds`). Responses include standardized camelCase aliases alongside relational details.

---

## 2. API Endpoints Overview

| Method | Endpoint | Description | Required Permission |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/sizing-outcomes/` | List sizing outcome sets (paginated, searchable, filterable) | `sizing.view` |
| `POST` | `/api/v1/sizing-outcomes/` | Create a new Sizing Outcome (optionally assign Beams) | `sizing.add` (`beams.assign`) |
| `GET` | `/api/v1/sizing-outcomes/:id/` | Retrieve a single Sizing Outcome by ID with full details | `sizing.view` |
| `PUT` | `/api/v1/sizing-outcomes/:id/` | Full update of a Sizing Outcome | `sizing.edit` |
| `PATCH` | `/api/v1/sizing-outcomes/:id/` | Partial update of a Sizing Outcome | `sizing.edit` |
| `DELETE` | `/api/v1/sizing-outcomes/:id/` | Delete Sizing Outcome (fails if active beam assignments exist) | `sizing.delete` |
| `POST` | `/api/v1/sizing-outcomes/:id/assign-beams/` | Assign additional existing Beams to this Sizing Outcome | `beams.assign` or `sizing.edit` |
| `GET` | `/api/v1/sizing-outcomes/:id/beams/` | Get list of all Beams assigned to this Sizing Outcome | `sizing.view` |
| `POST` | `/api/v1/sizing-outcomes/:id/release-beam/` | Release an assigned Beam back to `Available` status | `beams.assign` or `beams.edit` |

---

## 3. Endpoints Detail

### 3.1 List Sizing Outcomes
**`GET /api/v1/sizing-outcomes/`**

Retrieves a paginated list of all Sizing Outcome records.

#### Query Parameters:
| Parameter | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `page` | integer | Page number (default: `1`) | `?page=1` |
| `page_size` | integer | Items per page (default: `25`, max: `100`) | `?page_size=20` |
| `yarn_outcome` | integer | Filter by parent Yarn Outcome ID | `?yarn_outcome=14` |
| `sizing` | integer | Filter by Sizing Unit ID | `?sizing=2` |
| `set_no` | string | Filter by Sizing Set Number (case-insensitive substring) | `?set_no=SET-102` |
| `set_bill` | string | Filter by Set Bill / Invoice number | `?set_bill=SB-500` |
| `outcome_date` | string (YYYY-MM-DD) | Filter by exact return date | `?outcome_date=2026-10-04` |
| `start_date` | string (YYYY-MM-DD) | Filter outcomes returned on or after date | `?start_date=2026-10-01` |
| `end_date` | string (YYYY-MM-DD) | Filter outcomes returned on or before date | `?end_date=2026-10-31` |
| `search` | string | Text search across set number, set bill, sizing name, remarks | `?search=Al-Karam` |
| `ordering` | string | Sort field (`outcome_date`, `created_at`, prefix `-` for desc) | `?ordering=-outcome_date` |

#### Example Response:
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/v1/sizing-outcomes/?page=2",
  "previous": null,
  "results": [
    {
      "id": 15,
      "yarnOutcome": 8,
      "yarn_outcome": 8,
      "yarnOutcomeId": 8,
      "yarnOutcomeDetail": {
        "id": 8,
        "outcomeType": "Sizing",
        "outcomeBags": 20,
        "yarnName": "Cotton Warp 20/1",
        "yarnType": "Warp",
        "yarnCount": "20/1",
        "intakeSetNo": "INT-440",
        "sizingName": "Star Sizing Mills"
      },
      "sizingDetail": {
        "id": 2,
        "sizingName": "Star Sizing Mills",
        "contactPerson": "Ali Khan",
        "phoneNo": "0300-1234567",
        "status": "Active"
      },
      "setNo": "SET-990",
      "set_no": "SET-990",
      "setBill": "SB-1044",
      "set_bill": "SB-1044",
      "sizingName": "Star Sizing Mills",
      "sizing_name": "Star Sizing Mills",
      "outcomeDate": "2026-10-04",
      "outcome_date": "2026-10-04",
      "totalBagsOnSizing": 20,
      "bagPackingCone": 24,
      "totalCones": 480,
      "remainingBagsOnSizingStock": 2,
      "remainingConesOnSizingStock": 48,
      "lagatBags": "18.00",
      "lagatCones": "432.00",
      "brand": "Indus Mills",
      "width": "68.50",
      "setLengthMeter": "22000.00",
      "setLengthGaz": "24059.49",
      "totalTarr": 3200,
      "yarnBeam": "YB-04",
      "backBeam": "BB-02",
      "count": "20/1",
      "totalSetLumbai": "22000.00",
      "totalSetShortage": "150.00",
      "remarks": "Completed on schedule with minimal shortage",
      "totalBeams": 2,
      "beamAssignments": [
        {
          "id": 21,
          "yarnOutcome": 8,
          "beam": [101, 102],
          "beams": [
            {
              "id": 101,
              "beamName": "Main Warp Beam A",
              "beamNumber": "BN-101",
              "yarnCount": "20/1",
              "warpCount": 3200,
              "totalEnds": 3200,
              "productionOrder": "PO-900"
            },
            {
              "id": 102,
              "beamName": "Main Warp Beam B",
              "beamNumber": "BN-102",
              "yarnCount": "20/1",
              "warpCount": 3200,
              "totalEnds": 3200,
              "productionOrder": "PO-900"
            }
          ],
          "status": "ASSIGNED",
          "assignedAt": "2026-10-04T12:00:00Z",
          "releasedAt": null
        }
      ],
      "createdAt": "2026-10-04T12:00:00Z",
      "updatedAt": "2026-10-04T12:00:00Z",
      "createdBy": {
        "id": 1,
        "username": "admin",
        "fullName": "System Administrator"
      },
      "updatedBy": {
        "id": 1,
        "username": "admin",
        "fullName": "System Administrator"
      }
    }
  ]
}
```

---

### 3.2 Create Sizing Outcome
**`POST /api/v1/sizing-outcomes/`**

Creates a Sizing Outcome record. Existing Beams can be assigned atomically at creation time via `beam_ids` or `beamIds`.

#### Request Payload:
```json
{
  "yarn_outcome_id": 8,
  "set_no": "SET-990",
  "set_bill": "SB-1044",
  "outcome_date": "2026-10-04",
  "sizing_name": "Star Sizing Mills",
  "total_bags_on_sizing": 20,
  "bag_packing_cone": 24,
  "total_cones": 480,
  "remaining_bags_on_sizing_stock": 2,
  "remaining_cones_on_sizing_stock": 48,
  "lagat_bags": 18.00,
  "lagat_cones": 432.00,
  "brand": "Indus Mills",
  "width": 68.50,
  "set_length_meter": 22000.00,
  "set_length_gaz": 24059.49,
  "total_tarr": 3200,
  "yarn_beam": "YB-04",
  "back_beam": "BB-02",
  "count": "20/1",
  "total_set_lumbai": 22000.00,
  "total_set_shortage": 150.00,
  "remarks": "Completed on schedule",
  "beam_ids": [101, 102]
}
```

*(You can also use camelCase keys like `yarnOutcomeId`, `setNo`, `setBill`, `outcomeDate`, `totalBagsOnSizing`, `beamIds`, etc.)*

#### Success Response (`201 Created`):
```json
{
  "success": true,
  "message": "Sizing outcome #15 created successfully with 2 beam(s).",
  "data": {
    "id": 15,
    "yarnOutcome": 8,
    "yarn_outcome": 8,
    "yarnOutcomeId": 8,
    "setNo": "SET-990",
    "set_no": "SET-990",
    "setBill": "SB-1044",
    "set_bill": "SB-1044",
    "sizingName": "Star Sizing Mills",
    "outcomeDate": "2026-10-04",
    "totalBeams": 2,
    "beamAssignments": [ ... ],
    "createdAt": "2026-10-04T12:00:00Z",
    "updatedAt": "2026-10-04T12:00:00Z"
  }
}
```

---

### 3.3 Retrieve Sizing Outcome Details
**`GET /api/v1/sizing-outcomes/:id/`**

Retrieves full specifications, assigned physical beams, and user audit information for a specific Sizing Outcome.

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "data": {
    "id": 15,
    "yarnOutcome": 8,
    "yarnOutcomeId": 8,
    "yarnOutcomeDetail": {
      "id": 8,
      "outcomeType": "Sizing",
      "outcomeBags": 20,
      "yarnName": "Cotton Warp 20/1",
      "yarnType": "Warp",
      "yarnCount": "20/1",
      "intakeSetNo": "INT-440",
      "sizingName": "Star Sizing Mills"
    },
    "setNo": "SET-990",
    "setBill": "SB-1044",
    "sizingName": "Star Sizing Mills",
    "totalBagsOnSizing": 20,
    "bagPackingCone": 24,
    "totalCones": 480,
    "remainingBagsOnSizingStock": 2,
    "remainingConesOnSizingStock": 48,
    "lagatBags": "18.00",
    "lagatCones": "432.00",
    "brand": "Indus Mills",
    "width": "68.50",
    "setLengthMeter": "22000.00",
    "setLengthGaz": "24059.49",
    "totalTarr": 3200,
    "yarnBeam": "YB-04",
    "backBeam": "BB-02",
    "count": "20/1",
    "totalSetLumbai": "22000.00",
    "totalSetShortage": "150.00",
    "outcomeDate": "2026-10-04",
    "remarks": "Completed on schedule",
    "totalBeams": 2,
    "beamAssignments": [ ... ],
    "createdAt": "2026-10-04T12:00:00Z",
    "updatedAt": "2026-10-04T12:00:00Z"
  }
}
```

---

### 3.4 Update Sizing Outcome
**`PUT /api/v1/sizing-outcomes/:id/`** or **`PATCH /api/v1/sizing-outcomes/:id/`**

Updates specifications (such as `set_bill`, `total_set_shortage`, `remarks`, etc.).

#### Example Payload (`PATCH`):
```json
{
  "set_bill": "SB-1044-REV1",
  "total_set_shortage": 140.00,
  "remarks": "Bill updated after final inspection"
}
```

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "message": "Sizing outcome updated successfully.",
  "data": {
    "id": 15,
    "setBill": "SB-1044-REV1",
    "totalSetShortage": "140.00",
    "remarks": "Bill updated after final inspection"
  }
}
```

---

### 3.5 Delete Sizing Outcome
**`DELETE /api/v1/sizing-outcomes/:id/`**

Deletes a sizing outcome record.

> [!CAUTION]
> If the Sizing Outcome has any physical Beams currently in active assignment (`ASSIGNED` or `IN_USE`), deletion will be rejected with `400 Bad Request`. You must release the beams first.

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "message": "Sizing outcome deleted successfully."
}
```

---

### 3.6 Assign Additional Beams
**`POST /api/v1/sizing-outcomes/:id/assign-beams/`**

Assigns additional physical existing Beams to this Sizing Outcome.

#### Request Payload:
```json
{
  "beam_ids": [103, 104]
}
```
*(or `{"beamIds": [103, 104]}`)*

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "message": "Successfully assigned 2 beam(s) to Sizing Outcome #15.",
  "data": {
    "sizingOutcomeId": 15,
    "totalBeamsAssigned": 4,
    "assignments": [
      {
        "id": 22,
        "yarnOutcome": 8,
        "beam": [103, 104],
        "status": "ASSIGNED",
        "assignedAt": "2026-10-04T12:30:00Z"
      }
    ]
  }
}
```

---

### 3.7 List Assigned Beams
**`GET /api/v1/sizing-outcomes/:id/beams/`**

Returns all physical Beams connected to this Sizing Outcome.

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "data": {
    "sizingOutcomeId": 15,
    "outcomeDate": "2026-10-04",
    "totalBeams": 4,
    "assignments": [ ... ]
  }
}
```

---

### 3.8 Release an Assigned Beam
**`POST /api/v1/sizing-outcomes/:id/release-beam/`**

Releases an assigned physical Beam when sizing is complete or unloaded. The physical Beam immediately resets to status `"Available"` in warehouse inventory.

#### Request Payload:
```json
{
  "beam_id": 101
}
```
*(or `{"assignment_id": 21}`)*

#### Success Response (`200 OK`):
```json
{
  "success": true,
  "message": "Beam BN-101 released successfully and marked as Available.",
  "data": {
    "assignmentId": 21,
    "beamId": 101,
    "beamNumber": "BN-101",
    "status": "RELEASED",
    "releasedAt": "2026-10-04T13:00:00Z",
    "beamStatus": "Available"
  }
}
```

---

## 4. Field Dictionary

| Field (camelCase / snake_case) | Type | Required on POST | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| `yarnOutcomeId` / `yarn_outcome_id` | `number` | **Yes** | Foreign key to `YarnOutcome` (outcome_type = 'Sizing') | `8` |
| `setBill` / `set_bill` | `string` | No | Bill or Invoice number from Sizing Mill | `"SB-1044"` |
| `setNo` / `set_no` | `string` | No | Sizing Set number identifier | `"SET-990"` |
| `outcomeDate` / `outcome_date` | `string` (YYYY-MM-DD) | **Yes** | Date set was returned from sizing | `"2026-10-04"` |
| `sizingName` / `sizing_name` | `string` | No | Name of sizing unit (auto-populated if blank) | `"Star Sizing Mills"` |
| `totalBagsOnSizing` / `total_bags_on_sizing` | `number` | No | Total yarn bags sent/processed on sizing | `20` |
| `bagPackingCone` / `bag_packing_cone` | `number` | No | Cones per bag | `24` |
| `totalCones` / `total_cones` | `number` | No | Total cones on sizing (auto: bags * packing) | `480` |
| `remainingBagsOnSizingStock` / `remaining_bags_on_sizing_stock` | `number` | No | Unused yarn bags remaining at sizing mill | `2` |
| `remainingConesOnSizingStock` / `remaining_cones_on_sizing_stock` | `number` | No | Unused cones remaining at sizing mill | `48` |
| `lagatBags` / `lagat_bags` | `number` / `string` | No | Net bags consumed in sizing (Lagat) | `18.00` |
| `lagatCones` / `lagat_cones` | `number` / `string` | No | Net cones consumed in sizing (Lagat) | `432.00` |
| `brand` | `string` | No | Yarn Mill / Brand Name | `"Indus Mills"` |
| `width` | `number` / `string` | No | Fabric / Reed width in inches | `68.50` |
| `setLengthMeter` / `set_length_meter` | `number` / `string` | No | Set length in meters | `22000.00` |
| `setLengthGaz` / `set_length_gaz` | `number` / `string` | No | Set length in yards (gaz) | `24059.49` |
| `totalTarr` / `total_tarr` | `number` | No | Total ends count / Tarr | `3200` |
| `yarnBeam` / `yarn_beam` | `string` | No | Yarn beam count / identifier | `"YB-04"` |
| `backBeam` / `back_beam` | `string` | No | Back beam count / identifier | `"BB-02"` |
| `count` | `string` | No | Yarn Count | `"20/1"` |
| `totalSetLumbai` / `total_set_lumbai` | `number` / `string` | No | Total set length / lumbai | `22000.00` |
| `totalSetShortage` / `total_set_shortage` | `number` / `string` | No | Total set shortage observed | `150.00` |
| `remarks` | `string` | No | Production / delivery notes | `"Clean lot"` |
| `beamIds` / `beam_ids` | `number[]` | No | List of physical Beam IDs to assign upon creation | `[101, 102]` |
| `totalBeams` | `number` | *Read-only* | Count of assigned physical beams | `2` |
| `beamAssignments` | `array` | *Read-only* | Full nested beam assignment history records | `[...]` |
| `createdAt` / `updatedAt` | `ISO Date` | *Read-only* | Audit timestamps | `"2026-10-04T12:00:00Z"` |
| `createdBy` / `updatedBy` | `object` | *Read-only* | User audit details `{ id, username, fullName }` | `{ ... }` |

---

## 5. TypeScript Interfaces

Copy and paste these interfaces directly into your frontend codebase (e.g. `src/types/sizingOutcome.ts`):

```typescript
export interface SizingMin {
  id: number;
  sizingName: string;
  contactPerson: string;
  phoneNo: string;
  status: string;
}

export interface YarnOutcomeMin {
  id: number;
  outcomeType: "Sizing" | "Weft" | "Sold";
  outcomeBags: number;
  yarnName: string;
  yarnType: string;
  yarnCount: string;
  intakeSetNo: string;
  sizingName: string;
}

export interface BeamMin {
  id: number;
  beamName: string;
  beamNumber: string;
  yarnCount: string;
  warpCount: number;
  totalEnds: number;
  productionOrder: string;
}

export interface SizingBeamAssignment {
  id: number;
  yarnOutcome: number;
  beam: number[];
  beams?: BeamMin[];
  status: "ASSIGNED" | "IN_USE" | "COMPLETED" | "RELEASED";
  assignedAt: string;
  releasedAt: string | null;
}

export interface SizingOutcome {
  id: number;
  yarnOutcome: number;
  yarnOutcomeId: number;
  yarnOutcomeDetail?: YarnOutcomeMin;
  sizingDetail?: SizingMin;
  setNo: string;
  setBill: string;
  sizingName: string;
  totalBagsOnSizing: number;
  bagPackingCone: number;
  totalCones: number;
  remainingBagsOnSizingStock: number;
  remainingConesOnSizingStock: number;
  lagatBags: string;
  lagatCones: string;
  brand: string;
  width: string | null;
  setLengthMeter: string | null;
  setLengthGaz: string | null;
  totalTarr: number | null;
  yarnBeam: string;
  backBeam: string;
  count: string;
  totalSetLumbai: string | null;
  totalSetShortage: string | null;
  outcomeDate: string;
  remarks: string;
  totalBeams: number;
  beamAssignments: SizingBeamAssignment[];
  createdAt: string;
  updatedAt: string;
  createdBy?: { id: number; username: string; fullName: string };
  updatedBy?: { id: number; username: string; fullName: string };
}

export interface CreateSizingOutcomePayload {
  yarnOutcomeId: number; // or yarn_outcome_id
  setBill?: string;      // or set_bill
  setNo?: string;        // or set_no
  outcomeDate: string;   // YYYY-MM-DD
  sizingName?: string;
  totalBagsOnSizing?: number;
  bagPackingCone?: number;
  totalCones?: number;
  remainingBagsOnSizingStock?: number;
  remainingConesOnSizingStock?: number;
  lagatBags?: number | string;
  lagatCones?: number | string;
  brand?: string;
  width?: number | string;
  setLengthMeter?: number | string;
  setLengthGaz?: number | string;
  totalTarr?: number;
  yarnBeam?: string;
  backBeam?: string;
  count?: string;
  totalSetLumbai?: number | string;
  totalSetShortage?: number | string;
  remarks?: string;
  beamIds?: number[];    // or beam_ids
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

---

## 6. Frontend Service Implementation (Axios Example)

Create a service file (e.g. `src/services/sizingOutcomeService.ts`):

```typescript
import axios from "axios";
import {
  SizingOutcome,
  CreateSizingOutcomePayload,
  PaginatedResponse,
} from "@/types/sizingOutcome";

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
});

// Attach JWT token automatically
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("accessToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const sizingOutcomeService = {
  // 1. List with filters
  list: async (params?: Record<string, any>): Promise<PaginatedResponse<SizingOutcome>> => {
    const res = await API.get("/sizing-outcomes/", { params });
    return res.data;
  },

  // 2. Retrieve by ID
  getById: async (id: number): Promise<SizingOutcome> => {
    const res = await API.get(`/sizing-outcomes/${id}/`);
    return res.data.data;
  },

  // 3. Create Outcome with optional Beams
  create: async (payload: CreateSizingOutcomePayload): Promise<SizingOutcome> => {
    const res = await API.post("/sizing-outcomes/", payload);
    return res.data.data;
  },

  // 4. Update Outcome
  update: async (id: number, payload: Partial<CreateSizingOutcomePayload>): Promise<SizingOutcome> => {
    const res = await API.patch(`/sizing-outcomes/${id}/`, payload);
    return res.data.data;
  },

  // 5. Delete Outcome
  delete: async (id: number): Promise<void> => {
    await API.delete(`/sizing-outcomes/${id}/`);
  },

  // 6. Assign Beams to an existing Outcome
  assignBeams: async (outcomeId: number, beamIds: number[]) => {
    const res = await API.post(`/sizing-outcomes/${outcomeId}/assign-beams/`, {
      beam_ids: beamIds,
    });
    return res.data;
  },

  // 7. Get Beams assigned to an Outcome
  getAssignedBeams: async (outcomeId: number) => {
    const res = await API.get(`/sizing-outcomes/${outcomeId}/beams/`);
    return res.data.data;
  },

  // 8. Release a Beam
  releaseBeam: async (outcomeId: number, beamId: number) => {
    const res = await API.post(`/sizing-outcomes/${outcomeId}/release-beam/`, {
      beam_id: beamId,
    });
    return res.data;
  },
};
```

---

## 7. Error Handling & Validation Rules

All error responses from the backend follow this predictable structure:

```json
{
  "yarnOutcomeId": ["Yarn outcome with ID 99 does not exist."],
  "outcomeDate": ["outcomeDate (or outcome_date) is required."]
}
```

Or for permission issues:
```json
{
  "detail": "You do not have permission to perform this action."
}
```

Or for deletion with active assignments:
```json
{
  "success": false,
  "message": "Cannot delete sizing outcome with active beam assignments. Release or complete assignments first."
}
```

### Physical Beam Status Requirement:
> [!IMPORTANT]
> **Physical Beams Assigned to Sizing Outcomes Must Have Status `"Sizing"`**:
> When recording a Sizing Outcome (return of a set from Sizing), physical beams provided in `beam_ids` (or via `/assign-beams/`) must currently have status `"Sizing"`.
> - If an `"Available"`, `"Loaded"`, or other status beam is submitted, the API will reject it with:
>   `"Beam '<number>' cannot be assigned because its status is '<status>'. Only 'Sizing' beams can be assigned."`
> - Beams with an active assignment cannot be assigned to another outcome until released.
