# Yarn, Sizing & Reusable Beam Assignment Workflow API Specification
### Frontend Developer Integration Guide

> **For:** Frontend Engineering Team  
> **Base URL:** `http://<host>/api/v1/`  
> **Auth:** Every request requires an HTTP header: `Authorization: Bearer <token>`  
> **Content-Type:** `application/json`  
> **Module Scope:** Yarn Intake, Yarn Outcome, Sizing Units, Sizing Outcomes, and Reusable Beam Assignment & Lifecycle

---

## 1. Executive Workflow & Architecture

This power loom factory management system tracks the complete lifecycle from raw yarn intake to sizing and weaving machine beams:

```
[ Yarn Supplier ]
       │
       ▼
 [ YarnIntake ] (Raw yarn received into warehouse stock)
       │
       ├───────────────────┬───────────────────┐
       ▼                   ▼                   ▼
 [ YarnOutcome ]     [ YarnOutcome ]     [ YarnOutcome ]
(outcomeType: Sizing) (outcomeType: Weft) (outcomeType: Sold)
       │
       ▼
   [ Sizing ] (Sizing mill/party managing sizing process)
       │
       ▼
 [ SizingOutcome ] (Identifiable sizing operation / lot / cycle)
       │
       ▼ (Assign one, two, or multiple EXISTING physical Beams)
 [ SizingBeamAssignment ] ───► Connects physical [ Beam ] to SizingOutcome
       │                        (Beam status transitions: Available ──► Sizing)
       ▼
 [ Loom Production ] (Beam mounted on loom: Loaded ──► In Production ──► Completed)
       │
       ▼
[ Release Beam ] ───► Assignment status: RELEASED (releasedAt timestamp recorded)
                      Beam status: AVAILABLE again for new sizing operation
                      Historical records permanently preserved!
```

### Key Business Rules for Frontend Developers:
1. **Never create new Beams during sizing assignment**: Always select from existing available Beams (`status === "Available"`).
2. **Multiple Beams per SizingOutcome**: A sizing operation can yield 1, 2, 4, or more wound beams.
3. **Beam Reusability**: A physical beam is a reusable hardware asset. When emptied after production, it is released back to `Available` and can be assigned to a new sizing cycle with new yarn.
4. **Single Active Assignment**: A physical Beam can have only **one** active sizing assignment (`ASSIGNED` or `IN_USE`) at any given time.
5. **Permanent Audit History**: Sizing cycles are never overwritten or deleted upon reuse. Full history is accessible via `/api/v1/factory/beams/:id/sizing-history/`.

---

## 2. Global Authentication & Response Envelope

### Headers
```http
Authorization: Bearer <access_jwt_token>
Content-Type: application/json
Accept: application/json
```

### Unified Success Response (`200 OK` / `201 Created`)
```json
{
  "success": true,
  "message": "Action completed successfully.",
  "data": { ... }
}
```

### Unified Error Response (`400 Bad Request` / `403 Forbidden` / `404 Not Found`)
```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "beam_ids": [
      "Beam 'B-001' already has an active sizing assignment (Assignment #4)."
    ]
  }
}
```

---

