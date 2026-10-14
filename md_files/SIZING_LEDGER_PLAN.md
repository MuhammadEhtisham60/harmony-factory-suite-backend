# Sizing Ledger – Implementation Plan

> **Status:** BACKEND IMPLEMENTED. See [SIZING_LEDGER_FRONTEND_GUIDE.md](SIZING_LEDGER_FRONTEND_GUIDE.md) for the API contract.  
> **Decisions taken for the open questions (Section 9), since no answers were given:**  
> 1. Income = yarn sent to sizing (`YarnOutcome` type Sizing). Outcome = `SizingOutcome`.  
> 2. The kg balance uses lagat: `lagat_bags × yarn_outcome.outcome_weight_per_bag_kg`. `net_weight_kg` is shown for information only.  
> 3. No yarn-value column on income rows (the stock price changes over time).  
> 4. No payment tracking. `chargesPayable` is the running sum of sizing charges.  
> 5. One endpoint for all parties or one party. Balances are kept per party.  
> 6. CSV export is included.  
> **Deviation from Section 4.3:** the ledger returns exact, non-quantized decimal strings (up to 12 decimals for products), not fixed 6-decimal strings, to honor the zero-rounding rule.  
> **Goal:** A "Sizing Ledger" tab in the frontend that shows every sizing **income** and **outcome** entry in one chronological, running-balance ledger.  
> **Constraint:** Follows the zero-rounding rule in [DECIMAL_CALCULATION_PRECISION_SPEC.md](DECIMAL_CALCULATION_PRECISION_SPEC.md).

---

## 1. What Exists Today (from codebase inspection)

| Concept | Model / Endpoint | Key Fields |
| :--- | :--- | :--- |
| Sizing party | `Sizing` → `/sizings/` | `sizing_name`, `status` |
| Yarn sent to a sizing party | `YarnOutcome` with `outcome_type="Sizing"` (FK `sizing`) | `outcome_bags`, `outcome_cones_per_bag`, `outcome_weight_kg`, `outcome_weight_lb`, `outcome_date`, `status`, `stock` |
| Set returned from sizing | `SizingOutcome` → `/sizing-outcomes/` (FK `yarn_outcome`) | `set_no`, `set_bill`, `outcome_date`, `total_bags_on_sizing`, `total_cones`, `remaining_bags_on_sizing_stock`, `remaining_cones_on_sizing_stock`, `lagat_bags`, `lagat_cones`, `set_length_meter`, `set_length_gaz`, `total_set_shortage`, `net_weight_kg`, `rate_per_kg`, `total_rate` |
| Beams on a set | `SizingBeamAssignment` | beam links, status |
| Per-party history | `GET /sizings/{id}/outcomes/` | outcomes only (no income side, no running balance) |

**Gap:** there is no single view that combines yarn sent to sizing with sets coming back, and no running balance. There is also no ledger model or endpoint anywhere in the project.

---

## 2. Ledger Definition (proposed, please confirm in Section 9)

The ledger is shown **from the sizing party's point of view**:

| Side | Meaning | Source row | Columns it fills |
| :--- | :--- | :--- | :--- |
| **INCOME (In)** | Yarn received by the sizing party | `YarnOutcome` where `outcome_type = Sizing` | bags, cones, kg, lb, yarn value |
| **OUTCOME (Out)** | Sized set returned / yarn consumed | `SizingOutcome` | lagat bags/cones, set no, set bill, length (m / gaz), shortage, net kg, sizing charge (`total_rate`) |

### Running balances per sizing party
- **Yarn balance (bags / cones / kg)** = Σ income − Σ outcome (lagat).
- **Sizing charges payable** = Σ `total_rate` of outcomes. This is a separate money column, because it is the charge for sizing work and not a yarn value.

---

## 3. Architecture Decision: Computed View, Not a New Table

