# Yarn Stock Remaining Balances Field Specification

> **Module:** Factory – Shared Yarn Stock (`factory.yarn.yarn_stock`)  
> **Target Model:** `YarnStock(models.Model)`  
> **New Fields:** `remaining_bags`, `remaining_cones`, `remaining_weight_kg`, `remaining_weight_lb`, `remaining_total_price`  
> **Migration:** `factory/migrations/0029_yarnstock_remaining_bags_yarnstock_remaining_cones_and_more.py`  
> **Version:** 1.0.0  

---

## 1. Overview & Purpose

In yarn warehouse operations, shared inventory pools (`YarnStock`) aggregate deliveries from multiple `YarnIntake` batches and deduct dispatches from `YarnOutcome` records.

To mirror the clear ledger design of `YarnIntake` (`remaining_bags`, `remaining_weight_kg`, `remaining_weight_lb`), the `YarnStock` model now features explicit remaining balance fields with full 6-decimal-place precision:

1. **`remaining_bags`**: Exact boxes / bags remaining available in warehouse.
2. **`remaining_cones`**: Exact cones remaining available in warehouse.
3. **`remaining_weight_kg`**: Exact weight in kilograms remaining in stock (up to 6 decimal places).
4. **`remaining_weight_lb`**: Exact weight in pounds remaining in stock (up to 6 decimal places).
5. **`remaining_total_price`**: Exact inventory valuation of remaining stock (remaining bags $\times$ weighted unit rate, up to 6 decimal places).

> **Backward Compatibility:** Previous field names (`total_boxes`, `cones`, `total_weight_kg`, `total_weight_lb`) are preserved and synchronized automatically so existing frontend components continue to function seamlessly.

---

## 2. Complete Field Matrix on `YarnStock`

| Conceptual Category | Python Model Field | JSON API Key | Data Type | Decimals | Description / Derivation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pricing** | `price` | `price` | `DecimalField` | 6 | Weighted average intake rate per bag |
| **Pricing** | `total_price` | `totalPrice` | `DecimalField` | 6 | Total cumulative purchase rate across all intakes ($\sum \text{intake.total\_rate}$) |
| **Pricing** | `price_per_kg` | `pricePerKg` | Property (`Decimal`) | 6 | Weighted average purchase rate per kilogram |
| **Remaining Stock** | `remaining_bags` | `remainingBags` | `IntegerField` | — | Current remaining bags available ($\text{Intake bags} - \text{Outcome bags}$) |
| **Remaining Stock** | `remaining_cones` | `remainingCones` | `IntegerField` | — | Current remaining cones available ($\text{Intake cones} - \text{Outcome cones}$) |
| **Remaining Stock** | `remaining_weight_kg` | `remainingWeightKg` | `DecimalField` | 6 | Current remaining weight in KG ($\text{Intake kg} - \text{Outcome kg}$) |
| **Remaining Stock** | `remaining_weight_lb` | `remainingWeightLb` | `DecimalField` | 6 | Current remaining weight in LB ($\text{remaining\_weight\_kg} \times 2.20462262$) |
| **Remaining Stock** | `remaining_total_price` | `remainingTotalPrice` | `DecimalField` | 6 | Current available inventory valuation ($\text{remaining\_bags} \times \text{price}$) |
| **Legacy Aliases** | `total_boxes` | `totalBoxes` | `IntegerField` | — | Synchronized with `remaining_bags` |
| **Legacy Aliases** | `cones` | `cones` | `IntegerField` | — | Synchronized with `remaining_cones` |
| **Legacy Aliases** | `total_weight_kg` | `totalWeightKg` | `DecimalField` | 6 | Synchronized with `remaining_weight_kg` |
| **Legacy Aliases** | `total_weight_lb` | `totalWeightLb` | `DecimalField` | 6 | Synchronized with `remaining_weight_lb` |
| **Received Totals** | `total_received_boxes` | `totalReceivedBoxes` | Property (`int`) | — | Cumulative bags received from all intakes |
| **Received Totals** | `total_received_cones` | `totalReceivedCones` | Property (`int`) | — | Cumulative cones received from all intakes |
| **Received Totals** | `total_received_weight_kg` | `totalReceivedWeightKg` | Property (`Decimal`) | 6 | Cumulative kilograms received from all intakes |
| **Received Totals** | `total_received_weight_lb` | `totalReceivedWeightLb` | Property (`Decimal`) | 6 | Cumulative pounds received from all intakes |
| **Dispatched Totals**| `total_dispatched_boxes` | `totalDispatchedBoxes` | Property (`int`) | — | Cumulative bags dispatched across all outcomes |
| **Dispatched Totals**| `total_dispatched_weight_kg` | `totalDispatchedWeightKg`| Property (`Decimal`) | 6 | Cumulative kilograms dispatched across all outcomes |
| **Dispatched Totals**| `total_dispatched_weight_lb` | `totalDispatchedWeightLb`| Property (`Decimal`) | 6 | Cumulative pounds dispatched across all outcomes |

