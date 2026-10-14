# Main & Individual Sizing Ledger – Frontend API Integration Guide

> **Module:** Factory – Sizing Ledger & Accounting  
> **Backend Framework:** Django REST Framework (DRF)  
> **Authentication:** `Authorization: Bearer <access_token>`  
> **Permission Code:** `sizing.view` (Read-only operations)  
> **Precision Compliance:** Full decimal precision preserved across all intermediate and final calculations. All numeric quantities and monetary values are returned as exact strings (e.g. `"10.166667"`, `"1724.326221"`).  

---

## 1. Architecture & Overview

The Sizing Ledger system provides two distinct views for the frontend application:

1. **Main Sizing Ledger (`GET /api/v1/sizing-ledger/`)**:
   - Master list of all sizing mill units/parties (`Sizing`).
   - Per-sizing summary counters for each mill row: `totalBoxesSent`, `totalBoxesReceived`, `totalBoxesBalance`, `totalPayables`, `totalWeightKgSent`, etc.
   - Global aggregate counters computed across the **entire filtered dataset** (not just the current pagination page).
   - Server-side filtering by `search`, `status`, `date_from`, `date_to`, and `ordering`.

2. **Individual Sizing Ledger (`GET /api/v1/sizing-ledger/{id}/` or `GET /api/v1/sizings/{id}/ledger/`)**:
   - Master detail of the selected sizing mill (`sizing`).
   - Chronological ledger transactions (`results` / `transactions`) belonging strictly to that sizing mill.
   - Exact running balances for every transaction row (`balanceBags`, `balanceCones`, `balanceWeightKg`, `balanceWeightLb`, `chargesPayable`).
   - Opening balance (`openingBalance`) calculated immediately prior to `date_from`.
   - Single-mill summary counters (`totalBoxesSent`, `totalBoxesReceived`, `totalBoxesBalance`, `totalPayables`).

---

## 2. Business Logic & Counter Formulas

### 2.1 Formula Definitions

| Metric | Source Model | Field & Derivation Rule | Meaning |
| :--- | :--- | :--- | :--- |
| **Boxes Sent** (`totalBoxesSent`) | `YarnOutcome` | $\sum \text{outcome\_bags}$ where `outcome_type = 'Sizing'` | Total boxes/bags of yarn dispatched from warehouse to the sizing mill. |
| **Boxes Received** (`totalBoxesReceived`) | `SizingOutcome` | $\sum \text{lagat\_bags}$ | Total boxes/bags of yarn consumed/received in sized beams (Lagat). |
| **Boxes in Balance** (`totalBoxesBalance`) | Derived | $\text{totalBoxesSent} - \text{totalBoxesReceived}$ | Yarn boxes/bags currently remaining on hand at the sizing mill. |
| **Total Payables** (`totalPayables`) | `SizingOutcome` | $\sum \text{total\_rate}$ where $\text{total\_rate} = \text{rate\_per\_kg} \times \text{net\_weight\_kg}$ | Cumulative sizing service charges billed by the sizing mill. |
| **Weight Sent (KG)** (`totalWeightKgSent`) | `YarnOutcome` | $\sum (\text{outcome\_bags} \times \text{outcome\_weight\_per\_bag\_kg})$ | Total net yarn kilograms sent to sizing mill. |
| **Weight Received (KG)** (`totalWeightKgReceived`)| `SizingOutcome` | $\sum \text{net\_weight\_kg}$ | Total net weight of sized yarn returned on beams. |
| **Weight in Balance (KG)** (`totalWeightKgBalance`)| Derived | $\text{totalWeightKgSent} - \text{totalWeightKgReceived}$ | Net kilograms remaining at sizing mill. |
| **Cones Sent** (`totalConesSent`) | `YarnOutcome` | $\sum (\text{outcome\_bags} \times \text{outcome\_cones\_per\_bag})$ | Total cones sent to sizing mill. |
| **Cones Received** (`totalConesReceived`) | `SizingOutcome` | $\sum \text{lagat\_cones}$ | Total cones consumed in sizing sets. |
| **Cones in Balance** (`totalConesBalance`) | Derived | $\text{totalConesSent} - \text{totalConesReceived}$ | Cones remaining on hand at sizing mill. |

