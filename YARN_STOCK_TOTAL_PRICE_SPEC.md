# Yarn Stock `total_price` Field Specification

> **Module:** Factory – Shared Yarn Stock (`factory.yarn.yarn_stock`)  
> **Target Model:** `YarnStock(models.Model)`  
> **New Field:** `total_price` (`models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0.000000"))`)  
> **Migration:** `factory/migrations/0028_yarnstock_total_price.py`  
> **Version:** 1.0.0  

---

## 1. Overview & Purpose

In yarn inventory management, each distinct yarn quality pool is uniquely identified by:
- `yarn_name`
- `yarn_type`
- `yarn_count`
- `production_type` (e.g., Warp, Weft)

Previously, `YarnStock` only stored:
- `price`: The **weighted average purchase rate per box/bag** across contributing intakes (`total_intake_rate / total_intake_bags`).

This update introduces the `total_price` field directly on the `YarnStock` model:
- **Exact Total Valuation:** Stores the **cumulative total purchase value** of all yarn intakes belonging to that specific yarn quality pool.
- **High Precision:** Preserves up to **6 decimal places** after the decimal point (`decimal_places=6`, `max_digits=18`).
- **Separation of Concepts:** Clearly distinguishes between average unit rate (`price`) and aggregate inventory valuation (`total_price`).

---

## 2. Field Comparison on `YarnStock`

| Field Name | JSON API Key | Type | Decimals | Purpose | Formula / Derivation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `price` | `price` | `DecimalField` | 6 | Weighted average intake rate per box/bag | `Sum(total_rate) / Sum(bags)` |
| `total_price` | `totalPrice` | `DecimalField` | 6 | **Total intake purchase value of this yarn quality** | `Sum(YarnIntake.total_rate)` |
| `price_per_kg` | `pricePerKg` | Property (`Decimal`) | 6 | Weighted average purchase rate per kilogram | `Sum(total_rate) / Sum(net_weight_kg)` |

---

## 3. Implementation Details

### 3.1 Model Definition (`factory/yarn/yarn_stock/models.py`)

```python
class YarnStock(models.Model):
    ...
    # ── Current Available Balances ─────────────────────────────────────────
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

### 3.2 Inventory Calculation Service (`factory/yarn/yarn_stock/services.py`)

The authoritative stock ledger recalculation service populates `total_price` directly from the sum of contributing intake rates (`total_rate`).

```python
def calculate_stock_aggregates(stock):
    intake_agg = stock.intakes.aggregate(
        total_bags=Sum("bags"),
        total_cones=Sum("total_cones"),
        total_weight_kg=Sum("net_weight_kg"),
        total_weight_lb=Sum("net_weight_lb"),
        total_rate=Sum("total_rate"),
    )
    ...
    total_intake_rate = intake_agg["total_rate"] or Decimal("0.000000")
    ...
    return {
        ...
        "price": weighted_price,
        "total_price": total_intake_rate,
    }


def recalculate_yarn_stock(stock):
    aggs = calculate_stock_aggregates(stock)

    stock.total_boxes = aggs["available_boxes"]
    stock.cones = aggs["available_cones"]
    stock.total_weight_kg = aggs["available_weight_kg"]
    stock.total_weight_lb = aggs["available_weight_lb"]
    stock.price = aggs["price"]
    stock.total_price = aggs["total_price"]

    stock.save(update_fields=[
        "total_boxes",
        "cones",
        "total_weight_kg",
        "total_weight_lb",
        "price",
        "total_price",
        "updated_at",
    ])
    return stock
