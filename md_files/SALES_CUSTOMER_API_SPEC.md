# Sales Module – Customer & Bank Account API Specification
### Frontend Integration Guide

> **For:** Frontend Developers  
> **Base URL:** `http://<host>/api/v1/sales/`  
> **Auth:** Every request must include `Authorization: Bearer <token>`  
> **Content-Type:** `application/json`

---

## Quick Reference – All Endpoints

| Method | URL | What it does |
|--------|-----|--------------|
| `GET` | `/api/v1/sales/customers/` | List all customers (paginated) |
| `POST` | `/api/v1/sales/customers/` | Create customer + bank accounts |
| `GET` | `/api/v1/sales/customers/:id/` | Get single customer with bank accounts |
| `PUT` | `/api/v1/sales/customers/:id/` | Full update (reconciles bank accounts) |
| `PATCH` | `/api/v1/sales/customers/:id/` | Partial update |
| `DELETE` | `/api/v1/sales/customers/:id/` | Delete customer (banks deleted too) |
| `GET` | `/api/v1/sales/customers/stats/` | Dashboard counts |
| `GET` | `/api/v1/sales/customers/choices/` | Dropdown options |

---

## Authentication Header

```js
headers: {
  "Authorization": `Bearer ${token}`,
  "Content-Type": "application/json"
}
```

---

## 1. List Customers

```
GET /api/v1/sales/customers/
```

Returns a paginated list. Each item shows `bankAccountCount` (a number) — not the full bank list. For full bank details call the single customer endpoint.

### Query Parameters (all optional)

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `page` | number | `1` | Page number |
| `page_size` | number | `20` | Items per page (max 100, default 10) |
| `search` | string | `"Raza"` | Searches name, code, company, phone, email, contact person |
| `status` | string | `"Active"` | `Active` / `Inactive` / `Blocked` |
| `customer_type` | string | `"Wholesaler"` | Filter by customer type |
| `created_after` | date | `"2026-01-01"` | `YYYY-MM-DD` |
| `created_before` | date | `"2026-12-31"` | `YYYY-MM-DD` |
| `ordering` | string | `"-created_at"` | Prefix `-` for descending |

**Orderable fields:** `customer_name`, `customer_code`, `company_name`, `status`, `customer_type`, `created_at`, `updated_at`

### Axios Example

```js
const response = await axios.get('/api/v1/sales/customers/', {
  headers: { Authorization: `Bearer ${token}` },
  params: {
    page: 1,
    page_size: 20,
    status: 'Active',
    customer_type: 'Wholesaler',
    ordering: '-created_at'
  }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "count": 58,
  "totalPages": 3,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 1,
      "customerCode": "CUS-0001",
      "customerName": "Raza Fabrics",
      "companyName": "Raza Group Pvt Ltd",
      "phone": "03211234567",
      "email": "raza@fabrics.com",
      "contactPerson": "Raza Ahmed",
      "customerType": "Wholesaler",
      "status": "Active",
      "registrationNumber": "NTN-9876543",
      "bankAccountCount": 2,
      "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
      "createdAt": "2026-09-30T07:00:00Z",
      "updatedAt": "2026-09-30T07:00:00Z"
    }
  ]
}
```

---

## 2. Create Customer (with Bank Accounts)

```
POST /api/v1/sales/customers/
```

### Required Fields

| Field | Required |
|-------|----------|
| `customerName` | ✅ Yes |
| `phone` | ✅ Yes |
| `contactPerson` | ✅ Yes |
| All other fields | Optional |
| `bankAccounts` array | Optional (omit or send `[]` for no banks) |

### Request Body

```json
{
  "customerName": "Raza Fabrics",
  "companyName": "Raza Group Pvt Ltd",
  "address": "Plot 45, Textile City, Lahore",
  "phone": "03211234567",
  "email": "raza@fabrics.com",
  "contactPerson": "Raza Ahmed",
  "customerType": "Wholesaler",
  "status": "Active",
  "registrationNumber": "NTN-9876543",
  "bankAccounts": [
    {
      "bankName": "HBL",
      "accountTitle": "Raza Fabrics",
      "accountNumber": "1234567890123",
      "iban": "PK36HABB0000001123456702",
      "branchName": "Lahore Main Branch",
      "branchCode": "0456",
      "swiftCode": "HABBPKKA",
      "isPrimary": true
    },
    {
      "bankName": "MCB",
      "accountTitle": "Raza Fabrics",
      "accountNumber": "9876543210",
      "isPrimary": false
    }
  ]
}
```