## 3. Quick Reference – All Endpoints

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| **Yarn Intake** | | | |
| `GET` | `/api/v1/yarn-intakes/` | List yarn intakes (paginated, filterable) | `yarn_intake.view` |
| `POST` | `/api/v1/yarn-intakes/` | Record new yarn arrival from supplier | `yarn_intake.add` |
| `GET` | `/api/v1/yarn-intakes/:id/` | Get single yarn intake details & stock balance | `yarn_intake.view` |
| `PUT/PATCH`| `/api/v1/yarn-intakes/:id/` | Update yarn intake entry | `yarn_intake.edit` |
| `DELETE` | `/api/v1/yarn-intakes/:id/` | Delete intake (only if no dispatched outcomes) | `yarn_intake.delete` |
| `GET` | `/api/v1/yarn-intakes/stats/`| Aggregated warehouse yarn stock statistics | `yarn_intake.view` |
| **Yarn Outcome** | | | |
| `GET` | `/api/v1/yarn-outcomes/` | List yarn outcome dispatches | `yarn_outcome.view` |
| `POST` | `/api/v1/yarn-outcomes/` | Dispatch yarn (Sizing, Weft, Sold) | `yarn_outcome.add` |
| `GET` | `/api/v1/yarn-outcomes/:id/`| Get single dispatch details | `yarn_outcome.view` |
| `PUT/PATCH`| `/api/v1/yarn-outcomes/:id/`| Update dispatch details | `yarn_outcome.edit` |
| `DELETE` | `/api/v1/yarn-outcomes/:id/`| Delete dispatch and restore intake stock balance | `yarn_outcome.delete` |
| **Sizing Units** | | | |
| `GET` | `/api/v1/sizings/` | List sizing mills / parties | `sizing.view` |
| `POST` | `/api/v1/sizings/` | Register new sizing unit | `sizing.add` |
| `GET` | `/api/v1/sizings/:id/` | Get sizing unit details | `sizing.view` |
| `PUT/PATCH` | `/api/v1/sizings/:id/` | Replace or partially update a sizing unit | `sizing.edit` |
| `DELETE` | `/api/v1/sizings/:id/` | Delete a sizing unit (blocked when protected outcome records reference it) | `sizing.delete` |
| `GET` | `/api/v1/sizings/choices/` | Minimal dropdown list of active sizing units | `sizing.view` |
| `GET` | `/api/v1/sizings/:id/outcomes/`| List all Sizing Outcomes for a sizing mill | `sizing.view` |
| **Sizing Outcomes & Beam Assignment** | | | |
| `GET` | `/api/v1/sizing-outcomes/` | List sizing outcomes (filter by sizing, date) | `sizing.view` |
| `POST` | `/api/v1/sizing-outcomes/` | Create outcome + optionally assign multiple Beams | `sizing.add` & `beams.assign` |
| `GET` | `/api/v1/sizing-outcomes/:id/` | Get outcome details with all assigned beams | `sizing.view` |
| `PUT/PATCH`| `/api/v1/sizing-outcomes/:id/`| Update outcome remarks or date | `sizing.edit` |
| `DELETE` | `/api/v1/sizing-outcomes/:id/`| Delete outcome (only if no active assignments) | `sizing.delete` |
| `POST` | `/api/v1/sizing-outcomes/:id/assign-beams/` | Assign additional existing Beams to outcome | `beams.assign` |
| `GET` | `/api/v1/sizing-outcomes/:id/beams/` | List all beams currently assigned to outcome | `sizing.view` |
| `POST` | `/api/v1/sizing-outcomes/:id/release-beam/` | Release an assigned beam from this outcome | `beams.assign` |
| **Assignment Lifecycle & Transitions** | | | |
| `GET` | `/api/v1/sizing-beam-assignments/` | List assignments (filter by beam, outcome, status) | `beams.view` |
| `GET` | `/api/v1/sizing-beam-assignments/:id/` | Get single assignment record | `beams.view` |
| `POST` | `/api/v1/sizing-beam-assignments/:id/transition/` | Advance status (`IN_USE`, `COMPLETED`) | `beams.assign` |
| `POST` | `/api/v1/sizing-beam-assignments/:id/release/` | Release assignment & mark physical beam Available | `beams.assign` |
| **Beam Sizing History & Available Beams** | | | |
| `GET` | `/api/v1/factory/beams/available/` | Get currently Available beams for sizing selector | `beams.view` |
| `GET` | `/api/v1/factory/beams/:id/sizing-history/` | Complete history of sizing cycles for a Beam | `beams.view` |
| `GET` | `/api/v1/factory/beams/:id/active-assignment/`| Current active sizing assignment of a Beam (or null) | `beams.view` |
| `POST` | `/api/v1/factory/beams/:id/release/` | Direct release of beam's active assignment | `beams.assign` |

---

