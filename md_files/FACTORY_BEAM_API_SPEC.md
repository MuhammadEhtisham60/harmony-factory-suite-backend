# Factory Module – Beam API Specification
### Frontend Integration Guide

> **For:** Frontend Developers  
> **Base URL:** `http://<host>/api/v1/factory/`  
> **Auth:** Every request must include `Authorization: Bearer <token>`  
> **Content-Type:** `application/json`

---

## Quick Reference – All Endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| `GET` | `/api/v1/factory/beams/` | List all beams (paginated) |
| `POST` | `/api/v1/factory/beams/` | Create a new beam |
| `GET` | `/api/v1/factory/beams/:id/` | Get single beam detail |
| `PUT` | `/api/v1/factory/beams/:id/` | Full update |
| `PATCH` | `/api/v1/factory/beams/:id/` | Partial update |
| `DELETE` | `/api/v1/factory/beams/:id/` | Delete beam |
| `GET` | `/api/v1/factory/beams/stats/` | Dashboard counts by status |
| `GET` | `/api/v1/factory/beams/choices/` | Dropdown options |

---

## Authentication Header

```js
headers: {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
}
```

---

## 1. List Beams

```
GET /api/v1/factory/beams/
```

### Query Parameters (all optional)

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `page` | number | `1` | Page number |
| `page_size` | number | `20` | Items per page (max 100, default 10) |
| `search` | string | `"B-001"` | Searches code, name, number, yarn count, production order |
| `status` | string | `"Available"` | Filter by status (see choices below) |
| `production_order` | string | `"PO-2026"` | Partial match on production order |
| `yarn_count` | string | `"20/1"` | Partial match on yarn count |
| `min_length` | decimal | `500.00` | Beams with length >= value |
| `max_length` | decimal | `2000.00` | Beams with length <= value |
| `min_weight` | decimal | `50.00` | Beams with weight >= value |
| `max_weight` | decimal | `500.00` | Beams with weight <= value |
| `created_after` | date | `"2026-01-01"` | `YYYY-MM-DD` |
| `created_before` | date | `"2026-12-31"` | `YYYY-MM-DD` |
| `ordering` | string | `"-created_at"` | Prefix `-` for descending |

**Orderable fields:** `beam_code`, `beam_name`, `beam_number`, `status`, `yarn_count`, `length`, `weight`, `warp_count`, `total_ends`, `created_at`, `updated_at`

### Axios Example

```js
const response = await axios.get('/api/v1/factory/beams/', {
  headers: { Authorization: `Bearer ${token}` },
  params: {
    page: 1,
    page_size: 20,
    status: 'Available',
    ordering: 'beam_code'
  }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "count": 85,
  "totalPages": 5,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 1,
      "beamCode": "B-001",
      "beamName": "Main Beam 1",
      "beamNumber": "BN-10001",
      "yarnCount": "20/1",
      "warpCount": 2400,
      "totalEnds": 2400,
      "length": "1500.00",
      "weight": "250.00",
      "productionOrder": "PO-2026-001",
      "status": "Available",
      "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "createdAt": "2026-09-30T07:00:00Z",
      "updatedAt": "2026-09-30T07:00:00Z"
    }
  ]
}
```

---

## 2. Create Beam

```
POST /api/v1/factory/beams/
```

### Required Fields

| Field | Required |
|-------|----------|
| `beamCode` | ✅ Yes – must be unique |
| `beamNumber` | ✅ Yes – must be unique |
| All other fields | Optional |

> **Note:** Both `beamCode` and `beamNumber` are **user-provided** and must be unique across all beams.

### Request Body

```json
{
  "beamCode": "B-001",
  "beamName": "Main Beam 1",
  "beamNumber": "BN-10001",
  "yarnCount": "20/1",
  "warpCount": 2400,
  "totalEnds": 2400,
  "length": 1500.00,
  "weight": 250.00,
  "productionOrder": "PO-2026-001",
  "status": "Available",
  "notes": "Newly prepared beam. Ready for sizing."
}
```

### Axios Example

