# Purchase Module – Supplier & Bank Account
### Frontend Integration Guide

> **For:** Frontend Developers  
> **Backend Base URL:** `http://<host>/api/v1/purchase/`  
> **Auth:** Every request must include `Authorization: Bearer <token>` in the header

---

## Quick Reference – All Endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| `GET` | `/api/v1/purchase/suppliers/` | List all suppliers (paginated) |
| `POST` | `/api/v1/purchase/suppliers/` | Create supplier + bank accounts |
| `GET` | `/api/v1/purchase/suppliers/:id/` | Get single supplier with bank accounts |
| `PUT` | `/api/v1/purchase/suppliers/:id/` | Full update (replaces bank accounts) |
| `PATCH` | `/api/v1/purchase/suppliers/:id/` | Partial update |
| `DELETE` | `/api/v1/purchase/suppliers/:id/` | Delete supplier (banks deleted too) |
| `GET` | `/api/v1/purchase/suppliers/stats/` | Dashboard counts |
| `GET` | `/api/v1/purchase/suppliers/choices/` | Dropdown options |

---

## Authentication Header

```js
// Attach to every API call
headers: {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
}
```

---

## 1. Get Suppliers List

```
GET /api/v1/purchase/suppliers/
```

### Query Params (all optional)

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `page` | number | `1` | Page number |
| `page_size` | number | `20` | Items per page (max 100) |
| `search` | string | `"HBL"` | Search in name, code, company, phone, email, contact |
| `status` | string | `"Active"` | Filter: `Active` / `Inactive` / `Blocked` |
| `supplier_type` | string | `"Yarn"` | Filter by supplier type |
| `created_after` | date | `"2026-01-01"` | YYYY-MM-DD |
| `created_before` | date | `"2026-12-31"` | YYYY-MM-DD |
| `ordering` | string | `"-created_at"` | Prefix `-` for descending |

**Orderable fields:** `supplier_name`, `supplier_code`, `company_name`, `status`, `supplier_type`, `created_at`, `updated_at`

### Axios Example

```js
const response = await axios.get('/api/v1/purchase/suppliers/', {
  headers: { Authorization: `Bearer ${token}` },
  params: {
    page: 1,
    page_size: 20,
    status: 'Active',
    ordering: '-created_at'
  }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "count": 42,
  "totalPages": 3,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 1,
      "supplierCode": "SUP-0001",
      "supplierName": "Ali Textile Mills",
      "companyName": "Ali Group Pvt Ltd",
      "phone": "03001234567",
      "email": "ali@textiles.com",
      "contactPerson": "Muhammad Ali",
      "supplierType": "Yarn",
      "status": "Active",
      "registrationNumber": "NTN-1234567",
      "bankAccountCount": 2,
      "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "createdAt": "2026-09-30T07:00:00Z",
      "updatedAt": "2026-09-30T07:00:00Z"
    }
  ]
}
```

> **Note:** List view shows `bankAccountCount` (a number). For full bank account details, call the single supplier endpoint.

---

## 2. Create Supplier (with Bank Accounts)

```
POST /api/v1/purchase/suppliers/
```

### Required Fields

| Field | Required |
|-------|----------|
| `supplierName` | ✅ Yes |
| `phone` | ✅ Yes |
| `contactPerson` | ✅ Yes |
| All other fields | Optional |
| `bankAccounts` array | Optional (can be empty or omitted) |

### Request Body

```json
{
  "supplierName": "Ali Textile Mills",
  "companyName": "Ali Group Pvt Ltd",
  "address": "123 Industrial Area, Faisalabad",
  "phone": "03001234567",
  "email": "ali@textiles.com",
  "contactPerson": "Muhammad Ali",
  "supplierType": "Yarn",
  "status": "Active",
  "registrationNumber": "NTN-1234567",
  "bankAccounts": [
    {
      "bankName": "HBL",
      "accountTitle": "Ali Textile Mills",
      "accountNumber": "1234567890123",
      "iban": "PK36HABB0000001123456702",
      "branchName": "Faisalabad Main Branch",
      "branchCode": "0123",
      "swiftCode": "HABBPKKA",
      "isPrimary": true
    },
    {
      "bankName": "MCB",
      "accountTitle": "Ali Textile Mills",
      "accountNumber": "9876543210",
      "isPrimary": false
    }
  ]
}
```

