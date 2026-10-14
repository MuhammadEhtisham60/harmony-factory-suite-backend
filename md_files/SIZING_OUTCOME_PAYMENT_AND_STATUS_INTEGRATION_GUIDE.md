# Sizing Outcome Status & Payment Fields – Frontend Integration Guide

> **Module:** Yarn – Sizing Outcome & Accounting  
> **Backend Framework:** Django REST Framework (DRF)  
> **Authentication:** `Authorization: Bearer <access_token>`  
> **Permission Code:** `sizing.view`, `sizing.add`, `sizing.edit`  
> **Precision Compliance:** Full decimal precision preserved across all intermediate and final calculations without premature rounding.

---

## 1. Overview of Changes

1. **YarnOutcome Status Management**:
   - `yarn_outcome.status` previously transitioned unconditionally to `"Received"` upon creating any sizing outcome.
   - It now accurately identifies partial returns and transitions to `"Partially Received"` if not all bags dispatched have been consumed/received or if sizing stock remains at the mill.
   - Automatically synchronizes across creation, partial update (`PATCH`), full update (`PUT`), and deletion (`DELETE`).

2. **Sizing Outcome Payment Fields**:
   - Added `amount_paid` (`amountPaid`), `amount_due` (`amountDue`), and `payment_status` (`paymentStatus`) to `SizingOutcome`.
   - `amount_due` and `payment_status` are automatically calculated on the backend from `total_rate` and `amount_paid`.
   - Supports filtering sizing outcomes by `payment_status` (`Unpaid`, `Partially Paid`, `Paid`).
   - Payment fields are also exposed in Sizing Detail Ledger transaction rows.

---

## 2. Business Logic & Status Transitions

### 2.1 Yarn Outcome Status Rules

| Status | Condition | Meaning | UI Badge Recommendation |
| :--- | :--- | :--- | :--- |
| **`In Sizing`** | No sizing outcomes exist yet, or total lagat bags consumed = 0. | Dispatched to mill; processing has not yet returned beams. | `bg-blue-100 text-blue-800` |
| **`Partially Received`** | `0 < sum(lagat_bags) < outcome_bags` **OR** `remaining_bags_on_sizing_stock > 0`. | Mill returned some beams/sets, but yarn bags remain at sizing. | `bg-amber-100 text-amber-800` |
| **`Received`** | $\sum \text{lagat\_bags} \ge \text{outcome\_bags}$ **AND** `remaining_bags_on_sizing_stock == 0`. | All dispatched yarn bags have been fully returned or consumed. | `bg-emerald-100 text-emerald-800` |

#### Serializer Status Indicators on `/api/v1/yarn-outcomes/`:
- `status`: String (`"In Sizing"`, `"Partially Received"`, `"Received"`, `"Dispatched"`, `"Completed"`).
- `isReceived`: Boolean (`true` **only** if status is `"Received"`).
- `isPartiallyReceived`: Boolean (`true` if status is `"Partially Received"`, `false` otherwise).

#### Serializer Status Indicators on `/api/v1/sizing-outcomes/`:
- `yarnOutcomeStatus`: String (e.g. `"Partially Received"` or `"Received"`).
- `yarnOutcomeDetail.status`: String (e.g. `"Partially Received"` or `"Received"`).

---

### 2.2 Sizing Outcome Payment Rules

| Metric | Source / Formula | Meaning |
| :--- | :--- | :--- |
| **`total_rate` (`totalRate`)** | $\text{net\_weight\_kg} \times \text{rate\_per\_kg}$ | Total sizing service charge billed for this set. |
| **`amount_paid` (`amountPaid`)** | User input (default `0.000000`) | Sizing charges paid so far to the mill. |
| **`amount_due` (`amountDue`)** | $\max(0, \text{total\_rate} - \text{amount\_paid})$ | Remaining balance due for this set invoice. |
| **`payment_status` (`paymentStatus`)** | Derived automatically | `"Unpaid"`, `"Partially Paid"`, or `"Paid"`. |

#### Payment Status Evaluation Table:
- If `amount_paid == 0`: `payment_status = "Unpaid"`, `amount_due = total_rate`.
- If `0 < amount_paid < total_rate`: `payment_status = "Partially Paid"`, `amount_due = total_rate - amount_paid`.
- If `amount_paid >= total_rate` (where `total_rate > 0`): `payment_status = "Paid"`, `amount_due = 0.000000`.

---

## 3. API Endpoints Specification

### 3.1 Create Sizing Outcome (`POST /api/v1/sizing-outcomes/`)

Create a return set from sizing. You may optionally supply initial `amountPaid` or leave it to default to `0` (`Unpaid`).

#### Request Payload (`POST`)

```json
{
  "yarnOutcomeId": 101,
  "outcomeDate": "2026-10-15",
  "setNo": "SET-442",
  "setBill": "BILL-901",
  "sizingName": "Star Sizing Mill",
  "totalBagsOnSizing": 20,
  "bagPackingCone": 24,
  "totalCones": 480,
  "lagatBags": "8.500000",
  "lagatCones": "204.000000",
  "remainingBagsOnSizingStock": 11,
  "remainingConesOnSizingStock": 276,
  "ratePerKg": "15.000000",
  "netWeightKg": "385.500000",
  "amountPaid": "2000.000000",
  "remarks": "First batch of warp beams received"
}
```

#### Response (`201 Created`)