```

---

### 3.3 Serializers (`factory/yarn/yarn_stock/serializers.py`)

`totalPrice` is exposed as a read-only decimal field with 6 decimal places across all stock serializers:

1. **`YarnStockMinSerializer`**: Compact representation for dropdowns and nested views.
2. **`YarnStockListSerializer`**: Standard representation for inventory tables and lists.
3. **`YarnStockDetailSerializer`**: Full detail view.

```python
class YarnStockListSerializer(serializers.ModelSerializer):
    ...
    price = serializers.DecimalField(max_digits=15, decimal_places=6, read_only=True)
    totalPrice = serializers.DecimalField(source="total_price", max_digits=18, decimal_places=6, read_only=True)
    pricePerKg = serializers.DecimalField(source="price_per_kg", max_digits=15, decimal_places=6, read_only=True)
    ...
    class Meta:
        model = YarnStock
        fields = [
            "id",
            "yarnName",
            "yarnType",
            "yarnCount",
            "yarnNameId",
            "yarnTypeId",
            "yarnCountId",
            "yarnNameDetail",
            "yarnTypeDetail",
            "yarnCountDetail",
            "productionType",
            "price",
            "totalPrice",
            "pricePerKg",
            "totalBoxes",
            "cones",
            "totalWeightKg",
            "totalWeightLb",
            "totalReceivedBoxes",
            "totalReceivedCones",
            "totalReceivedWeightKg",
            "totalReceivedWeightLb",
            "totalDispatchedBoxes",
            "totalDispatchedWeightKg",
            "totalDispatchedWeightLb",
            "intakesCount",
            "outcomesCount",
            "createdAt",
            "updatedAt",
            "createdBy",
            "updatedBy",
        ]
```

---

### 3.4 ViewSet & Sorting (`factory/yarn/yarn_stock/views.py`)

Added `total_price` to `ordering_fields` in `YarnStockViewSet`:
```python
ordering_fields = [
    "yarn_name__name",
    "yarn_type__name",
    "yarn_count__name",
    "production_type",
    "total_boxes",
    "cones",
    "total_weight_kg",
    "total_weight_lb",
    "price",
    "total_price",
    "created_at",
    "updated_at",
]
```

Sorting can be requested via API:
- Ascending: `GET /yarn-stocks/?ordering=total_price`
- Descending: `GET /yarn-stocks/?ordering=-total_price`

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
      "yarnName": "Cotton Carded",
      "yarnType": "100% Cotton",
      "yarnCount": "30/1",
      "yarnNameId": 1,
      "yarnTypeId": 1,
      "yarnCountId": 1,
      "yarnNameDetail": { "id": 1, "name": "Cotton Carded" },
      "yarnTypeDetail": { "id": 1, "name": "100% Cotton" },
      "yarnCountDetail": { "id": 1, "name": "30/1" },
      "productionType": "Warp",
      "price": "14250.000000",
      "totalPrice": "1425000.000000",
      "pricePerKg": "314.159265",
      "totalBoxes": 100,
      "cones": 2400,
      "totalWeightKg": "4535.923700",
      "totalWeightLb": "10000.000000",
      "totalReceivedBoxes": 100,
      "totalReceivedCones": 2400,
      "totalReceivedWeightKg": "4535.923700",
      "totalReceivedWeightLb": "10000.000000",
      "totalDispatchedBoxes": 0,
      "totalDispatchedWeightKg": "0.000000",
      "totalDispatchedWeightLb": "0.000000",
      "intakesCount": 1,
      "outcomesCount": 0,
      "createdAt": "2026-10-12T10:00:00Z",
      "updatedAt": "2026-10-13T05:22:00Z",
      "createdBy": { "id": 1, "username": "admin" },
      "updatedBy": { "id": 1, "username": "admin" }
    }
  ]
}
```

---

## 5. Database Migration & Historical Data Reconcile

1. **Migration File:** `factory/migrations/0028_yarnstock_total_price.py`
2. **Migration Command Executed:** `python manage.py migrate` (Applied successfully).
3. **Data Reconciliation Executed:**
   ```bash
   python manage.py shell -c "from factory.yarn.yarn_stock.services import reconcile_all_stocks; reconcile_all_stocks()"
   ```
   All existing `YarnStock` records were updated with their respective ledger sum of contributing intake prices.