### Axios Example

```js
const response = await axios.post('/api/v1/sales/customers/', {
  customerName: 'Raza Fabrics',
  phone: '03211234567',
  contactPerson: 'Raza Ahmed',
  customerType: 'Wholesaler',
  status: 'Active',
  bankAccounts: [
    {
      bankName: 'HBL',
      accountTitle: 'Raza Fabrics',
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
  "message": "Customer created successfully.",
  "data": {
    "id": 1,
    "customerCode": "CUS-0001",
    "customerName": "Raza Fabrics",
    "companyName": "Raza Group Pvt Ltd",
    "address": "Plot 45, Textile City, Lahore",
    "phone": "03211234567",
    "email": "raza@fabrics.com",
    "contactPerson": "Raza Ahmed",
    "customerType": "Wholesaler",
    "status": "Active",
    "registrationNumber": "NTN-9876543",
    "bankAccounts": [
      {
        "id": 1,
        "bankName": "HBL",
        "accountTitle": "Raza Fabrics",
        "accountNumber": "1234567890123",
        "iban": "PK36HABB0000001123456702",
        "branchName": "Lahore Main Branch",
        "branchCode": "0456",
        "swiftCode": "HABBPKKA",
        "isPrimary": true,
        "createdAt": "2026-09-30T07:00:00Z",
        "updatedAt": "2026-09-30T07:00:00Z"
      },
      {
        "id": 2,
        "bankName": "MCB",
        "accountTitle": "Raza Fabrics",
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

## 3. Get Single Customer

```
GET /api/v1/sales/customers/:id/
```

Returns full detail including all bank accounts.

### Axios Example

```js
const response = await axios.get(`/api/v1/sales/customers/${customerId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
// response.data.data → full customer object with bankAccounts[]
```

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "id": 1,
    "customerCode": "CUS-0001",
    "customerName": "Raza Fabrics",
    "companyName": "Raza Group Pvt Ltd",
    "address": "Plot 45, Textile City, Lahore",
    "phone": "03211234567",
    "email": "raza@fabrics.com",
    "contactPerson": "Raza Ahmed",
    "customerType": "Wholesaler",
    "status": "Active",
    "registrationNumber": "NTN-9876543",
    "bankAccounts": [ ... ],
    "createdBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "updatedBy": { "id": 1, "username": "admin", "fullName": "Admin User" },
    "createdAt": "2026-09-30T07:00:00Z",
    "updatedAt": "2026-09-30T07:00:00Z"
  }
}
```

---

## 4. Update Customer (Full / PUT)

```
PUT /api/v1/sales/customers/:id/
```

### ⚠️ Bank Account Reconcile Rules (Read carefully!)

When you send `bankAccounts` in a PUT or PATCH request:

| What you send | What happens |
|---------------|--------------|
| Account object **with** matching `id` | That account is **updated** |
| Account object **without** `id` | A **new** account is **created** |
| Existing account **not included** in array | That account is **deleted** |
| `"bankAccounts": []` | **All** bank accounts are deleted |
| `bankAccounts` key **omitted** (PATCH only) | Bank accounts **left unchanged** |

### Workflow for Edit Form

```
1. Load customer     → GET /api/v1/sales/customers/:id/
2. Pre-fill form     → use data.bankAccounts[] — each account has an id
3. User edits        → add rows (no id), remove rows, edit existing rows (keep id)
4. Submit            → PUT with full payload
   - Existing rows   → include their id
   - New rows        → no id field
   - Deleted rows    → just omit them from the array