```js
const response = await axios.post('/api/v1/factory/beams/', {
  beamCode: 'B-001',
  beamNumber: 'BN-10001',
  yarnCount: '20/1',
  warpCount: 2400,
  totalEnds: 2400,
  status: 'Available'
}, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `201 Created`

```json
{
  "success": true,
  "message": "Beam created successfully.",
  "data": {
    "id": 1,
    "beamCode": "B-001",
    "beamName": "Main Beam 1",
    "beamNumber": "BN-10001",
    "yarnCount": "20/1",
    "warpCount": 2400,
    "totalEnds": 2400,
    "length": "1500.00",
    "weight": "250.00",
    "productionOrder": "PO-2026-001",
    "status": "Available",
    "notes": "Newly prepared beam. Ready for sizing.",
    "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "createdAt": "2026-09-30T07:00:00Z",
    "updatedAt": "2026-09-30T07:00:00Z"
  }
}
```

---

## 3. Get Single Beam

```
GET /api/v1/factory/beams/:id/
```

Returns full detail including `notes` field (not shown in list view).

### Axios Example

```js
const response = await axios.get(`/api/v1/factory/beams/${beamId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
// response.data.data → full beam object
```

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "beamCode": "B-001",
    ...
    "notes": "Newly prepared beam. Ready for sizing."
  }
}
```

---

## 4. Update Beam (Full / PUT)

```
PUT /api/v1/factory/beams/:id/
```

Send all fields. Any omitted optional field will be reset to its default.

### Request Body

```json
{
  "beamCode": "B-001",
  "beamName": "Main Beam 1",
  "beamNumber": "BN-10001",
  "yarnCount": "20/1",
  "warpCount": 2400,
  "totalEnds": 2400,
  "length": 1500.00,
  "weight": 250.00,
  "productionOrder": "PO-2026-001",
  "status": "In Production",
  "notes": "Moved to loom L-005 for production."
}
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Beam updated successfully.",
  "data": { ... }
}
```

---

## 5. Partial Update (PATCH)

```
PATCH /api/v1/factory/beams/:id/
```

Send only the fields you want to change.

### Examples

**Change status only (most common use case):**
```json
{ "status": "In Production" }
```

**Update weight and notes:**
```json
{
  "weight": 245.50,
  "notes": "Weight re-measured after loading."
}
```

**Link to a production order:**
```json
{ "productionOrder": "PO-2026-042" }
```

**Mark as damaged:**
```json
{
  "status": "Damaged",
  "notes": "Beam damaged during transport on 30 Sep 2026."
}
```

---

## 6. Delete Beam

```
DELETE /api/v1/factory/beams/:id/
```

### Axios Example

```js
await axios.delete(`/api/v1/factory/beams/${beamId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Beam deleted successfully."
}
```

---

## 7. Beam Stats (Dashboard)

```
GET /api/v1/factory/beams/stats/
```

Use for dashboard cards. Accepts all list filter params.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "totalBeams": 85,
    "byStatus": {
      "Available": 30,
      "Sizing": 10,
      "Loaded": 15,
      "In Production": 20,
      "Completed": 5,
      "Damaged": 3,
      "Inactive": 2
    }
  }
}
```

---

## 8. Dropdown Choices

```
GET /api/v1/factory/beams/choices/
```

Call once on page load to populate the `status` dropdown.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "statusChoices": [
      { "value": "Available",    "label": "Available" },
      { "value": "Sizing",       "label": "Sizing" },
      { "value": "Loaded",       "label": "Loaded" },
      { "value": "In Production","label": "In Production" },
      { "value": "Completed",    "label": "Completed" },
      { "value": "Damaged",      "label": "Damaged" },
      { "value": "Inactive",     "label": "Inactive" }
    ]
  }
}
```

---

## Beam Form – Field Guide

| Form Label | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Beam Code | `beamCode` | string | ✅ | User-defined, must be unique |
| Beam Name | `beamName` | string | — | Optional label/description |
| Beam Number | `beamNumber` | string | ✅ | User-defined, must be unique |
| Yarn Count | `yarnCount` | string | — | e.g. `20/1`, `30/2` |
| Warp Count | `warpCount` | integer | — | e.g. `2400` |
| Total Ends | `totalEnds` | integer | — | e.g. `2400` |
| Length | `length` | decimal | — | 2 decimal places, e.g. `1500.00` |
| Weight | `weight` | decimal | — | 2 decimal places, e.g. `250.00` |
| Production Order | `productionOrder` | string | — | Reference to production order |
| Status | `status` | string | — | Use values from `/choices/`. Default: `Available` |
| Notes | `notes` | string | — | Multi-line text for remarks |