### Axios Example

```js
const response = await axios.post('/api/v1/purchase/suppliers/', {
  supplierName: 'Ali Textile Mills',
  phone: '03001234567',
  contactPerson: 'Muhammad Ali',
  supplierType: 'Yarn',
  status: 'Active',
  bankAccounts: [
    {
      bankName: 'HBL',
      accountTitle: 'Ali Textile Mills',
      accountNumber: '1234567890123',
      isPrimary: true
    }
  ]
}, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `201 Created`

```json
{
  "success": true,
  "message": "Supplier created successfully.",
  "data": {
    "id": 1,
    "supplierCode": "SUP-0001",
    "supplierName": "Ali Textile Mills",
    "companyName": "Ali Group Pvt Ltd",
    "address": "123 Industrial Area, Faisalabad",
    "phone": "03001234567",
    "email": "ali@textiles.com",
    "contactPerson": "Muhammad Ali",
    "supplierType": "Yarn",
    "status": "Active",
    "registrationNumber": "NTN-1234567",
    "bankAccounts": [
      {
        "id": 1,
        "bankName": "HBL",
        "accountTitle": "Ali Textile Mills",
        "accountNumber": "1234567890123",
        "iban": "PK36HABB0000001123456702",
        "branchName": "Faisalabad Main Branch",
        "branchCode": "0123",
        "swiftCode": "HABBPKKA",
        "isPrimary": true,
        "createdAt": "2026-09-30T07:00:00Z",
        "updatedAt": "2026-09-30T07:00:00Z"
      },
      {
        "id": 2,
        "bankName": "MCB",
        "accountTitle": "Ali Textile Mills",
        "accountNumber": "9876543210",
        "iban": "",
        "branchName": "",
        "branchCode": "",
        "swiftCode": "",
        "isPrimary": false,
        "createdAt": "2026-09-30T07:00:00Z",
        "updatedAt": "2026-09-30T07:00:00Z"
      }
    ],
    "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "createdAt": "2026-09-30T07:00:00Z",
    "updatedAt": "2026-09-30T07:00:00Z"
  }
}
```

---

## 3. Get Single Supplier

```
GET /api/v1/purchase/suppliers/:id/
```

Returns full detail including all bank accounts.

### Axios Example

```js
const response = await axios.get(`/api/v1/purchase/suppliers/${supplierId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
// response.data.data → full supplier object with bankAccounts[]
```

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "supplierCode": "SUP-0001",
    "supplierName": "Ali Textile Mills",
    ...
    "bankAccounts": [ ... ]
  }
}
```

---

## 4. Update Supplier (Full / PUT)

```
PUT /api/v1/purchase/suppliers/:id/
```

### ⚠️ Bank Account Reconcile Rules (important!)

When you send `bankAccounts` in a PUT/PATCH:

| What you send | What happens |
|---------------|--------------|
| Account object **with `id`** | That account is **updated** |
| Account object **without `id`** | A **new** account is **created** |
| Existing account **not included** in the array | That account is **deleted** |
| `"bankAccounts": []` | **All** bank accounts are deleted |
| `bankAccounts` key **not sent at all** (PATCH only) | Bank accounts are **left unchanged** |

### Workflow for Edit Form

1. Load supplier → `GET /api/v1/purchase/suppliers/:id/`
2. Pre-fill the form with `data` (including `bankAccounts` array, each has an `id`)
3. User edits fields / adds or removes bank rows
4. On submit → send `PUT` with the full updated payload
   - Keep `id` on existing bank rows (even if unchanged)
   - Remove the `id` field from any newly added bank rows
   - Simply omit deleted rows from the array

### Request Body Example

```json
{
  "supplierName": "Ali Textile Mills",
  "companyName": "Ali Group Pvt Ltd",
  "address": "New Address Line",
  "phone": "03009876543",
  "email": "ali@textiles.com",
  "contactPerson": "Muhammad Ali",
  "supplierType": "Yarn",
  "status": "Active",
  "registrationNumber": "NTN-1234567",
  "bankAccounts": [
    {
      "id": 1,
      "bankName": "HBL",
      "accountTitle": "Ali Textile – Updated",
      "accountNumber": "1234567890123",
      "iban": "PK36HABB0000001123456702",
      "isPrimary": true
    },
    {
      "bankName": "UBL",
      "accountTitle": "Ali Textile UBL Account",
      "accountNumber": "5555555555",
      "isPrimary": false
    }
  ]
}
```

> In this example: `id=1` (HBL) is updated, `id=2` (MCB) was removed from the array so it gets **deleted**, and UBL is a new row (no `id`) so it gets **created**.

### Axios Example

```js
const response = await axios.put(
  `/api/v1/purchase/suppliers/${supplierId}/`,
  payload,
  { headers: { Authorization: `Bearer ${token}` } }
)
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Supplier updated successfully.",
  "data": { ... }   // full updated supplier with reconciled bankAccounts[]
}
```

---

## 5. Partial Update (PATCH)

```
PATCH /api/v1/purchase/suppliers/:id/
```

Send only the fields you want to change. `bankAccounts` key follows the same reconcile rules.

### Examples

**Change status only:**
```json
{ "status": "Inactive" }
```

**Change phone only:**
```json
{ "phone": "03331234567" }
```

**Add a new bank account without touching existing ones:**
```json
{
  "bankAccounts": [
    { "id": 1, "bankName": "HBL", "accountTitle": "Ali Textile", "accountNumber": "1234567890123", "isPrimary": true },
    { "id": 2, "bankName": "MCB", "accountTitle": "Ali Textile", "accountNumber": "9876543210", "isPrimary": false },
    { "bankName": "Meezan", "accountTitle": "Ali Textile Islamic", "accountNumber": "1111222233334444", "isPrimary": false }
  ]
}
```

---

## 6. Delete Supplier

```
DELETE /api/v1/purchase/suppliers/:id/
```

Deletes the supplier AND all its bank accounts.

### Axios Example

```js
await axios.delete(`/api/v1/purchase/suppliers/${supplierId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Supplier deleted successfully."
}
```

---

## 7. Supplier Stats (Dashboard)

```
GET /api/v1/purchase/suppliers/stats/
```

Use this for dashboard cards / charts. Accepts the same filter params as the list endpoint.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "totalSuppliers": 42,
    "byStatus": {
      "Active": 35,
      "Inactive": 5,
      "Blocked": 2
    },
    "byType": {
      "Yarn": 12,
      "Spare Parts": 8,
      "Machinery": 5,
      "Dyes & Chemicals": 7,
      "Packaging": 4,
      "General": 4,
      "Other": 2
    }
  }
}
```

---

## 8. Dropdown Choices

```
GET /api/v1/purchase/suppliers/choices/
```

Call this once on page load to populate your `<select>` dropdowns.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "supplierTypes": [
      { "value": "Yarn", "label": "Yarn" },
      { "value": "Spare Parts", "label": "Spare Parts" },
      { "value": "Machinery", "label": "Machinery" },
      { "value": "Dyes & Chemicals", "label": "Dyes & Chemicals" },
      { "value": "Packaging", "label": "Packaging" },
      { "value": "General", "label": "General" },
      { "value": "Other", "label": "Other" }
    ],
    "statusChoices": [
      { "value": "Active", "label": "Active" },
      { "value": "Inactive", "label": "Inactive" },
      { "value": "Blocked", "label": "Blocked" }
    ]
  }
}
```