```

### Request Body Example

```json
{
  "customerName": "Raza Fabrics",
  "companyName": "Raza Group Pvt Ltd",
  "address": "New Address, Lahore",
  "phone": "03219876543",
  "email": "raza@fabrics.com",
  "contactPerson": "Raza Ahmed",
  "customerType": "Distributor",
  "status": "Active",
  "registrationNumber": "NTN-9876543",
  "bankAccounts": [
    {
      "id": 1,
      "bankName": "HBL",
      "accountTitle": "Raza Fabrics – Updated",
      "accountNumber": "1234567890123",
      "iban": "PK36HABB0000001123456702",
      "isPrimary": true
    },
    {
      "bankName": "UBL",
      "accountTitle": "Raza Fabrics UBL",
      "accountNumber": "5555555555",
      "isPrimary": false
    }
  ]
}
```

> In this example: `id=1` (HBL) is **updated**, `id=2` (MCB) is **deleted** (not in array), UBL is **created** (no id).

### Response `200 OK`

```json
{
  "success": true,
  "message": "Customer updated successfully.",
  "data": { ... }
}
```

---

## 5. Partial Update (PATCH)

```
PATCH /api/v1/sales/customers/:id/
```

Send only the fields you want to change. If `bankAccounts` key is **omitted**, banks are **not touched**.

### Examples

**Change status only:**
```json
{ "status": "Inactive" }
```

**Change type only:**
```json
{ "customerType": "Retailer" }
```

**Add a new bank without disturbing existing ones:**
```json
{
  "bankAccounts": [
    { "id": 1, "bankName": "HBL", "accountTitle": "Raza Fabrics", "accountNumber": "1234567890123", "isPrimary": true },
    { "id": 2, "bankName": "MCB", "accountTitle": "Raza Fabrics", "accountNumber": "9876543210", "isPrimary": false },
    { "bankName": "Meezan", "accountTitle": "Raza Fabrics Islamic", "accountNumber": "1111222233334444", "isPrimary": false }
  ]
}
```

---

## 6. Delete Customer

```
DELETE /api/v1/sales/customers/:id/
```

Deletes the customer and **all its bank accounts** automatically (CASCADE).

### Axios Example

```js
await axios.delete(`/api/v1/sales/customers/${customerId}/`, {
  headers: { Authorization: `Bearer ${token}` }
})
```

### Response `200 OK`

```json
{
  "success": true,
  "message": "Customer deleted successfully."
}
```

---

## 7. Customer Stats (Dashboard)

```
GET /api/v1/sales/customers/stats/
```

Use for dashboard cards or charts. Accepts all list filter params.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "totalCustomers": 58,
    "byStatus": {
      "Active": 50,
      "Inactive": 6,
      "Blocked": 2
    },
    "byType": {
      "Wholesaler": 15,
      "Retailer": 20,
      "Distributor": 8,
      "Manufacturer": 5,
      "Exporter": 4,
      "General": 4,
      "Other": 2
    }
  }
}
```

---

## 8. Dropdown Choices

```
GET /api/v1/sales/customers/choices/
```

Call once on page load to populate `<select>` dropdowns. No need to hardcode values.

### Response `200 OK`

```json
{
  "success": true,
  "data": {
    "customerTypes": [
      { "value": "Wholesaler",   "label": "Wholesaler" },
      { "value": "Retailer",     "label": "Retailer" },
      { "value": "Distributor",  "label": "Distributor" },
      { "value": "Manufacturer", "label": "Manufacturer" },
      { "value": "Exporter",     "label": "Exporter" },
      { "value": "General",      "label": "General" },
      { "value": "Other",        "label": "Other" }
    ],
    "statusChoices": [
      { "value": "Active",   "label": "Active" },
      { "value": "Inactive", "label": "Inactive" },
      { "value": "Blocked",  "label": "Blocked" }
    ]
  }
}
```

---

## Customer Form – Field Guide

### Customer Info Section

| Form Label | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Customer Name | `customerName` | string | ✅ | Unique (case-insensitive) |
| Company Name | `companyName` | string | — | |
| Address | `address` | string | — | Multi-line text |
| Phone | `phone` | string | ✅ | |
| Email | `email` | string | — | Unique when provided |
| Contact Person | `contactPerson` | string | ✅ | |
| Customer Type | `customerType` | string | — | Use values from `/choices/` |
| Status | `status` | string | — | Default: `Active` |
| Registration No. | `registrationNumber` | string | — | NTN / STRN etc. |