---

## 3. Implementation Details

### 3.1 Model Definition (`factory/yarn/yarn_stock/models.py`)

```python
class YarnStock(models.Model):
    ...
    # ── Current Available / Remaining Balances ─────────────────────────────
    price = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Weighted average purchase rate per box/bag from contributing intakes."
    )
    total_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Total price of yarn of this quality from contributing intakes."
    )
    remaining_bags = models.IntegerField(
        default=0,
        help_text="Current remaining available boxes / bags in stock."
    )
    remaining_cones = models.IntegerField(
        default=0,
        help_text="Current remaining available cones in stock."
    )
    remaining_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available weight in kilograms."
    )
    remaining_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available weight in pounds."
    )
    remaining_total_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current remaining available inventory total price / valuation."
    )

    # Legacy balance field aliases (maintained for backward compatibility)
    total_boxes = models.IntegerField(
        default=0,
        help_text="Current available boxes / bags remaining in stock."
    )
    cones = models.IntegerField(
        default=0,
        help_text="Current available cones remaining in stock."
    )
    total_weight_kg = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current available weight in kilograms."
    )
    total_weight_lb = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        default=Decimal("0.000000"),
        help_text="Current available weight in pounds."
    )
```

---

### 3.2 Calculation Service (`factory/yarn/yarn_stock/services.py`)

The inventory recalculation logic populates remaining balances directly from the ledger:

```python
def calculate_stock_aggregates(stock):
    ...
    available_boxes = total_intake_bags - total_outcome_bags
    available_cones = total_intake_cones - total_outcome_cones
    available_weight_kg = total_intake_weight_kg - total_outcome_weight_kg
    available_weight_lb = (available_weight_kg * LB_PER_KG).quantize(Decimal("0.000001"))

    if total_intake_bags > 0:
        weighted_price = (total_intake_rate / Decimal(str(total_intake_bags))).quantize(Decimal("0.000001"))
    else:
        weighted_price = Decimal("0.000000")

    if available_boxes > 0:
        remaining_total_price = (Decimal(str(available_boxes)) * weighted_price).quantize(Decimal("0.000001"))
    else:
        remaining_total_price = Decimal("0.000000")

    return {
        ...
        "remaining_bags": available_boxes,
        "remaining_cones": available_cones,
        "remaining_weight_kg": available_weight_kg,
        "remaining_weight_lb": available_weight_lb,
        "remaining_total_price": remaining_total_price,
    }


def recalculate_yarn_stock(stock):
    aggs = calculate_stock_aggregates(stock)

    stock.total_boxes = aggs["available_boxes"]
    stock.cones = aggs["available_cones"]
    stock.total_weight_kg = aggs["available_weight_kg"]
    stock.total_weight_lb = aggs["available_weight_lb"]
    stock.price = aggs["price"]
    stock.total_price = aggs["total_price"]

    stock.remaining_bags = aggs["remaining_bags"]
    stock.remaining_cones = aggs["remaining_cones"]
    stock.remaining_weight_kg = aggs["remaining_weight_kg"]
    stock.remaining_weight_lb = aggs["remaining_weight_lb"]
    stock.remaining_total_price = aggs["remaining_total_price"]

    stock.save(update_fields=[
        "total_boxes",
        "cones",
        "total_weight_kg",
        "total_weight_lb",
        "price",
        "total_price",
        "remaining_bags",
        "remaining_cones",
        "remaining_weight_kg",
        "remaining_weight_lb",
        "remaining_total_price",
        "updated_at",
    ])
    return stock
```