---

## Supplier Form – Field Guide

### Supplier Info Section

| Form Field | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Supplier Name | `supplierName` | string | ✅ | Must be unique |
| Company Name | `companyName` | string | — | |
| Address | `address` | string | — | Multi-line text |
| Phone | `phone` | string | ✅ | |
| Email | `email` | string | — | Must be unique if provided |
| Contact Person | `contactPerson` | string | ✅ | |
| Supplier Type | `supplierType` | string | — | Use values from `/choices/` |
| Status | `status` | string | — | Default: `Active` |
| Registration No. | `registrationNumber` | string | — | NTN / STRN etc. |

### Bank Account Section (repeatable rows)

| Form Field | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Bank Name | `bankName` | string | ✅ | |
| Account Title | `accountTitle` | string | ✅ | |
| Account Number | `accountNumber` | string | ✅ | |
| IBAN | `iban` | string | — | |
| Branch Name | `branchName` | string | — | |
| Branch Code | `branchCode` | string | — | |
| SWIFT Code | `swiftCode` | string | — | |
| Primary Account | `isPrimary` | boolean | — | Radio/toggle; only one allowed |

> **Primary account rule:** Only one bank account may have `isPrimary: true`. If the user selects a new primary, deselect the previous one on the frontend before submitting.

---

