# Sizing Ledger – Frontend Integration Guide

> **Backend status:** Implemented and tested (`factory.tests.test_sizing_ledger`, 20 tests).  
> **Base URL:** `/api/v1/sizing-ledger/`  
> **Auth:** `Authorization: Bearer <token>` (same as the other sizing APIs)  
> **Permission:** `sizing.view` (read-only; there are no create/update/delete endpoints)  
> **Precision rule:** every number is an **exact decimal string**. Never use `Number()`, `parseFloat()`, `toFixed()` or `Math.round()` on it. See [DECIMAL_CALCULATION_PRECISION_SPEC.md](DECIMAL_CALCULATION_PRECISION_SPEC.md).

---

## 1. What the Ledger Shows

The ledger is shown from the **sizing party's point of view**. It merges two sources into one chronological list:

| Entry type | `entryType` | Meaning | Source |
| :--- | :--- | :--- | :--- |
| **Income** | `income` | Yarn sent to the sizing party | Yarn Outcome with type **Sizing** |
| **Outcome** | `outcome` | Set returned from sizing, and the yarn it used (lagat) | Sizing Outcome |

Each row carries **running balances for its own sizing party**. When the tab shows "All sizings", the balances of different parties are never mixed. Select a party to see one clean ledger.

### How the values are derived
| Column | Formula |
| :--- | :--- |
| Income cones | `outcome_bags × outcome_cones_per_bag` |
| Income kg | `outcome_bags × outcome_weight_per_bag_kg` |
| Income / balance lb | `kg × 2.20462262` |
| Outcome bags / cones | `lagat_bags` / `lagat_cones` of the sizing outcome |
| Outcome kg (yarn consumed) | `lagat_bags × yarn_outcome.outcome_weight_per_bag_kg` |
| Sizing charge | `rate_per_kg × net_weight_kg` (falls back to the stored `total_rate`) |
| Balance bags / cones / kg | previous balance **+ income − outcome** |
| Charges payable | running sum of sizing charges |

> **Note:** a sizing outcome's `netWeightKg` is the weight of the sized set. It is shown for information only. It does **not** reduce the yarn balance. Yarn balance uses lagat.

---

## 2. Endpoints

### 2.1 `GET /api/v1/sizing-ledger/`: ledger rows (paginated)

**Query params (all optional)**

| Param | Example | Description |
| :--- | :--- | :--- |
| `sizing` | `3` | Sizing party id (use `/api/v1/sizings/choices/` for the dropdown) |
| `date_from` | `2026-10-01` | Inclusive start date (`YYYY-MM-DD`) |
| `date_to` | `2026-10-31` | Inclusive end date |
| `entry_type` | `income` \| `outcome` | Show only one side |
| `set_no` | `SET-1` | Case-insensitive substring match on set number |
| `search` | `alpha` | Matches sizing name, reference, set no, set bill, remarks |
| `ordering` | `date` (default) \| `-date` | Oldest first, or newest first. Balances are identical either way. |
| `page`, `page_size` | `1`, `20` | Standard pagination (`page_size` max 100) |

**Response**
```json
{
  "success": true,
  "count": 4,
  "totalPages": 1,
  "currentPage": 1,
  "pageSize": 10,
  "openingBalance": {
    "balanceBags": "6.666667",
    "balanceCones": "159.999999",
    "balanceWeightKg": "300.8230...",
    "balanceWeightLb": "663.17...",
    "chargesPayable": "1219.2..."
  },
  "results": [ /* row objects, see 2.1.1 */ ]
}
```

- `openingBalance` is the party's balance **just before `date_from`**.
  - It is `null` when no `sizing` filter is given.
  - It is all zeros when there is no `date_from` or no earlier activity.
- Use it to render an "Opening balance" line above the first row.

#### 2.1.1 Row object

```json
{
  "id": "OUT-45",
  "entryType": "outcome",
  "date": "2026-10-05",
  "sizingId": 3,
  "sizingName": "Alpha Sizing",
  "reference": "Set #SET-1 / Bill #B-1",
  "yarnOutcomeId": 18,
  "sizingOutcomeId": 45,
  "setNo": "SET-1",
  "setBill": "B-1",

  "bagsIn": null, "conesIn": null, "weightKgIn": null, "weightLbIn": null,

  "bagsOut": "3.333333",
  "conesOut": "80.000001",
  "weightKgOut": "150.411496...",
  "weightLbOut": "331.57...",
  "setLengthMeter": null,
  "setLengthGaz": null,
  "shortage": null,
  "netWeightKg": "98.765432",
  "ratePerKg": "12.345678",
  "sizingCharge": "1219.3...",

  "balanceBags": "6.666667",
  "balanceCones": "159.999999",
  "balanceWeightKg": "300.8230...",
  "balanceWeightLb": "663.17...",
  "chargesPayable": "1219.3...",

  "remarks": ""
}
```