---

### 3.3 Serializers (`factory/yarn/yarn_stock/serializers.py`)

Both `YarnStockMinSerializer` and `YarnStockListSerializer` expose the camelCase keys:
- `remainingBags`
- `remainingCones`
- `remainingWeightKg`
- `remainingWeightLb`
- `remainingTotalPrice`

```python
class YarnStockListSerializer(serializers.ModelSerializer):
    ...
    remainingBags = serializers.IntegerField(source="remaining_bags", read_only=True)
    remainingCones = serializers.IntegerField(source="remaining_cones", read_only=True)
    remainingWeightKg = serializers.DecimalField(source="remaining_weight_kg", max_digits=15, decimal_places=6, read_only=True)
    remainingWeightLb = serializers.DecimalField(source="remaining_weight_lb", max_digits=15, decimal_places=6, read_only=True)
    remainingTotalPrice = serializers.DecimalField(source="remaining_total_price", max_digits=18, decimal_places=6, read_only=True)
```

---

## 4. API Response Example

`GET /yarn-stocks/`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "yarnName": "Cotton Ring Spun",
      "yarnType": "100% Cotton",
      "yarnCount": "30/1",
      "yarnNameId": 1,
      "yarnTypeId": 1,
      "yarnCountId": 1,
      "yarnNameDetail": { "id": 1, "name": "Cotton Ring Spun" },
      "yarnTypeDetail": { "id": 1, "name": "100% Cotton" },
      "yarnCountDetail": { "id": 1, "name": "30/1" },
      "productionType": "Warp",

      "price": "14250.000000",
      "totalPrice": "1425000.000000",
      "pricePerKg": "314.159265",

      "remainingBags": 80,
      "remainingCones": 1920,
      "remainingWeightKg": "3628.738960",
      "remainingWeightLb": "8000.000000",
      "remainingTotalPrice": "1140000.000000",

      "totalBoxes": 80,
      "cones": 1920,
      "totalWeightKg": "3628.738960",
      "totalWeightLb": "8000.000000",

      "totalReceivedBoxes": 100,
      "totalReceivedCones": 2400,
      "totalReceivedWeightKg": "4535.923700",
      "totalReceivedWeightLb": "10000.000000",

      "totalDispatchedBoxes": 20,
      "totalDispatchedWeightKg": "907.184740",
      "totalDispatchedWeightLb": "2000.000000",

      "intakesCount": 1,
      "outcomesCount": 1,
      "createdAt": "2026-10-12T10:00:00Z",
      "updatedAt": "2026-10-13T06:10:00Z",
      "createdBy": { "id": 1, "username": "admin" },
      "updatedBy": { "id": 1, "username": "admin" }
    }
  ]
}
```

---

## 5. Filtering and Ordering

### Filters Available (`factory/yarn/yarn_stock/filters.py`)
- `min_remaining_bags`: `GET /yarn-stocks/?min_remaining_bags=10`
- `min_remaining_weight_kg`: `GET /yarn-stocks/?min_remaining_weight_kg=500`
- `in_stock`: `GET /yarn-stocks/?in_stock=true` (filters for `remaining_bags > 0` or `remaining_weight_kg > 0`)

### Sorting Supported (`factory/yarn/yarn_stock/views.py`)
- `GET /yarn-stocks/?ordering=remaining_bags`
- `GET /yarn-stocks/?ordering=-remaining_bags`
- `GET /yarn-stocks/?ordering=-remaining_weight_kg`
- `GET /yarn-stocks/?ordering=-remaining_total_price`