| Option | Verdict |
| :--- | :--- |
| New `SizingLedgerEntry` table written by signals | Rejected. It can drift from source rows on edit or delete, and it needs a backfill migration. |
| **Read-only computed endpoint built from `YarnOutcome` + `SizingOutcome`** | **Chosen.** There is a single source of truth, edits and deletes show up immediately, and no migration is needed. It matches how `YarnStock` is recalculated from its rows. |

Both sources are merged in Python and sorted by `(date, created_at, id)`. Running balances are accumulated in `Decimal` with no `quantize`, no `float`, and no rounding.

---

## 4. Backend Plan

### 4.1 New files (inside `factory/yarn/sizing/`)
- `ledger.py` – pure service functions:
  - `build_sizing_ledger(sizing_id=None, date_from=None, date_to=None, entry_type=None, search=None)` returns ordered rows with running balances.
  - `get_sizing_ledger_summary(...)` returns totals per party.
- `ledger_serializers.py` – a read-only row serializer. All numeric fields use `DecimalField(decimal_places=6)` and are returned as strings.
- `ledger_views.py` – `SizingLedgerViewSet(ViewSet)`.
- Register the router in [urls.py](file:///e:/loom/harmony-factory-suite-backend/factory/yarn/sizing/urls.py).

### 4.2 Endpoints
| Method | URL | Purpose |
| :--- | :--- | :--- |
| GET | `/api/v1/sizing-ledger/` | Paginated ledger rows with running balances |
| GET | `/api/v1/sizing-ledger/summary/` | Total income, total outcome, balance, charges payable (per party or overall) |
| GET | `/api/v1/sizing-ledger/export/` | CSV export of the filtered ledger (full-precision strings) |

**Query params:** `sizing` (id), `date_from`, `date_to`, `entry_type` (`income` / `outcome`), `set_no`, `search`, `page`, `page_size`.  
**Permissions:** `IsAuthenticated` + `HasERPModulePermission` with `GET → sizing.view`, the same as the existing sizing viewsets. It is read-only, so no add/edit/delete permissions are needed.

### 4.3 Row shape (camelCase, matching existing serializers)
```json
{
  "id": "OUT-45",
  "entryType": "outcome",
  "date": "2026-10-14",
  "sizingId": 3,
  "sizingName": "ABC Sizing",
  "reference": "Set #S-12 / Bill #B-7",
  "yarnOutcomeId": 18,
  "sizingOutcomeId": 45,
  "bagsIn": null, "conesIn": null, "weightKgIn": null, "weightLbIn": null,
  "bagsOut": "2.500000", "conesOut": "125.000000", "weightKgOut": "98.123456",
  "setLengthMeter": "5400.250000", "shortage": "1.125000",
  "ratePerKg": "12.345678", "sizingCharge": "1211.345679",
  "balanceBags": "7.500000", "balanceCones": "375.000000", "balanceWeightKg": "301.876544",
  "chargesPayable": "1211.345679",
  "remarks": ""
}
```
All decimals are `Decimal`-accumulated and serialized as strings, so the frontend never receives IEEE floats.

### 4.4 Running-balance and pagination strategy
- Compute the full filtered, ordered list, then slice it for the page. The slice keeps the running balance carried from earlier rows, so page 2 starts from the right opening balance.
- Add `openingBalance` to the response meta when `date_from` is set. It is the sum of everything before `date_from`.
- Use `select_related` and `only()` to avoid N+1 queries.
- Expected data volume is small, so no raw SQL or window functions are needed. This can be revisited if the ledger grows very large.

### 4.5 Precision rules
- `Decimal` throughout. No `float()`, `round()` or `quantize()`.
- Balances are carried unrounded between rows, and DRF only formats at the output boundary with `decimal_places=6`, which matches the DB column precision.
- No `.0f`-style CSV formatting. Values are written as `str(Decimal)`.

---

## 5. Frontend Plan

> The frontend lives in `e:\loom\harmony-factory-suite` (React + Vite, `decimal.js` already installed). I will locate the exact sizing page and tab container when I start implementing.

### 5.1 UI
- New **"Sizing Ledger"** tab next to the existing sizing tabs.
- **Filter bar:** sizing party dropdown (from `/sizings/choices/`), date range, type toggle (All / Income / Outcome), search box, Export CSV button.
- **Summary cards:** Total Income (bags / cones / kg), Total Outcome, Current Balance, Sizing Charges Payable.
- **Ledger table** with columns: Date, Type badge (green for Income, amber for Outcome), Sizing, Reference (Set / Bill), In (bags, cones, kg), Out (bags, cones, kg), Set Length, Shortage, Rate/kg, Charge, then running Balance columns.
- Row click opens the existing Sizing Outcome detail or beams view.
- Server-side pagination, loading and empty states, and a sticky header.

### 5.2 Frontend precision rules
- Display raw API strings via `formatFullPrecision` from `src/utils/decimal.js`. No `toFixed()` and no `Number()` conversion.
- Any client-side totals use `decAdd` / `decSub` from `src/utils/decimal.js`.
- Table cells never feed formatted text into later calculations.

### 5.3 Files to add or change (frontend)
- New: `SizingLedgerTab` component, `sizingLedgerApi` service module, and a small hook for filters and pagination.
- Change: the sizing page container, to register the tab.

---

## 6. Tests (backend)
New file `factory/tests/test_sizing_ledger.py`:
1. Income-only and outcome-only rows appear with the correct sign and columns.
2. A mixed ledger is ordered by date, and the running balance is correct row by row.
3. **Fractional precision:** values like `12.345678 kg` and `0.000001` keep all 6 decimals through chained balances, with no drift.
4. Filters work: by sizing, date range, entry type, and search.
5. `openingBalance` is correct when `date_from` is set, and page 2 balances continue from page 1.
6. **Updates and deletes:** editing or deleting a `YarnOutcome` or `SizingOutcome` is reflected immediately in the ledger.
7. API serialization returns strings, not floats. CSV export values equal the API values.
8. Permission test: users without `sizing.view` get 403.

Frontend verification: `npm run build` must pass. A manual browser check will cover filters, pagination and the exported CSV.

---

## 7. Documentation
- `md_files/SIZING_LEDGER_API_SPEC.md` – endpoints, params, row schema, balance formulas, and the frontend integration guide.

---

## 8. Rollout Steps
1. Confirm the ledger definition and open questions (Section 9).
2. Backend: `ledger.py` → serializer → viewset → URL.
3. Backend tests → run `python manage.py test factory.tests.test_sizing_ledger`.
4. Write the API spec md.
5. Frontend: API service → tab component → page registration.
6. Frontend build, then a browser walkthrough.

---

## 9. Open Questions (need your answer before coding)

1. **Income / Outcome meaning:** Is the plan in Section 2 correct? That is, Income = yarn sent to sizing, and Outcome = sets returned and yarn consumed. Or do you mean the money side, where the ledger shows only the sizing charges owed and paid?
2. **Yarn consumed (kg):** `SizingOutcome` stores lagat in bags and cones, and it stores `net_weight_kg`. The net weight is the weight of the sized set, not necessarily the yarn consumed. Should the kg balance be computed from lagat, or from `net_weight_kg`?
3. **Yarn value on income rows:** `YarnOutcome.total_price` is `0` for Sizing outcomes, and the stock price changes over time. Should the ledger show a yarn value for income rows (`outcome_weight_lb × stock.price` at today's price), or skip the value column?
4. **Payments:** Is there a sizing payment or voucher model? None was found. If you want paid / unpaid tracking against the charges, that needs a separate feature.
5. **One tab for all parties, or per party?** The plan supports both: an "All sizings" view plus a party filter. Is that fine?
6. **CSV export:** Should it be included in this version?