```json
{
  "success": true,
  "message": "Sizing outcome #25 created successfully with 0 beam(s).",
  "data": {
    "id": 25,
    "yarnOutcomeId": 101,
    "yarnOutcomeStatus": "Partially Received",
    "yarnOutcomeDetail": {
      "id": 101,
      "outcome_type": "Sizing",
      "outcome_bags": 20,
      "yarnName": "Cotton 30/1 Carded",
      "yarnType": "Carded",
      "yarnCount": "30/1",
      "intakeSetNo": "LOT-100",
      "sizingName": "Star Sizing Mill",
      "status": "Partially Received"
    },
    "setNo": "SET-442",
    "setBill": "BILL-901",
    "sizingName": "Star Sizing Mill",
    "lagatBags": "8.500000",
    "lagatCones": "204.000000",
    "remainingBagsOnSizingStock": 11,
    "remainingConesOnSizingStock": 276,
    "ratePerKg": "15.000000",
    "netWeightKg": "385.500000",
    "totalRate": "5782.500000",
    "amountPaid": "2000.000000",
    "amountDue": "3782.500000",
    "paymentStatus": "Partially Paid",
    "outcomeDate": "2026-10-15",
    "remarks": "First batch of warp beams received",
    "totalBeams": 0,
    "beamAssignments": [],
    "beamLoadings": []
  }
}
```

---

### 3.2 Update Sizing Outcome / Record Payment (`PATCH /api/v1/sizing-outcomes/{id}/`)

Used to update sizing set specifications or record additional payments made for sizing charges.

#### Recording an Additional Payment (`PATCH`)

```json
{
  "amountPaid": "5782.500000"
}
```

#### Response (`200 OK`)

```json
{
  "success": true,
  "message": "Sizing outcome updated successfully.",
  "data": {
    "id": 25,
    "totalRate": "5782.500000",
    "amountPaid": "5782.500000",
    "amountDue": "0.000000",
    "paymentStatus": "Paid"
  }
}
```

---

### 3.3 List Sizing Outcomes with Payment Filters (`GET /api/v1/sizing-outcomes/`)

#### Query Parameters:
| Parameter | Type | Options / Description | Example |
| :--- | :--- | :--- | :--- |
| `payment_status` | `string` | Filter by payment status: `Unpaid`, `Partially Paid`, `Paid` | `?payment_status=Unpaid` |
| `yarn_outcome` | `integer` | Filter outcomes belonging to a specific yarn dispatch | `?yarn_outcome=101` |
| `sizing` | `integer` | Filter by sizing unit ID | `?sizing=3` |
| `ordering` | `string` | Sort: `outcome_date`, `amount_paid`, `amount_due`, `payment_status` | `?ordering=-amount_due` |

---

## 4. Frontend Integration Snippets

### 4.1 Status Badge Component (`StatusBadge.jsx`)

```jsx
import React from "react";

export const YarnOutcomeStatusBadge = ({ status }) => {
  const styles = {
    "In Sizing": "bg-blue-100 text-blue-800 border-blue-200",
    "Partially Received": "bg-amber-100 text-amber-800 border-amber-200 font-medium",
    "Received": "bg-emerald-100 text-emerald-800 border-emerald-200",
    "Dispatched": "bg-purple-100 text-purple-800 border-purple-200",
  };

  const currentStyle = styles[status] || "bg-gray-100 text-gray-800 border-gray-200";

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${currentStyle}`}>
      {status || "Unknown"}
    </span>
  );
};

export const SizingPaymentStatusBadge = ({ paymentStatus, amountDue }) => {
  const styles = {
    "Unpaid": "bg-red-100 text-red-800 border-red-200",
    "Partially Paid": "bg-yellow-100 text-yellow-800 border-yellow-200 font-medium",
    "Paid": "bg-emerald-100 text-emerald-800 border-emerald-200",
  };

  const currentStyle = styles[paymentStatus] || "bg-gray-100 text-gray-800 border-gray-200";

  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${currentStyle}`}>
      <span>{paymentStatus}</span>
      {paymentStatus !== "Paid" && amountDue && Number(amountDue) > 0 && (
        <span className="text-xs opacity-75 font-normal">
          (Due: {amountDue})
        </span>
      )}
    </span>
  );
};
```

### 4.2 Sizing Outcome Payment Modal / Inline Payment Update

```javascript
import api from "../services/api";

/**
 * Record a payment against a SizingOutcome.
 * @param {number} outcomeId
 * @param {string|number} newTotalPaidAmount
 */
export const updateSizingPayment = async (outcomeId, newTotalPaidAmount) => {
  const response = await api.patch(`/sizing-outcomes/${outcomeId}/`, {
    amountPaid: String(newTotalPaidAmount),
  });
  return response.data;
};

/**
 * Quick action: Mark Sizing Outcome as Fully Paid
 * @param {object} sizingOutcome
 */
export const markOutcomeFullyPaid = async (sizingOutcome) => {
  const response = await api.patch(`/sizing-outcomes/${sizingOutcome.id}/`, {
    amountPaid: sizingOutcome.totalRate,
  });
  return response.data;
};
```

---

## 5. Summary of API Fields

| Field Name (JSON) | Type | Writable | Calculation Rule / Notes |
| :--- | :--- | :--- | :--- |
| `yarnOutcomeStatus` | `string` | Read-only | Status of linked yarn outcome (`In Sizing`, `Partially Received`, `Received`). |
| `amountPaid` / `amount_paid` | `string` (Decimal) | Yes | Sizing charges paid so far. Default `"0.000000"`. |
| `amountDue` / `amount_due` | `string` (Decimal) | Read-only | Automatically calculated as `totalRate - amountPaid`. |
| `paymentStatus` / `payment_status` | `string` | Optional / Computed | `"Unpaid"`, `"Partially Paid"`, `"Paid"`. |
| `isReceived` (on YarnOutcome) | `boolean` | Read-only | `true` only if fully received. |
| `isPartiallyReceived` (on YarnOutcome)| `boolean` | Read-only | `true` if partially received. |