## 4. Yarn Intake & Outcome Specifications

### 4.1 Record Yarn Intake
```http
POST /api/v1/yarn-intakes/
```
#### Request Payload
```json
{
  "yarnName": "Cotton Warp 20/1",
  "yarnType": "Warp",
  "yarnCount": "20/1",
  "setNo": "SET-2026-08",
  "supplier": 3,
  "bags": 100,
  "conesPerBag": 24,
  "weightPerBagKg": "45.360",
  "ratePerBag": "18500.00",
  "intakeDate": "2026-10-01",
  "notes": "Premium quality carded yarn"
}
```
#### Backend Calculations (Automatic):
* `netWeightKg` = `bags` * `weightPerBagKg`
* `netWeightLb` = `netWeightKg` * 2.20462262
* `totalRate` = `bags` * `ratePerBag`
* `remainingBags` initialized to `bags`

---

### 4.2 Dispatch Yarn Outcome
```http
POST /api/v1/yarn-outcomes/
```

#### Outcome Type Rules:
* **`Sizing`**: `sizing` foreign key is **REQUIRED**. `yarnBuyer` must be `null`. `totalPrice` must be `0`.
* **`Weft`**: `yarnBuyer` must be `null`. `sizing` must be `null`. `totalPrice` must be `0`.
* **`Sold`**: `yarnBuyer` is **REQUIRED**. `totalPrice` must be `> 0`. `sizing` must be `null`.

#### Request Payload (Dispatch to Sizing Unit)
```json
{
  "yarnIntake": 12,
  "outcomeType": "Sizing",
  "outcomeBags": 40,
  "outcomeConesPerBag": 24,
  "outcomeWeightPerBagKg": "45.360",
  "sizing": 5,
  "outcomeDate": "2026-10-02",
  "notes": "Sent 40 bags to Star Sizing for Set #8"
}
```

#### Response `201 Created`
```json
{
  "success": true,
  "message": "Yarn outcome recorded successfully.",
  "data": {
    "id": 88,
    "yarnIntake": 12,
    "outcomeType": "Sizing",
    "outcomeBags": 40,
    "outcomeWeightKg": "1814.400",
    "outcomeWeightLb": "3999.999",
    "sizing": 5,
    "sizingDetail": {
      "id": 5,
      "sizingName": "Star Sizing Mills",
      "contactPerson": "Ali Khan"
    },
    "outcomeDate": "2026-10-02"
  }
}
```

---

## 5. Sizing Units API

### 5.1 Dropdown Choices for Forms
```http
GET /api/v1/sizings/choices/
```
#### Response `200 OK`
```json
{
  "success": true,
  "data": [
    { "value": 1, "label": "Star Sizing Mills", "contactPerson": "Ali Khan" },
    { "value": 2, "label": "National Sizing Co.", "contactPerson": "Zahid Mehmood" }
  ]
}
```

---

## 6. Sizing Outcome & Beam Assignment API

### 6.1 Get Available Beams (For Sizing Assignment Dropdown/Selector)
Returns physical beams that are currently `Available` and not locked or in production.

```http
GET /api/v1/factory/beams/available/
```
#### Query Parameters (Optional)
| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `search` | string | `"B-001"` | Searches beam code, number, yarn count |
| `yarn_count` | string | `"20/1"` | Filter by yarn count |
| `page` | number | `1` | Pagination page number |
| `page_size`| number | `50` | Default 10, max 100 |

#### Response `200 OK`
```json
{
  "success": true,
  "count": 4,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 50,
  "results": [
    {
      "id": 101,
      "beamCode": "B-001",
      "beamName": "Main Warp Beam 1",
      "beamNumber": "BN-10001",
      "yarnCount": "20/1",
      "warpCount": 2400,
      "totalEnds": 2400,
      "status": "Available"
    },
    {
      "id": 102,
      "beamCode": "B-002",
      "beamName": "Main Warp Beam 2",
      "beamNumber": "BN-10002",
      "yarnCount": "20/1",
      "warpCount": 2400,
      "totalEnds": 2400,
      "status": "Available"
    }
  ]
}
```