### 2.2 Accounting & Join Multiplication Rules
1. **No Cartesian Join Duplication**: A single `YarnOutcome` can be referenced by multiple `SizingOutcome` records. The backend executes independent group-by aggregations on `YarnOutcome` and `SizingOutcome`. This prevents SQL join cartesian explosion and guarantees that `totalBoxesSent` is never artificially multiplied.
2. **Yarn Outcomes Are Not Financial Payments**: In `YarnOutcome`, `total_price = 0` for sizing outcomes because yarn remains factory-owned raw material dispatched for processing.
3. **Payables**: Represent service charges owed to the sizing mill for work done (`total_rate = rate_per_kg * net_weight_kg`). No separate payment model currently exists; if disbursements are introduced in the future, $\text{Payables Balance} = \text{Total Charges} - \text{Total Disbursements}$.

---

## 3. API Endpoints Specification

### 3.1 Main Sizing Ledger API

- **Method**: `GET`
- **URL**: `/api/v1/sizing-ledger/`
- **Description**: Returns all sizing records with per-sizing counters, aggregate totals across all filtered records, and pagination.

#### Query Parameters

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `search` | `string` | No | Case-insensitive search on `sizing_name`, `contact_person`, `phone_no`, `email`, `address` | `?search=star` |
| `status` | `string` | No | Filter by sizing status (`Active` or `Inactive`) | `?status=Active` |
| `date_from` | `string` | No | Inclusive transaction start date (`YYYY-MM-DD`) | `?date_from=2026-10-01` |
| `date_to` | `string` | No | Inclusive transaction end date (`YYYY-MM-DD`) | `?date_to=2026-10-31` |
| `ordering` | `string` | No | Sort field: `sizing_name`, `status`, `created_at`, `total_boxes_sent`, `total_boxes_received`, `total_boxes_balance`, `total_payables`, `transactions_count` (prefix with `-` for descending) | `?ordering=-total_payables` |
| `page` | `integer`| No | Current page number (default: `1`) | `?page=1` |
| `page_size` | `integer`| No | Page size (default: `10`, max: `100`) | `?page_size=20` |

#### Response Payload (`200 OK`)

```json
{
  "success": true,
  "count": 2,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "summary": {
    "totalPayables": "1724.326221",
    "totalBoxesSent": "15.000000",
    "totalBoxesReceived": "4.833333",
    "totalBoxesBalance": "10.166667",
    "totalWeightKgSent": "676.851855",
    "totalWeightKgReceived": "149.265432",
    "totalWeightKgBalance": "527.586423",
    "totalConesSent": "360.000000",
    "totalConesReceived": "116.000001",
    "totalConesBalance": "243.999999",
    "totalSizingsCount": 2
  },
  "totalPayables": "1724.326221",
  "totalBoxesSent": "15.000000",
  "totalBoxesReceived": "4.833333",
  "totalBoxesBalance": "10.166667",
  "openingBalance": null,
  "results": [
    {
      "id": 1,
      "sizingName": "Alpha Sizing",
      "contactPerson": "Ali Khan",
      "contactNumber": "0300-1111111",
      "phoneNo": "0300-1111111",
      "email": "alpha@example.com",
      "address": "Faisalabad Sector 1",
      "status": "Active",
      "notes": "Primary cotton sizing mill",
      "totalBoxesSent": "15.000000",
      "totalBoxesReceived": "4.833333",
      "totalBoxesBalance": "10.166667",
      "totalPayables": "1724.326221",
      "totalWeightKgSent": "676.851855",
      "totalWeightKgReceived": "149.265432",
      "totalWeightKgBalance": "527.586423",
      "totalConesSent": "360.000000",
      "totalConesReceived": "116.000001",
      "totalConesBalance": "243.999999",
      "transactionsCount": 4,
      "createdAt": "2026-10-01T08:00:00Z",
      "updatedAt": "2026-10-12T14:30:00Z"
    },
    {
      "id": 2,
      "sizingName": "Beta Sizing",
      "contactPerson": "Bilal Ahmed",
      "contactNumber": "0300-2222222",
      "phoneNo": "0300-2222222",
      "email": "beta@example.com",
      "address": "Faisalabad Sector 2",
      "status": "Active",
      "notes": "",
      "totalBoxesSent": "0",
      "totalBoxesReceived": "0",
      "totalBoxesBalance": "0",
      "totalPayables": "0",
      "totalWeightKgSent": "0",
      "totalWeightKgReceived": "0",
      "totalWeightKgBalance": "0",
      "totalConesSent": "0",
      "totalConesReceived": "0",
      "totalConesBalance": "0",
      "transactionsCount": 0,
      "createdAt": "2026-10-01T09:00:00Z",
      "updatedAt": "2026-10-01T09:00:00Z"
    }
  ]
}
```

