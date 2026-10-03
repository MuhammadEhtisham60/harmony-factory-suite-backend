# Factory Module – Loom API Specification
### Frontend Integration Guide

> **For:** Frontend Developers  
> **Base URL:** `http://<host>/api/v1/factory/`  
> **Auth:** Every request must include `Authorization: Bearer <token>`  
> **Content-Type:** `application/json`

---

## Quick Reference – All Endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| `GET` | `/api/v1/factory/looms/` | List all looms (paginated) |
| `POST` | `/api/v1/factory/looms/` | Create a new loom |
| `GET` | `/api/v1/factory/looms/:id/` | Get single loom detail |
| `PUT` | `/api/v1/factory/looms/:id/` | Full update |
| `PATCH` | `/api/v1/factory/looms/:id/` | Partial update |
| `DELETE` | `/api/v1/factory/looms/:id/` | Delete loom |
| `GET` | `/api/v1/factory/looms/stats/` | Dashboard counts by status |
| `GET` | `/api/v1/factory/looms/choices/` | Dropdown options |

---

## Authentication Header

```js
headers: {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
}
```

---

## 1. List Looms

```
GET /api/v1/factory/looms/
```

### Query Parameters (all optional)

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `page` | number | `1` | Page number |
| `page_size` | number | `20` | Items per page (max 100, default 10) |
| `search` | string | `"L-001"` | Searches code, name, model no., location |
| `status` | string | `"Active"` | Filter by status (see choices below) |
| `location` | string | `"Hall A"` | Partial match on location |
| `installed_after` | date | `"2020-01-01"` | `YYYY-MM-DD` – installation date from |
| `installed_before` | date | `"2026-12-31"` | `YYYY-MM-DD` – installation date to |
| `created_after` | date | `"2026-01-01"` | `YYYY-MM-DD` – record created from |
| `created_before` | date | `"2026-12-31"` | `YYYY-MM-DD` – record created to |
| `ordering` | string | `"-created_at"` | Prefix `-` for descending |

**Orderable fields:** `loom_code`, `loom_name`, `status`, `location`, `installation_date`, `created_at`, `updated_at`

### Axios Example

```js
const response = await axios.get('/api/v1/factory/looms/', {
  headers: { Authorization: `Bearer ${token}` },
  params: {
    page: 1,
    page_size: 20,
    status: 'Active',
    ordering: 'loom_code'
  }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "count": 120,
  "totalPages": 6,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 1,
      "loomCode": "L-001",
      "loomName": "Loom A1",
      "modelNumber": "TM-500",
      "width": "220.00",
      "installationDate": "2020-05-15",
      "location": "Hall A",
      "status": "Active",
      "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "createdAt": "2026-09-30T07:00:00Z",
      "updatedAt": "2026-09-30T07:00:00Z"
    }
  ]
}
```

---

## 2. Create Loom

```
POST /api/v1/factory/looms/
```

### Required Fields

| Field | Required |
|-------|----------|
| `loomCode` | ✅ Yes – must be unique |
| `loomName` | ✅ Yes |
| All other fields | Optional |

> **Note:** `loomCode` is **user-provided** (unlike supplier/customer codes which are auto-generated). You must supply a unique code.

### Request Body

```json
{
  "loomCode": "L-001",
  "loomName": "Loom A1",
  "modelNumber": "TM-500",
  "width": 220.00,
  "installationDate": "2020-05-15",
  "location": "Hall A",
  "status": "Active",
  "notes": "Recently serviced. Running well."
}
```

### Axios Example

```js
const response = await axios.post('/api/v1/factory/looms/', {
  loomCode: 'L-001',
  loomName: 'Loom A1',
  status: 'Active'
}, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `201 Created`

```json
{
  "success": true,
  "message": "Loom created successfully.",
  "data": {
    "id": 1,
    "loomCode": "L-001",
    "loomName": "Loom A1",
    "modelNumber": "TM-500",
    "width": "220.00",
    "installationDate": "2020-05-15",
    "location": "Hall A",
    "status": "Active",
    "notes": "Recently serviced. Running well.",
    "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "createdAt": "2026-09-30T07:00:00Z",
    "updatedAt": "2026-09-30T07:00:00Z"
  }
}
```

---

## 3. Get Single Loom

```
GET /api/v1/factory/looms/:id/
```

Returns full detail including `notes` field (not shown in list).

### Axios Example

```js
const response = await axios.get(`/api/v1/factory/looms/${loomId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
// response.data.data → full loom object
```

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "loomCode": "L-001",
    "loomName": "Loom A1",
    ...
    "notes": "Recently serviced. Running well."
  }
}
```

---

## 4. Update Loom (Full / PUT)

```
PUT /api/v1/factory/looms/:id/
```

Send all fields. Any omitted optional field will be reset to its default.

### Request Body

```json
{
  "loomCode": "L-001",
  "loomName": "Loom A1 Updated",
  "modelNumber": "TM-600",
  "width": 240.00,
  "installationDate": "2020-05-15",
  "location": "Hall B",
  "status": "Production",
  "notes": "Moved to Hall B after upgrade."
}
```

### Axios Example

```js
const response = await axios.put(
  `/api/v1/factory/looms/${loomId}/`,
  payload,
  { headers: { Authorization: `Bearer ${token}` } }
)
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Loom updated successfully.",
  "data": { ... }
}
```

---

## 5. Partial Update (PATCH)

```
PATCH /api/v1/factory/looms/:id/
```

Send only the fields you want to change.

### Examples

**Change status only (most common use case):**
```json
{ "status": "Maintenance" }
```

**Change location only:**
```json
{ "location": "Hall C" }
```

**Update notes and status:**
```json
{
  "status": "Breakdown",
  "notes": "Motor failure reported on 30 Sep 2026. Technician notified."
}
```

---

## 6. Delete Loom

```
DELETE /api/v1/factory/looms/:id/
```

### Axios Example

```js
await axios.delete(`/api/v1/factory/looms/${loomId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Loom deleted successfully."
}
```

---

## 7. Loom Stats (Dashboard)

```
GET /api/v1/factory/looms/stats/
```

Use for dashboard cards or status summary charts. Accepts all list filter params.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "totalLooms": 120,
    "byStatus": {
      "Active": 80,
      "Inactive": 10,
      "Sizing": 8,
      "Production": 15,
      "Maintenance": 5,
      "Breakdown": 2
    }
  }
}
```

---

## 8. Dropdown Choices

```
GET /api/v1/factory/looms/choices/
```

Call once on page load to populate the `status` dropdown.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "statusChoices": [
      { "value": "Active",      "label": "Active" },
      { "value": "Inactive",    "label": "Inactive" },
      { "value": "Sizing",      "label": "Sizing" },
      { "value": "Production",  "label": "Production" },
      { "value": "Maintenance", "label": "Maintenance" },
      { "value": "Breakdown",   "label": "Breakdown" }
    ]
  }
}
```