---

### 6.2 Create Sizing Outcome and Assign Multiple Beams
Atomically creates a SizingOutcome and assigns one or more existing Beams.

```http
POST /api/v1/sizing-outcomes/
```

#### Request Payload
Both camelCase (`sizingId`, `outcomeDate`, `beamIds`) and snake_case (`sizing_id`, `outcome_date`, `beam_ids`) are supported.

```json
{
  "sizing_id": 5,
  "outcome_date": "2026-10-03",
  "beam_ids": [101, 102, 103, 104],
  "remarks": "4 existing beams sized from Cotton 20/1 lot"
}
```

#### Response `201 Created`
```json
{
  "success": true,
  "message": "Sizing outcome #25 created successfully with 4 beam(s).",
  "data": {
    "id": 25,
    "sizing": 5,
    "sizingDetail": {
      "id": 5,
      "sizingName": "Star Sizing Mills",
      "contactPerson": "Ali Khan",
      "phoneNo": "0300-1234567",
      "status": "Active"
    },
    "outcomeDate": "2026-10-03",
    "remarks": "4 existing beams sized from Cotton 20/1 lot",
    "totalBeams": 4,
    "beamAssignments": [
      {
        "id": 1,
        "sizingOutcomeId": 25,
        "beamId": 101,
        "beam": {
          "id": 101,
          "beamCode": "B-001",
          "beamName": "Main Warp Beam 1",
          "beamNumber": "BN-10001",
          "yarnCount": "20/1",
          "status": "Sizing"
        },
        "status": "ASSIGNED",
        "assignedAt": "2026-10-03T09:30:00Z",
        "releasedAt": null
      },
      {
        "id": 2,
        "sizingOutcomeId": 25,
        "beamId": 102,
        "beam": {
          "id": 102,
          "beamCode": "B-002",
          "beamName": "Main Warp Beam 2",
          "beamNumber": "BN-10002",
          "yarnCount": "20/1",
          "status": "Sizing"
        },
        "status": "ASSIGNED",
        "assignedAt": "2026-10-03T09:30:00Z",
        "releasedAt": null
      }
    ],
    "createdAt": "2026-10-03T09:30:00Z",
    "updatedAt": "2026-10-03T09:30:00Z"
  }
}
```

#### Error Response: Beam Unavailable / Double Assignment (`400 Bad Request`)
```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "beam_ids": [
      "Beam 'B-001' already has an active sizing assignment (Assignment #1 in Outcome #25)."
    ]
  }
}
```

---

### 6.3 Add Additional Beams to an Existing Sizing Outcome
Use this when more beams are finished or added to an existing outcome record.

```http
POST /api/v1/sizing-outcomes/:id/assign-beams/
```

#### Request Payload
```json
{
  "beam_ids": [105, 106]
}
```

#### Response `200 OK`
```json
{
  "success": true,
  "message": "Successfully assigned 2 beam(s) to Sizing Outcome #25.",
  "data": {
    "sizingOutcomeId": 25,
    "totalBeamsAssigned": 6,
    "assignments": [
      {
        "id": 5,
        "sizingOutcomeId": 25,
        "beamId": 105,
        "beam": { "id": 105, "beamCode": "B-005", "status": "Sizing" },
        "status": "ASSIGNED",
        "assignedAt": "2026-10-03T11:00:00Z"
      },
      {
        "id": 6,
        "sizingOutcomeId": 25,
        "beamId": 106,
        "beam": { "id": 106, "beamCode": "B-006", "status": "Sizing" },
        "status": "ASSIGNED",
        "assignedAt": "2026-10-03T11:00:00Z"
      }
    ]
  }
}
```

---

### 6.4 List Beams for a Sizing Outcome
```http
GET /api/v1/sizing-outcomes/:id/beams/
```