---

## Status Values Reference

| Value | Meaning |
|-------|---------|
| `Available` | Beam is ready and available for use |
| `Sizing` | Beam is currently in the sizing process |
| `Loaded` | Beam is loaded onto a loom |
| `In Production` | Beam is actively being used in production |
| `Completed` | Beam has completed its production run |
| `Damaged` | Beam is damaged and not usable |
| `Inactive` | Beam is inactive / retired |

---

## Permission Codes

| Action | Required Permission |
|--------|-------------------|
| List / Retrieve | `beams.view` |
| Create | `beams.add` |
| Update (PUT/PATCH) | `beams.change` |
| Delete | `beams.delete` |

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | What to show |
|------|---------|--------------|
| `201` | Created | Success toast |
| `200` | OK | Success toast |
| `400` | Validation error | Show field-level errors inline |
| `401` | Unauthorized | Redirect to login |
| `403` | Forbidden | "Access denied" message |
| `404` | Not found | "Beam not found" |
| `500` | Server error | Generic error message |

### Validation Error Shape `400`

```json
{
  "beamCode": ["A beam with this code already exists."],
  "beamNumber": ["A beam with this number already exists."]
}
```

### React Error Handling Example

```js
try {
  await axios.post('/api/v1/factory/beams/', payload, { headers })
} catch (error) {
  if (error.response?.status === 400) {
    const errors = error.response.data
    setFormErrors(errors)
    // errors.beamCode?.[0]   → "A beam with this code already exists."
    // errors.beamNumber?.[0] → "A beam with this number already exists."
  }
}
```

---

## TypeScript Types (Reference)

```ts
export type BeamStatus =
  | 'Available'
  | 'Sizing'
  | 'Loaded'
  | 'In Production'
  | 'Completed'
  | 'Damaged'
  | 'Inactive'

export interface Beam {
  id?: number
  beamCode: string          // user-provided, unique
  beamName?: string
  beamNumber: string        // user-provided, unique
  yarnCount?: string        // e.g. "20/1"
  warpCount?: number | null
  totalEnds?: number | null
  length?: number | null    // decimal, e.g. 1500.00
  weight?: number | null    // decimal, e.g. 250.00
  productionOrder?: string
  status?: BeamStatus       // default: 'Available'
  notes?: string
  createdBy?: { id: number; username: string; fullName: string }
  updatedBy?: { id: number; username: string; fullName: string }
  createdAt?: string        // ISO 8601, read-only
  updatedAt?: string        // ISO 8601, read-only
}

export interface PaginatedBeams {
  success: boolean
  count: number
  totalPages: number
  currentPage: number
  pageSize: number
  results: Beam[]
}

export interface BeamStats {
  totalBeams: number
  byStatus: Record<BeamStatus, number>
}
```

---

## Full Form Submit Flow

```
1. Open "Add Beam" form
   → GET /api/v1/factory/beams/choices/         populate status dropdown

2. User fills in beam details
   → Both beamCode and beamNumber are manually entered (not auto-generated)

3. Submit
   → POST /api/v1/factory/beams/
   → 201: success toast → redirect to list or detail page
   → 400: display field-level errors inline
      (most common: duplicate beamCode or beamNumber)

4. Open "Edit Beam" form
   → GET /api/v1/factory/beams/:id/             pre-fill all fields

5. User edits, submit
   → PUT /api/v1/factory/beams/:id/
   → 200: success toast

6. Quick status change (e.g. mark In Production)
   → PATCH /api/v1/factory/beams/:id/
   → body: { "status": "In Production" }
   → 200: update status badge in UI

7. Delete beam
   → Show confirm dialog
   → DELETE /api/v1/factory/beams/:id/
   → 200: remove from UI list
```