| Field group | Income row | Outcome row |
| :--- | :--- | :--- |
| `bagsIn`, `conesIn`, `weightKgIn`, `weightLbIn` | filled | `null` |
| `bagsOut`, `conesOut`, `weightKgOut`, `weightLbOut` | `null` | filled |
| `setLengthMeter`, `setLengthGaz`, `shortage`, `netWeightKg`, `ratePerKg`, `sizingCharge` | `null` | filled (an individual one may still be `null` if not entered) |
| `sizingOutcomeId`, `setNo`, `setBill` | `null` / `""` | filled |
| `balance*`, `chargesPayable` | always filled | always filled |

- `id` is `IN-<yarnOutcomeId>` or `OUT-<sizingOutcomeId>`. It is unique across both types, so use it as the React `key`.
- Ordering inside the same date: income rows come before outcome rows, then by creation time.

> **Precision note:** `weightKgOut`, `sizingCharge`, etc. are products of 6-decimal values, so they can have **up to 12 decimals**. The API returns them in full, with no rounding. Display them as returned.

### 2.2 `GET /api/v1/sizing-ledger/summary/`: totals for the cards

Takes the **same filter params** as the list (pagination params are ignored).

```json
{
  "success": true,
  "data": {
    "totals": {
      "entries": 4,
      "totalBagsIn": "15.000000", "totalConesIn": "360.000000",
      "totalWeightKgIn": "676.85...", "totalWeightLbIn": "1492.1...",
      "totalBagsOut": "4.833333", "totalConesOut": "116.000001",
      "totalWeightKgOut": "218.1...", "totalWeightLbOut": "480.8...",
      "totalSizingCharge": "1724.3...",
      "balanceBags": "10.166667", "balanceCones": "243.999999",
      "balanceWeightKg": "458.6...", "balanceWeightLb": "1011.2...",
      "chargesPayable": "1724.3..."
    },
    "parties": [
      { "sizingId": 3, "sizingName": "Alpha Sizing", "entries": 4, "...same fields as totals...": "..." }
    ],
    "openingBalance": null
  }
}
```

- `balance*` / `chargesPayable` = the **closing balance** of the last row in the filtered set. In `totals` it is the sum of each party's closing balance.
- `parties` is sorted by sizing name, which is handy for a per-party breakdown table when "All sizings" is selected.

### 2.3 `GET /api/v1/sizing-ledger/export/`: CSV download

Same filter params. Returns `text/csv` (`sizing-ledger.csv`) with **all** filtered rows, not just one page. Values are written at full precision. Empty cells mean "not applicable".

Because it needs the auth header, download it with `fetch`/axios as a blob. A plain `<a href>` will not send the token.

```js
export async function downloadSizingLedgerCsv(params) {
  const res = await api.get("/sizing-ledger/export/", { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = Object.assign(document.createElement("a"), { href: url, download: "sizing-ledger.csv" });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
```

### 2.4 Error responses
Invalid params return `400`:
```json
{ "date_from": ["Enter a valid date in YYYY-MM-DD format."] }
```
Possible keys: `sizing`, `date_from`, `date_to`, `entry_type`, `ordering`. `date_from` after `date_to` also returns `400`. A user without `sizing.view` gets `403`.

---

## 3. Recommended UI

### 3.1 Layout of the "Sizing Ledger" tab
1. **Filter bar:** sizing dropdown (include an "All sizings" option), date range, type toggle (All / Income / Outcome), search box, set no, **Export CSV** button.
2. **Summary cards** (from `/summary/`): Total Income, Total Outcome, Current Balance (bags, cones, kg), Charges Payable.
3. **Opening balance line** (only when a sizing and `date_from` are selected, using `openingBalance`).
4. **Ledger table** (paginated server-side).

### 3.2 Table columns
| Group | Columns |
| :--- | :--- |
| Info | Date, Type badge, Sizing (hide when one party is selected), Reference |
| **In** | Bags, Cones, Weight kg, Weight lb |
| **Out** | Bags, Cones, Weight kg |
| Set details | Set length (m / gaz), Shortage, Net kg, Rate/kg, Sizing charge |
| **Balance** | Bags, Cones, Weight kg, Weight lb, Charges payable |

Suggested styling: **Income** = green badge, **Outcome** = amber badge. Use right-aligned tabular numerals and horizontal scroll for the wide table. Show a dash `—` for `null`. Because values can be long (up to 12 decimals), allow the cell to expand or show a tooltip with the full value. **Do not truncate with `toFixed()`.**