#### Response `200 OK`
```json
{
  "success": true,
  "data": {
    "sizingOutcomeId": 25,
    "outcomeDate": "2026-10-03",
    "totalBeams": 4,
    "assignments": [
      {
        "id": 1,
        "sizingOutcomeId": 25,
        "beamId": 101,
        "beam": {
          "id": 101,
          "beamCode": "B-001",
          "beamName": "Main Beam 1",
          "beamNumber": "BN-10001",
          "status": "Sizing"
        },
        "status": "ASSIGNED",
        "assignedAt": "2026-10-03T09:30:00Z",
        "releasedAt": null
      }
    ]
  }
}
```

---

### 6.5 Release an Assigned Beam from a Sizing Outcome
Releases a beam from its sizing assignment, marks the physical beam as `Available`, and preserves the historical record.

```http
POST /api/v1/sizing-outcomes/:id/release-beam/
```

#### Request Payload
Accepts either `beam_id` or `assignment_id`:
```json
{
  "beam_id": 101
}
```

#### Response `200 OK`
```json
{
  "success": true,
  "message": "Beam 'B-001' has been released and is now Available.",
  "data": {
    "id": 1,
    "sizingOutcomeId": 25,
    "beamId": 101,
    "beam": {
      "id": 101,
      "beamCode": "B-001",
      "status": "Available"
    },
    "status": "RELEASED",
    "assignedAt": "2026-10-03T09:30:00Z",
    "releasedAt": "2026-10-07T14:15:00Z"
  }
}
```

---

## 7. Beam Lifecycle & Reusability Management

### 7.1 Status Lifecycle Matrix

```
       Physical Beam Status                       Assignment Status
   ─────────────────────────────              ─────────────────────────
             AVAILABLE                               (No active assignment)
                 │
                 ▼ [Assigned to Sizing Outcome]
              SIZING                     ───────►            ASSIGNED
                 │
                 ▼ [Mounted on Loom]
              LOADED                     ───────►            IN_USE
                 │
                 ▼ [Weaving in Progress]
           IN_PRODUCTION                 ───────►            IN_USE
                 │
                 ▼ [Fabric Cut Completed]
             COMPLETED                   ───────►           COMPLETED
                 │
                 ▼ [Empty Beam Released]
             AVAILABLE                   ◄───────            RELEASED
                 │                                     (releasedAt set)
                 ▼
          [ READY FOR REUSE ]
      (Can be assigned to new sizing)
```

> **Important**: You cannot set a Beam's status directly to `Available` via `PATCH /api/v1/factory/beams/:id/` if it has an active sizing assignment. You must call the `release` endpoint!

---

### 7.2 Transition Beam Assignment Status
Advance assignment as production progresses:

```http
POST /api/v1/sizing-beam-assignments/:id/transition/
```

#### Request Payload
```json
{
  "status": "IN_USE"
}
```
*Valid `status` choices:* `"IN_USE"`, `"COMPLETED"`, `"RELEASED"`

#### Response `200 OK`
```json
{
  "success": true,
  "message": "Assignment #1 transitioned to 'IN_USE'.",
  "data": {
    "id": 1,
    "sizingOutcomeId": 25,
    "beamId": 101,
    "status": "IN_USE",
    "beam": {
      "id": 101,
      "beamCode": "B-001",
      "status": "Loaded"
    }
  }
}
```

---

### 7.3 Direct Release via Beam ID
```http
POST /api/v1/factory/beams/:id/release/
```
#### Response `200 OK`
```json
{
  "success": true,
  "message": "Beam 'B-001' has been released and is now Available.",
  "data": {
    "id": 1,
    "sizingOutcomeId": 25,
    "beamId": 101,
    "status": "RELEASED",
    "assignedAt": "2026-10-03T09:30:00Z",
    "releasedAt": "2026-10-07T14:15:00Z"
  }
}
```

---

### 7.4 Get Current Active Assignment for a Beam
Check whether a beam is currently assigned or in use.

```http
GET /api/v1/factory/beams/:id/active-assignment/
```