---

## Loom Form – Field Guide

| Form Label | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Loom Code | `loomCode` | string | ✅ | User-defined, must be unique |
| Loom Name | `loomName` | string | ✅ | |
| Model Number | `modelNumber` | string | — | |
| Width (cm) | `width` | decimal | — | Max 2 decimal places, e.g. `220.00` |
| Installation Date | `installationDate` | date | — | Format: `YYYY-MM-DD` |
| Location | `location` | string | — | e.g. Hall A, Section 3 |
| Status | `status` | string | — | Use values from `/choices/`. Default: `Active` |
| Notes | `notes` | string | — | Multi-line text for remarks |

> **`loomCode`** is manually entered by the user — unlike supplier/customer codes which are auto-generated. Validate uniqueness before submit using the `400` error response.

---

## Status Values Reference

| Value | Meaning |
|-------|---------|
| `Active` | Loom is operational and available |
| `Inactive` | Loom is not in use |
| `Sizing` | Loom is in the sizing process |
| `Production` | Loom is currently running production |
| `Maintenance` | Loom is under scheduled maintenance |
| `Breakdown` | Loom has broken down, needs repair |

---

## Permission Codes

| Action | Required Permission |
|--------|-------------------|
| List / Retrieve | `looms.view` |
| Create | `looms.add` |
| Update (PUT/PATCH) | `looms.change` |
| Delete | `looms.delete` |

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
| `404` | Not found | "Loom not found" |
| `500` | Server error | Generic error message |

### Validation Error Shape `400`

```json
{
  "loomCode": ["A loom with this code already exists."]
}
```

### React Error Handling Example

```js
try {
  await axios.post('/api/v1/factory/looms/', payload, { headers })
} catch (error) {
  if (error.response?.status === 400) {
    const errors = error.response.data
    setFormErrors(errors)
    // errors.loomCode?.[0] → "A loom with this code already exists."
  }
}
```

---

## TypeScript Types (Reference)

```ts
export type LoomStatus =
  | 'Active'
  | 'Inactive'
  | 'Sizing'
  | 'Production'
  | 'Maintenance'
  | 'Breakdown'

export interface Loom {
  id?: number
  loomCode: string            // user-provided, unique
  loomName: string
  modelNumber?: string
  width?: number | null         // decimal, e.g. 220.00
  installationDate?: string | null  // YYYY-MM-DD
  location?: string
  status?: LoomStatus           // default: 'Active'
  notes?: string
  createdBy?: { id: number; username: string; fullName: string }
  updatedBy?: { id: number; username: string; fullName: string }
  createdAt?: string            // ISO 8601, read-only
  updatedAt?: string            // ISO 8601, read-only
}

export interface PaginatedLooms {
  success: boolean
  count: number
  totalPages: number
  currentPage: number
  pageSize: number
  results: Loom[]
}

export interface LoomStats {
  totalLooms: number
  byStatus: Record<LoomStatus, number>
}
```

---

## Full Form Submit Flow

```
1. Open "Add Loom" form
   → GET /api/v1/factory/looms/choices/       populate status dropdown

2. User fills in loom details
   → loomCode is manually entered (not auto-generated)

3. Submit
   → POST /api/v1/factory/looms/
   → 201: success toast → redirect to list or detail page
   → 400: display field-level errors inline
      (most common: duplicate loomCode)

4. Open "Edit Loom" form
   → GET /api/v1/factory/looms/:id/           pre-fill all fields

5. User edits, submit
   → PUT /api/v1/factory/looms/:id/
   → 200: success toast

6. Quick status change (e.g. toggle to Maintenance)
   → PATCH /api/v1/factory/looms/:id/
   → body: { "status": "Maintenance" }
   → 200: update status badge in UI

7. Delete loom
   → Show confirm dialog
   → DELETE /api/v1/factory/looms/:id/
   → 200: remove from UI list
```