---

### 3.2 Individual Sizing Detail Ledger API

- **Method**: `GET`
- **URL**: `/api/v1/sizing-ledger/{id}/`  
  *(Alternative compatible endpoint: `GET /api/v1/sizings/{id}/ledger/`)*
- **Description**: Returns mill details, single-mill counters, and chronological transactions with per-row running balances.

#### Query Parameters

| Parameter | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `date_from` | `string` | No | Inclusive start date (`YYYY-MM-DD`). Computes `openingBalance` prior to this date. | `?date_from=2026-10-10` |
| `date_to` | `string` | No | Inclusive end date (`YYYY-MM-DD`) | `?date_to=2026-10-31` |
| `entry_type` | `string` | No | Filter by entry type: `income` (sent) or `outcome` (returned) | `?entry_type=outcome` |
| `set_no` | `string` | No | Substring match on sizing set number | `?set_no=SET-1` |
| `search` | `string` | No | Matches reference, set number, set bill, remarks | `?search=B-1` |
| `ordering` | `string` | No | `date` (oldest first, default) or `-date` (newest first) | `?ordering=-date` |
| `page` | `integer`| No | Current transaction page | `?page=1` |
| `page_size` | `integer`| No | Transactions per page | `?page_size=20` |

#### Response Payload (`200 OK`)

```json
{
  "success": true,
  "sizing": {
    "id": 1,
    "sizingName": "Alpha Sizing",
    "contactPerson": "Ali Khan",
    "contactNumber": "0300-1111111",
    "phoneNo": "0300-1111111",
    "email": "alpha@example.com",
    "address": "Faisalabad Sector 1",
    "status": "Active",
    "notes": "Primary cotton sizing mill",
    "createdAt": "2026-10-01T08:00:00Z",
    "updatedAt": "2026-10-12T14:30:00Z"
  },
  "summary": {
    "totalPayables": "1724.326221",
    "totalBoxesSent": "15.000000",
    "totalBoxesReceived": "4.833333",
    "totalBoxesBalance": "10.166667",
    "totalWeightKgSent": "676.851855",
    "totalWeightKgReceived": "149.265432",
    "totalWeightKgBalance": "527.586423",
    "totalConesSent": "360.000000",
    "totalConesReceived": "116.000001",
    "totalConesBalance": "243.999999"
  },
  "totalPayables": "1724.326221",
  "totalBoxesSent": "15.000000",
  "totalBoxesReceived": "4.833333",
  "totalBoxesBalance": "10.166667",
  "openingBalance": {
    "balanceBags": "6.666667",
    "balanceCones": "159.999999",
    "balanceWeightKg": "300.823000",
    "balanceWeightLb": "663.170000",
    "chargesPayable": "1219.326221"
  },
  "count": 4,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": "IN-101",
      "entryType": "income",
      "date": "2026-10-02",
      "sizingId": 1,
      "sizingName": "Alpha Sizing",
      "reference": "Yarn sent #101",
      "yarnOutcomeId": 101,
      "sizingOutcomeId": null,
      "setNo": "",
      "setBill": "",
      "bagsIn": "10.000000",
      "conesIn": "240.000000",
      "weightKgIn": "451.234570",
      "weightLbIn": "994.801968",
      "bagsOut": null,
      "conesOut": null,
      "weightKgOut": null,
      "weightLbOut": null,
      "setLengthMeter": null,
      "setLengthGaz": null,
      "shortage": null,
      "netWeightKg": null,
      "ratePerKg": null,
      "sizingCharge": null,
      "balanceBags": "10.000000",
      "balanceCones": "240.000000",
      "balanceWeightKg": "451.234570",
      "balanceWeightLb": "994.801968",
      "chargesPayable": "0",
      "remarks": ""
    },
    {
      "id": "OUT-201",
      "entryType": "outcome",
      "date": "2026-10-05",
      "sizingId": 1,
      "sizingName": "Alpha Sizing",
      "reference": "Set #SET-1 / Bill #B-1",
      "yarnOutcomeId": 101,
      "sizingOutcomeId": 201,
      "setNo": "SET-1",
      "setBill": "B-1",
      "bagsIn": null,
      "conesIn": null,
      "weightKgIn": null,
      "weightLbIn": null,
      "bagsOut": "3.333333",
      "conesOut": "80.000001",
      "weightKgOut": "150.411496333181",
      "weightLbOut": "331.600612",
      "setLengthMeter": "5400.000000",
      "setLengthGaz": "5905.511820",
      "shortage": "1.250000",
      "netWeightKg": "98.765432",
      "ratePerKg": "12.345678",
      "sizingCharge": "1219.326221002896",
      "balanceBags": "6.666667",
      "balanceCones": "159.999999",
      "balanceWeightKg": "300.823073666819",
      "balanceWeightLb": "663.201356",
      "chargesPayable": "1219.326221002896",
      "remarks": ""
    }
  ],
  "transactions": [
    /* Exact same list as results for convenience */
  ]
}
```