#### Response when Beam is assigned:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "sizingOutcomeId": 25,
    "beamId": 101,
    "status": "ASSIGNED",
    "assignedAt": "2026-10-03T09:30:00Z",
    "releasedAt": null
  }
}
```

#### Response when Beam is Available (empty):
```json
{
  "success": true,
  "data": null,
  "message": "Beam 'B-001' has no active sizing assignment."
}
```

---

### 7.5 Get Complete Sizing History of a Beam
Returns the audit trail of all sizing cycles this physical beam has undergone over its operational lifetime.

```http
GET /api/v1/factory/beams/:id/sizing-history/
```

#### Response `200 OK`
```json
{
  "success": true,
  "data": {
    "beamId": 101,
    "beamCode": "B-001",
    "beamNumber": "BN-10001",
    "currentStatus": "Available",
    "totalSizingCycles": 2,
    "history": [
      {
        "assignmentId": 35,
        "status": "RELEASED",
        "assignedAt": "2026-10-15T08:00:00Z",
        "releasedAt": "2026-10-20T16:30:00Z",
        "sizingOutcome": {
          "id": 40,
          "outcomeDate": "2026-10-15",
          "remarks": "Cycle 2: 24/1 Cotton warp",
          "sizing": {
            "id": 5,
            "sizingName": "Star Sizing Mills",
            "contactPerson": "Ali Khan",
            "phoneNo": "0300-1234567"
          },
          "dispatchedYarns": [
            {
              "id": 92,
              "yarnName": "Cotton 24/1 Combed",
              "yarnCount": "24/1",
              "outcomeBags": 50,
              "outcomeWeightKg": "2268.000",
              "outcomeDate": "2026-10-14"
            }
          ]
        }
      },
      {
        "assignmentId": 1,
        "status": "RELEASED",
        "assignedAt": "2026-10-03T09:30:00Z",
        "releasedAt": "2026-10-07T14:15:00Z",
        "sizingOutcome": {
          "id": 25,
          "outcomeDate": "2026-10-03",
          "remarks": "Cycle 1: 20/1 Cotton warp",
          "sizing": {
            "id": 5,
            "sizingName": "Star Sizing Mills",
            "contactPerson": "Ali Khan",
            "phoneNo": "0300-1234567"
          },
          "dispatchedYarns": [
            {
              "id": 88,
              "yarnName": "Cotton Warp 20/1",
              "yarnCount": "20/1",
              "outcomeBags": 40,
              "outcomeWeightKg": "1814.400",
              "outcomeDate": "2026-10-02"
            }
          ]
        }
      }
    ]
  }
}
```

---

## 8. Frontend Axios / TypeScript Integration Examples

### 8.1 API Client Setup (`api/sizing.ts`)

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 1. Fetch available beams for assignment selector
export const getAvailableBeams = async (search?: string) => {
  const response = await api.get('/factory/beams/available/', {
    params: { search, page_size: 100 },
  });
  return response.data.results || response.data.data;
};

// 2. Create Sizing Outcome and assign multiple Beams
export interface CreateSizingOutcomePayload {
  sizing_id: number;
  outcome_date: string;
  beam_ids: number[];
  remarks?: string;
}

export const createSizingOutcome = async (payload: CreateSizingOutcomePayload) => {
  const response = await api.post('/sizing-outcomes/', payload);
  return response.data;
};

// 3. Add more beams to an existing Sizing Outcome
export const addBeamsToOutcome = async (outcomeId: number, beamIds: number[]) => {
  const response = await api.post(`/sizing-outcomes/${outcomeId}/assign-beams/`, {
    beam_ids: beamIds,
  });
  return response.data;
};

// 4. Release a Beam when empty
export const releaseBeam = async (beamId: number) => {
  const response = await api.post(`/factory/beams/${beamId}/release/`);
  return response.data;
};

// 5. Get Beam Sizing History
export const getBeamSizingHistory = async (beamId: number) => {
  const response = await api.get(`/factory/beams/${beamId}/sizing-history/`);
  return response.data.data;
};

// 6. Get Beam Active Assignment
export const getBeamActiveAssignment = async (beamId: number) => {
  const response = await api.get(`/factory/beams/${beamId}/active-assignment/`);
  return response.data.data;
};
```

