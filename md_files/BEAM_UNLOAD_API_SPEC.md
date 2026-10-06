# Beam Unload & Empty API Specification
## Frontend Developer Integration Guide

> **Base URL:** `http://<host>/api/v1/factory/` or `http://<host>/api/v1/`  
> **Auth:** Required `Authorization: Bearer <access_jwt_token>`  
> **Content-Type:** `application/json`  
> **Accept:** `application/json`  

---

## 1. Overview & Business Workflow

In the factory system, a **Beam** is loaded onto a **Loom** via a `BeamLoading` record. Once the fabric has finished weaving or the beam runs out of yarn, it must be **unloaded / emptied**.

### Status Transitions Upon Unloading:
| Entity | Previous Status | New Status | Description |
| :--- | :--- | :--- | :--- |
| **Beam** | `In Production` / `Loaded` | **`Available`** | The physical beam is now empty and can be reused in future sizing sets. |
| **Loom** | `Production` | **`Active`** | The loom is freed and ready to receive a new loaded beam. |
| **BeamLoading** | `In Production` / `Loaded` | **`Completed`** | The loading cycle is closed. Full historical records remain intact. |

---

## 2. Primary API: Unload / Empty Beam

Use this endpoint when manually unloading a beam from a loom or marking it empty from the UI.

### **Endpoint Details**
* **Method:** `POST`
* **URL:** `/api/v1/factory/beam-loadings/{id}/empty/`  
  *(Also available at `/api/v1/beam-loadings/{id}/empty/`)*  
  *(Replace `{id}` with the `BeamLoading` ID)*
* **Permission:** User must be Superuser OR possess `beams.assign` or `looms.production` permission.
* **Request Body:** None required (send `{}`).

---

### **Request Example**

#### **cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/factory/beam-loadings/15/empty/" \
     -H "Authorization: Bearer <your_access_token>" \
     -H "Content-Type: application/json" \
     -d "{}"
```

#### **Frontend (JavaScript / Axios):**
```typescript
import axios from "axios";

export const unloadBeamFromLoom = async (beamLoadingId: number, token: string) => {
  const response = await axios.post(
    `/api/v1/factory/beam-loadings/${beamLoadingId}/empty/`,
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    }
  );
  return response.data;
};
```

---

### **Responses**

#### **Success Response (`200 OK`)**
```json
{
  "success": true,
  "message": "Beam 'BM-204' has been emptied and is now AVAILABLE for new sizing sets.",
  "data": {
    "id": 15,
    "beam": 8,
    "beamNumber": "BM-204",
    "beamName": "Main Warp Beam 204",
    "loom": 3,
    "loomCode": "LM-03",
    "sizingOutcome": 4,
    "sizingOutcomeSetNo": "SET-991",
    "warpCount": "40/1",
    "weftCount": "40/1",
    "reedWidth": "68.00",
    "pick": "64.00",
    "width": "63.00",
    "status": "Completed",
    "installationDate": "2026-10-01",
    "createdAt": "2026-10-01T08:30:00Z",
    "updatedAt": "2026-10-06T12:00:00Z"
  }
}
```

#### **Error Responses**

* **`400 Bad Request`** (Already unloaded/completed):
```json
{
  "detail": "BeamLoading #15 is already marked completed."
}
```

* **`404 Not Found`** (Invalid ID):
```json
{
  "detail": "No BeamLoading matches the given query."
}
```

* **`403 Forbidden`** (Missing required permissions):
```json
{
  "detail": "You do not have permission to mark beams as empty."
}
```

---

## 3. Alternative Method 1: Automatic Unload via Production Entry

If the beam runs out while recording daily production output, the frontend can pass `"beam_emptied": true`. This will log the final meters woven and unload the beam simultaneously in one atomic transaction.

* **Method:** `POST`
* **URL:** `/api/v1/factory/productions/`
* **Request Payload:**
```json
{
  "beam_loading": 15,
  "production_date": "2026-10-06",
  "meters_produced": 120.50,
  "shift": "Morning",
  "operator_name": "Aslam Khan",
  "remarks": "Final cut off roll. Beam completed.",
  "beam_emptied": true
}
```

* **Effects:**
  - Creates the `Production` record.
  - Automatically transitions `BeamLoading` to `Completed`.
  - Automatically transitions `Beam` to `Available`.
  - Automatically transitions `Loom` to `Active`.

---

## 4. Alternative Method 2: Cancel / Delete Loading (Loaded by mistake)

If an operator mounted a beam onto the wrong loom and needs to revert it before any weaving has occurred:

* **Method:** `DELETE`
* **URL:** `/api/v1/factory/beam-loadings/{id}/`
* **Condition:** Cannot delete if production has already been logged on this loading.
* **Effects:**
  - Deletes the loading record.
  - Automatically restores `Beam` to `Available` (or previous status).
  - Automatically restores `Loom` to `Active`.

---

## 5. TypeScript Interfaces for Frontend

```typescript
export interface EmptyBeamResponse {
  success: boolean;
  message: string;
  data: {
    id: number;
    beam: number;
    beamNumber: string;
    beamName?: string;
    loom: number;
    loomCode: string;
    sizingOutcome: number;
    sizingOutcomeSetNo: string;
    status: "Completed" | "Loaded" | "In Production" | "Empty";
    installationDate?: string;
    [key: string]: any;
  };
}

export interface UnloadBeamRequestParams {
  beamLoadingId: number;
}
```

---

## 6. Frontend UI Recommendations

1. **Active Looms / Loadings Table:**
   - Display an **"Unload / Mark Empty"** button on rows where `status` is `"Loaded"` or `"In Production"`.
   - Hide or disable this button when the status is `"Completed"`.

2. **Confirmation Modal:**
   - Prompt the user with a confirmation:  
     *"Are you sure you want to unload Beam [BM-204] from Loom [LM-03]? The beam will become Available for new sizing sets and the loom will be freed."*

3. **Post-Action State Update:**
   - On `200 OK`, invalidate the React Query / SWR cache for:
     - Active Beam Loadings (`/api/v1/factory/beam-loadings/active/`)
     - Loom List (`/api/v1/factory/looms/`)
     - Beam List (`/api/v1/factory/beams/`)