### 3.3 Interaction
- Changing any filter resets to page 1 and refetches both the list and the summary.
- Debounce the search box (about 300 ms).
- Row click on an `OUT-` row: open the existing sizing outcome detail using `sizingOutcomeId` (`/api/v1/sizing-outcomes/{id}/`).
- Row click on an `IN-` row: open the yarn outcome detail using `yarnOutcomeId`.
- Loading skeleton and an empty state ("No sizing activity for these filters").

---

## 4. Example Code

### 4.1 API service (`sizingLedgerApi.js`)
```js
import api from "./api"; // your configured axios instance with auth

const clean = (params) =>
  Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));

export const getSizingLedger = (params) =>
  api.get("/sizing-ledger/", { params: clean(params) }).then((r) => r.data);

export const getSizingLedgerSummary = (params) => {
  const { page, page_size, ...filters } = params; // pagination is ignored by the summary
  return api.get("/sizing-ledger/summary/", { params: clean(filters) }).then((r) => r.data.data);
};
```

### 4.2 Rendering values (no rounding)
```jsx
import { formatFullPrecision } from "../../utils/decimal";

const Num = ({ value }) =>
  value === null || value === undefined ? <span>—</span> : <span>{formatFullPrecision(value)}</span>;

// <td className="num"><Num value={row.balanceWeightKg} /></td>
```

### 4.3 Client-side math (only if you really need it)
Use the helpers in `src/utils/decimal.js`. Never feed formatted text back into a calculation.
```js
import { decAdd, decSub } from "../../utils/decimal";

// e.g. "net movement" for a row
const net = decSub(row.weightKgIn ?? "0", row.weightKgOut ?? "0").toString();
```
Prefer using the server's `balance*` values. They already include every earlier row, even rows on other pages.

### 4.4 Filter state sketch
```jsx
const [filters, setFilters] = useState({
  sizing: "", date_from: "", date_to: "", entry_type: "", search: "", set_no: "",
  ordering: "date", page: 1, page_size: 20,
});

useEffect(() => {
  const ctrl = new AbortController();
  Promise.all([getSizingLedger(filters), getSizingLedgerSummary(filters)]).then(([list, sum]) => {
    setRows(list.results);
    setMeta({ count: list.count, totalPages: list.totalPages, opening: list.openingBalance });
    setSummary(sum.totals);
  });
  return () => ctrl.abort();
}, [filters]);
```

---

## 5. Behaviours to Know

| Behaviour | Detail |
| :--- | :--- |
| Balances are cumulative | Date, type and search filters only hide rows. They never restart the balance. Page 2 continues from page 1. |
| Edits and deletes | The ledger is computed live. After editing or deleting a Yarn Outcome or Sizing Outcome, just refetch. |
| Only sizing yarn outcomes | Yarn outcomes of type **Weft** or **Sold** never appear. |
| Zero-quantity rows | A Yarn Outcome with 0 bags still appears as an income row with zeros. |
| Negative balances | If more yarn is booked out than was sent in, the balance goes negative. The API does not clamp it. Highlight negative balances in red. |
| No float anywhere | Values are strings such as `"12.345678"`. Compare or add them only with `decimal.js`. |

---

## 6. Quick Test (curl)
```bash
# one party, October, newest first
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/sizing-ledger/?sizing=3&date_from=2026-10-01&date_to=2026-10-31&ordering=-date"

# totals
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/sizing-ledger/summary/?sizing=3"

# CSV
curl -H "Authorization: Bearer $TOKEN" -o sizing-ledger.csv "http://localhost:8000/api/v1/sizing-ledger/export/?sizing=3"
```

---

## 7. Backend Files (for reference)
- [factory/yarn/sizing/ledger.py](file:///e:/loom/harmony-factory-suite-backend/factory/yarn/sizing/ledger.py): row building, running balances, summary
- [factory/yarn/sizing/ledger_serializers.py](file:///e:/loom/harmony-factory-suite-backend/factory/yarn/sizing/ledger_serializers.py): exact-decimal serializers
- [factory/yarn/sizing/ledger_views.py](file:///e:/loom/harmony-factory-suite-backend/factory/yarn/sizing/ledger_views.py): list / summary / export endpoints
- [factory/yarn/sizing/urls.py](file:///e:/loom/harmony-factory-suite-backend/factory/yarn/sizing/urls.py): `sizing-ledger` route
- [factory/tests/test_sizing_ledger.py](file:///e:/loom/harmony-factory-suite-backend/factory/tests/test_sizing_ledger.py): 20 tests