### 8.2 Frontend Modal Component Flow (React / Next.js)

```tsx
import React, { useState, useEffect } from 'react';
import { getAvailableBeams, createSizingOutcome } from '@/api/sizing';

export function SizingOutcomeModal({ sizingId, onSuccess, onClose }) {
  const [availableBeams, setAvailableBeams] = useState([]);
  const [selectedBeamIds, setSelectedBeamIds] = useState<number[]>([]);
  const [outcomeDate, setOutcomeDate] = useState(new Date().toISOString().slice(0, 10));
  const [remarks, setRemarks] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAvailableBeams().then(setAvailableBeams).catch(console.error);
  }, []);

  const handleToggleBeam = (beamId: number) => {
    setSelectedBeamIds((prev) =>
      prev.includes(beamId) ? prev.filter((id) => id !== beamId) : [...prev, beamId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedBeamIds.length === 0) {
      setError('Please select at least one available beam to assign.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await createSizingOutcome({
        sizing_id: sizingId,
        outcome_date: outcomeDate,
        beam_ids: selectedBeamIds,
        remarks,
      });
      onSuccess();
    } catch (err: any) {
      const msg = err.response?.data?.errors?.beam_ids?.[0] ||
                  err.response?.data?.message || 'Assignment failed.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal-content">
        <h2>Assign Beams to Sizing Outcome</h2>
        {error && <div className="error-alert">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>Outcome Date</label>
          <input
            type="date"
            value={outcomeDate}
            onChange={(e) => setOutcomeDate(e.target.value)}
            required
          />

          <label>Select Beams to Assign ({selectedBeamIds.length} selected)</label>
          <div className="beam-selector-grid">
            {availableBeams.map((beam: any) => (
              <div
                key={beam.id}
                className={`beam-card ${selectedBeamIds.includes(beam.id) ? 'selected' : ''}`}
                onClick={() => handleToggleBeam(beam.id)}
              >
                <strong>{beam.beamCode}</strong>
                <span>{beam.beamNumber}</span>
                <small>{beam.yarnCount} | Ends: {beam.totalEnds}</small>
              </div>
            ))}
          </div>

          <label>Remarks</label>
          <textarea
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Operational notes, set cuts, etc."
          />

          <div className="modal-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={loading}>
              {loading ? 'Assigning...' : `Assign ${selectedBeamIds.length} Beam(s)`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
```

---

## 9. Error Codes Reference Guide

| Error Response | Cause | Resolution for User |
|----------------|-------|---------------------|
| `"Beam with ID X does not exist."` | Invalid beam ID in `beam_ids` list | Check beam list and send valid IDs |
| `"Duplicate beam IDs submitted: [X]."` | Same beam ID provided multiple times in request | Filter duplicate IDs before submitting |
| `"Beam 'B-001' cannot be assigned because its status is 'Damaged'."` | Selected beam is not in `Available` state | Select only beams from `/factory/beams/available/` |
| `"Beam 'B-001' already has an active sizing assignment."` | Beam is currently assigned in another outcome | Release the beam first once it has been emptied |
| `"Cannot set beam status directly to 'Available' while it has an active sizing assignment."` | Direct update attempted via `PATCH /beams/:id/` | Use the dedicated `POST /beams/:id/release/` endpoint |
| `"Sizing reference is required for Sizing outcome type."` | Yarn dispatched with `outcomeType: Sizing` without `sizing` ID | Select a Sizing Unit dropdown item |
| `"Sizing must be null for Weft/Sold outcome type."` | `sizing` ID passed when dispatching Weft or Sold yarn | Leave `sizing` as `null` for Weft and Sold |
| `"You do not have permission to assign beams."` | User lacks `beams.assign` permission | Contact ERP administrator to assign permission |