### Bank Account Section (repeatable rows)

| Form Label | API Key | Type | Required | Notes |
|------------|---------|------|----------|-------|
| Bank Name | `bankName` | string | ✅ | |
| Account Title | `accountTitle` | string | ✅ | |
| Account Number | `accountNumber` | string | ✅ | |
| IBAN | `iban` | string | — | |
| Branch Name | `branchName` | string | — | |
| Branch Code | `branchCode` | string | — | |
| SWIFT Code | `swiftCode` | string | — | |
| Primary Account | `isPrimary` | boolean | — | Radio/toggle; only one allowed per customer |

> **Primary rule:** Only one bank account per customer can have `isPrimary: true`. If user selects a new primary, deselect the previous one on frontend before submitting. Sending more than one primary returns a **400 error**.

---

## Bank Account Lifecycle Summary

```
POST /customers/              → Customer created + bank accounts created
PUT  /customers/:id/          → Customer updated + banks reconciled (create / update / delete)
PATCH /customers/:id/         → Partial update; banks reconciled only if bankAccounts key present
DELETE /customers/:id/        → Customer deleted + ALL bank accounts CASCADE deleted
```

---

## Permission Codes

| Action | Required Permission |
|--------|-------------------|
| List / Retrieve | `customers.view` |
| Create | `customers.add` |
| Update (PUT/PATCH) | `customers.change` |
| Delete | `customers.delete` |

Superusers bypass all permission checks.

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
| `404` | Not found | "Customer not found" |
| `500` | Server error | Generic error message |

### Validation Error Shape `400`

```json
{
  "customerName": ["A customer with this name already exists."],
  "email": ["A customer with this email already exists."],
  "bankAccounts": ["Only one bank account can be marked as primary."]
}
```

### React Error Handling Example

```js
try {
  await axios.post('/api/v1/sales/customers/', payload, { headers })
} catch (error) {
  if (error.response?.status === 400) {
    const errors = error.response.data
    setFormErrors(errors)
    // errors.customerName?.[0] → "A customer with this name already exists."
    // errors.bankAccounts?.[0] → "Only one bank account can be marked as primary."
  }
}
```

---

## TypeScript Types (Reference)

```ts
export interface CustomerBankAccount {
  id?: number           // present on existing accounts; omit on new
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

export interface Customer {
  id?: number
  customerCode?: string     // read-only, auto-generated CUS-XXXX
  customerName: string
  companyName?: string
  address?: string
  phone: string
  email?: string
  contactPerson: string
  customerType?: 'Wholesaler' | 'Retailer' | 'Distributor' | 'Manufacturer' | 'Exporter' | 'General' | 'Other'
  status?: 'Active' | 'Inactive' | 'Blocked'
  registrationNumber?: string
  bankAccounts?: CustomerBankAccount[]
  bankAccountCount?: number   // list view only, read-only
  createdBy?: { id: number; username: string; fullName: string }
  updatedBy?: { id: number; username: string; fullName: string }
  createdAt?: string
  updatedAt?: string
}

export interface PaginatedCustomers {
  success: boolean
  count: number
  totalPages: number
  currentPage: number
  pageSize: number
  results: Customer[]
}

export interface CustomerStats {
  totalCustomers: number
  byStatus: Record<string, number>
  byType: Record<string, number>
}
```

---

## Full Form Submit Flow

```
1. Open "Add Customer" form
   → GET /api/v1/sales/customers/choices/        populate dropdowns

2. User fills customer fields + adds bank account rows

3. Submit
   → POST /api/v1/sales/customers/
   → 201: success toast → redirect to list or detail page
   → 400: show field-level errors inline

4. Open "Edit Customer" form
   → GET /api/v1/sales/customers/:id/            pre-fill all fields
   → Each existing bank row has an id — store it in form state

5. User edits / adds / removes bank rows

6. Submit
   → PUT /api/v1/sales/customers/:id/
   → Existing rows: keep id field
   → New rows: no id field
   → Removed rows: simply exclude from array
   → 200: success toast

7. Delete customer
   → Show confirm dialog
   → DELETE /api/v1/sales/customers/:id/
   → 200: remove from UI list
```
