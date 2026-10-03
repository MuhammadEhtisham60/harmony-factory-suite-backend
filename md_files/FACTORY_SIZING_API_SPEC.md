# Factory Sizing Entry API
### Frontend Integration Guide

## Base URL and Authentication

Use the backend API base URL followed by `/sizings/`. For example:

```text
http://<host>/api/v1/sizings/
```

All endpoints require an authenticated access token and JSON content:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json
```

## Sizing Entry Fields

| API field | Type | Required | Description |
|---|---|---:|---|
| `sizingName` | string | Yes on create/full update | Sizing company or unit name |
| `address` | string | No | Address |
| `contactNumber` | string | No | Contact phone number |
| `phoneNo` | string | No | Backward-compatible alias for `contactNumber` |
| `contactPerson` | string | No | Contact person's name |
| `email` | string | No | Contact email |
| `status` | string | No | `Active` or `Inactive`; defaults to `Active` |
| `notes` | string | No | Additional notes |

The API stores the contact number in its existing `phone_no` field. Both `contactNumber` and `phoneNo` are accepted; responses include both names for compatibility.

## CRUD Endpoints

| Method | Endpoint | Permission | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/sizings/` | `sizing.view` | List sizing entries |
| `POST` | `/api/v1/sizings/` | `sizing.add` | Create an entry |
| `GET` | `/api/v1/sizings/{id}/` | `sizing.view` | Get one entry |
| `PUT` | `/api/v1/sizings/{id}/` | `sizing.edit` | Replace an entry; send all editable fields |
| `PATCH` | `/api/v1/sizings/{id}/` | `sizing.edit` | Update only supplied fields |
| `DELETE` | `/api/v1/sizings/{id}/` | `sizing.delete` | Delete an entry |

### Create

```http
POST /api/v1/sizings/
```

```json
{
  "sizingName": "North Sizing Works",
  "address": "12 Mill Road, Faisalabad",
  "contactNumber": "0301-5550123",
  "status": "Active"
}
```

Successful create returns `201 Created`:

```json
{
  "success": true,
  "message": "Sizing created successfully.",
  "data": {
    "id": 7,
    "sizingName": "North Sizing Works",
    "contactPerson": "",
    "contactNumber": "0301-5550123",
    "phoneNo": "0301-5550123",
    "email": "",
    "address": "12 Mill Road, Faisalabad",
    "status": "Active",
    "notes": "",
    "createdBy": null,
    "updatedBy": null,
    "createdAt": "2026-10-03T09:00:00Z",
    "updatedAt": "2026-10-03T09:00:00Z"
  }
}
```

### Read and List

`GET /api/v1/sizings/{id}/` returns the same `success` and `data` envelope as create. List results use the standard pagination shape:

```json
{
  "success": true,
  "count": 1,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": []
}
```

Supported list query parameters:

| Parameter | Example | Behavior |
|---|---|---|
| `page` | `?page=2` | Select page |
| `page_size` | `?page_size=25` | Set page size (maximum 100) |
| `status` | `?status=Active` | Filter by `Active` or `Inactive` |
| `search` | `?search=North` | Search sizing name, contact person, phone, email, or address |
| `ordering` | `?ordering=sizing_name` | Order by `sizing_name`, `status`, `created_at`, or `updated_at`; prefix with `-` for descending order |

### Update

Use `PUT` with the complete editable entry, or `PATCH` to change only selected fields:

```http
PATCH /api/v1/sizings/7/
```

```json
{
  "address": "18 Mill Road, Faisalabad",
  "contactNumber": "0302-5550123",
  "status": "Inactive"
}
```

### Delete

```http
DELETE /api/v1/sizings/7/
```

Successful delete returns `200 OK` with `{"success": true, "message": "Sizing deleted successfully."}`. Deletion can fail if existing sizing outcomes reference the entry because those records protect their sizing history.

## Dropdown Options

`GET /api/v1/sizings/choices/` returns active entries for selectors:

```json
{
  "success": true,
  "data": [
    { "value": 7, "label": "North Sizing Works", "contactPerson": "" }
  ]
}
```

## Errors

Invalid field values return `400 Bad Request`; for example, `status` accepts only `Active` or `Inactive`. Missing authentication returns `401 Unauthorized`, and a user without the required module permission receives `403 Forbidden`.