#### Error Responses
- `400 Bad Request`: If `{id}` cannot be parsed as an integer:
  ```json
  { "detail": "Invalid sizing ID. Must be an integer." }
  ```
- `404 Not Found`: If sizing with `{id}` does not exist:
  ```json
  { "detail": "No Sizing matches the given query." }
  ```
- `403 Forbidden`: If user does not possess `sizing.view` permission.

---

### 3.3 CSV Export API

- **Method**: `GET`
- **URL**: `/api/v1/sizing-ledger/export/`
- **Description**: Returns CSV file stream for Excel or direct download.

#### Parameters
- Default call `GET /api/v1/sizing-ledger/export/?status=Active`: Exports the **Main Sizing Summary CSV** (`sizing-ledger-summary.csv`).
- With `sizing` ID `GET /api/v1/sizing-ledger/export/?sizing=1`: Exports the **Individual Transactions CSV** (`sizing-ledger-transactions.csv`).

---

## 4. Frontend Integration Patterns

### 4.1 Safe Decimal Formatting with `src/utils/decimal.js`
The project's centralized utility [src/utils/decimal.js](file:///e:/loom/harmony-factory-suite/src/utils/decimal.js) provides zero-rounding string formatting:

```javascript
import { formatFullPrecision, isNegativeDecimal } from "../../utils/decimal";

// Format boxes or financial charges without losing decimals:
<span>{formatFullPrecision(row.totalBoxesBalance)}</span>

// Apply red badge / styling if balance goes negative:
<span className={isNegativeDecimal(row.totalBoxesBalance) ? "text-red-600 font-bold" : "text-gray-900"}>
  {formatFullPrecision(row.totalBoxesBalance)}
</span>
```

### 4.2 API Client Service Module (`sizingLedgerApi.js`)

Create a clean client service for sizing ledger requests:

```javascript
import api from "./api"; // configured axios instance with Authorization header

const cleanParams = (params) =>
  Object.fromEntries(
    Object.entries(params).filter(([, val]) => val !== "" && val !== null && val !== undefined)
  );

// 1. Fetch Main Sizing Ledger (All sizing mills with counters)
export const fetchMainSizingLedger = async (params = {}) => {
  const response = await api.get("/sizing-ledger/", { params: cleanParams(params) });
  return response.data;
};

// 2. Fetch Individual Sizing Detail Ledger
export const fetchIndividualSizingLedger = async (sizingId, params = {}) => {
  const response = await api.get(`/sizing-ledger/${sizingId}/`, { params: cleanParams(params) });
  return response.data;
};

// 3. Download CSV Export
export const downloadSizingLedgerCsv = async (params = {}, filename = "sizing-ledger.csv") => {
  const response = await api.get("/sizing-ledger/export/", {
    params: cleanParams(params),
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
```

### 4.3 Recommended React View Structure

```
SizingLedgerContainer
├── TopStatsBar (Total Payables, Total Boxes Sent, Received, Balance Cards)
├── FilterHeader (Search, Status, DateFrom, DateTo, Export CSV)
├── SizingLedgerTable (Main table listing sizing mills with counters)
│   └── SizingRow (Displays mill info, totalBoxesSent, totalBoxesReceived, totalBoxesBalance, totalPayables)
│       └── ActionButton ("View Detail Ledger" -> opens detail drawer / modal / tab)
└── IndividualLedgerModal (When a sizing mill is selected)
    ├── MillHeaderSummary (Mill details + individual totalPayables, boxes sent, received, balance)
    ├── OpeningBalanceNotice (if date_from selected)
    └── TransactionsTable (IN/OUT rows, lagat bags, sizing charge, running balance)
```