## Error Handling

All errors return a consistent shape:

```json
{
  "supplierName": ["A supplier with this name already exists."],
  "email": ["A supplier with this email already exists."],
  "bankAccounts": ["Only one bank account can be marked as primary."]
}
```

### HTTP Status Codes

| Code | Meaning | What to show |
|------|---------|--------------|
| `201` | Created | Success toast |
| `200` | OK (update/delete) | Success toast |
| `400` | Validation error | Show field-level errors from response |
| `401` | Unauthorized | Redirect to login |
| `403` | No permission | "You don't have access" message |
| `404` | Not found | "Supplier not found" message |
| `500` | Server error | Generic error message |

### Validation Error Display Example (React)

```js
try {
  await axios.post('/api/v1/purchase/suppliers/', payload, { headers })
} catch (error) {
  if (error.response?.status === 400) {
    const errors = error.response.data
    // errors.supplierName[0] → "A supplier with this name already exists."
    // errors.bankAccounts[0] → "Only one bank account can be marked as primary."
    setFormErrors(errors)
  }
}
```

---

## Full Form Submit Flow

```
1. User opens "Add Supplier" form
   → GET /api/v1/purchase/suppliers/choices/   (populate dropdowns)

2. User fills supplier details + adds bank account rows

3. User submits form
   → POST /api/v1/purchase/suppliers/          (body: supplierInfo + bankAccounts[])
   → On success: show toast, redirect to supplier list or detail page
   → On 400: display field errors inline

4. User opens "Edit Supplier" form
   → GET /api/v1/purchase/suppliers/:id/       (pre-fill all fields including bankAccounts[])
   → Each bank account row will have an `id` — store it in the form state

5. User edits / adds / removes bank account rows

6. User submits
   → PUT /api/v1/purchase/suppliers/:id/
     - Existing rows: include their `id`
     - New rows: no `id` field
     - Deleted rows: don't include them at all

7. User clicks Delete
   → DELETE /api/v1/purchase/suppliers/:id/
   → Confirm dialog first → on confirm call API → remove from list
```

---

## TypeScript Types (Reference)

```ts
export interface BankAccount {
  id?: number           // present on existing, absent on new
  bankName: string
  accountTitle: string
  accountNumber: string
  iban?: string
  branchName?: string
  branchCode?: string
  swiftCode?: string
  isPrimary: boolean
  createdAt?: string    // ISO 8601, read-only
  updatedAt?: string    // ISO 8601, read-only
}

export interface Supplier {
  id?: number
  supplierCode?: string     // read-only, auto-generated
  supplierName: string
  companyName?: string
  address?: string
  phone: string
  email?: string
  contactPerson: string
  supplierType?: 'Yarn' | 'Spare Parts' | 'Machinery' | 'Dyes & Chemicals' | 'Packaging' | 'General' | 'Other'
  status?: 'Active' | 'Inactive' | 'Blocked'
  registrationNumber?: string
  bankAccounts?: BankAccount[]
  bankAccountCount?: number   // list view only, read-only
  createdBy?: { id: number; username: string; fullName: string }
  updatedBy?: { id: number; username: string; fullName: string }
  createdAt?: string
  updatedAt?: string
}

export interface PaginatedSuppliers {
  success: boolean
  count: number
  totalPages: number
  currentPage: number
  pageSize: number
  results: Supplier[]
}
```
