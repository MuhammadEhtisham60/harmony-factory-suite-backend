# Yarn Intake `set_no` Auto-Generation Specification

> **Module:** Factory – Yarn Intake (`factory.yarn.yarn_intake`)  
> **Target Model:** `YarnIntake(models.Model)`  
> **Target Field:** `set_no` (`models.CharField(max_length=100, blank=True, default="")`)  
> **Auto-Generation Format:** `BATCH-01`, `BATCH-02`, `BATCH-03`, ...  
> **Migration:** `factory/migrations/0025_alter_yarnintake_set_no.py`  
> **Version:** 1.0.0  

---

## 1. Overview & Purpose

In yarn warehouse operations, each yarn arrival received from a supplier is categorized into sequential lots/batches. Previously, `set_no` in `YarnIntake` was a required manual entry. 

With this update:
1. **Auto-Generation:** When creating a `YarnIntake` without providing `setNo` (or when passing an empty string), the backend automatically assigns sequential batch numbers in the format:
   $$\text{BATCH-01}, \text{BATCH-02}, \text{BATCH-03}, \dots, \text{BATCH-09}, \text{BATCH-10}, \dots$$
2. **Optional Override:** Users can still manually specify a custom batch number (e.g., `LOT-SPECIAL-99`, `CUSTOM-SET-01`). If a non-empty string is provided, it is preserved without modification.
3. **Smart Sequence Detection:** The auto-generator dynamically scans existing `BATCH-` records, finds the highest numeric suffix, increments it by 1, and zero-pads to at least 2 digits.
4. **Collision Prevention:** Includes collision-checking loop to prevent primary key or duplicate index collisions.

---

## 2. Implementation Details

### 2.1 Model Definition (`factory/yarn/yarn_intake/models.py`)

#### Field Definition:
```python
set_no = models.CharField(
    max_length=100,
    blank=True,
    default="",
    help_text="Batch / Set number. Auto-generated like BATCH-01 if left blank."
)
```

#### Auto-Generation Classmethod:
```python
@classmethod
def generate_next_batch_no(cls):
    """
    Auto-generates sequential batch identifiers like BATCH-01, BATCH-02, ...
    Finds the highest existing numeric suffix matching BATCH-<number>
    and returns the next formatted number (with at least 2 digits).
    """
    import re
    batch_intakes = cls.objects.filter(set_no__istartswith="BATCH-").values_list("set_no", flat=True)
    max_num = 0
    for val in batch_intakes:
        match = re.match(r"^BATCH-(\d+)$", val, re.IGNORECASE)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_num = max_num + 1
    candidate = f"BATCH-{next_num:02d}"
    while cls.objects.filter(set_no__iexact=candidate).exists():
        next_num += 1
        candidate = f"BATCH-{next_num:02d}"
    return candidate
```

#### Model `save()` Integration:
```python
def save(self, *args, **kwargs):
    if not self.set_no or not str(self.set_no).strip():
        self.set_no = self.generate_next_batch_no()
    self.calculate_intake_fields()
    if not self.pk and not self.remaining_bags and self.bags and not self.outcome_bags:
        self.init_remaining_stock()
    if not self.stock_id:
        from factory.yarn.yarn_stock.services import get_or_create_yarn_stock
        self.stock = get_or_create_yarn_stock(
            yarn_name=self.yarn_name,
            yarn_type=self.yarn_type,
            yarn_count=self.yarn_count,
            production_type=self.production_type,
            user=self.created_by,
        )
    super().save(*args, **kwargs)
```

---

### 2.2 Database Migration (`factory/migrations/0025_alter_yarnintake_set_no.py`)

* **Operation:** `migrations.AlterField(model_name='yarnintake', name='set_no', field=models.CharField(blank=True, default='', max_length=100, help_text='...'))`
* **Status:** Applied successfully to the PostgreSQL database.

---

### 2.3 Serializer Updates (`factory/yarn/yarn_intake/serializers.py`)

In `YarnIntakeDetailSerializer`:
* `setNo` field marked `required=False, allow_blank=True, default=""`.
* Added `to_internal_value()` hook for dual-case tolerance (accepts either `setNo` or `set_no`).

```python
setNo = serializers.CharField(
    source="set_no", required=False, allow_blank=True, default=""
)

def to_internal_value(self, data):
    data = data.copy() if hasattr(data, "copy") else dict(data)
    if "set_no" in data and "setNo" not in data:
        data["setNo"] = data["set_no"]
    return super().to_internal_value(data)
```

---

### 2.4 Filter Updates (`factory/yarn/yarn_intake/filters.py`)

Added direct `set_no` filtering in `YarnIntakeFilter`:
```python
set_no = django_filters.CharFilter(field_name="set_no", lookup_expr="icontains")
```
Allows query params like:
* `GET /api/v1/yarn-intakes/?set_no=BATCH-01`
* `GET /api/v1/yarn-intakes/?set_no=BATCH`

---

## 3. API Usage Guide for Frontend

### 3.1 Creating a Yarn Intake Without `setNo` (Auto-Generated)

#### Endpoint:
```http
POST /api/v1/yarn-intakes/
Content-Type: application/json
Authorization: Bearer <token>
```

#### Request Payload:
```json
{
  "yarnName": "Cotton Warp 20/1",
  "yarnType": "Warp",
  "yarnCount": "20/1",
  "supplier": 1,
  "intakeDate": "2026-10-13",
  "bags": 50,
  "conesPerBag": 24,
  "weightPerBagKg": "45.360",
  "ratePerLb": "165.0000"
}
```
*(Notice `setNo` is completely omitted)*

#### Response (`201 Created`):
```json
{
  "success": true,
  "message": "Yarn intake created successfully.",
  "data": {
    "id": 15,
    "yarnName": "Cotton Warp 20/1",
    "yarnType": "Warp",
    "yarnCount": "20/1",
    "setNo": "BATCH-01",
    "intakeDate": "2026-10-13",
    "bags": 50,
    "conesPerBag": 24,
    "totalCones": 1200,
    "weightPerBagKg": "45.360",
    "netWeightKg": "2268.000",
    "netWeightLb": "5000.084",
    "ratePerLb": "165.0000",
    "totalRate": "825013.860000",
    "remainingBags": 50,
    "remainingWeightKg": "2268.000",
    "remainingWeightLb": "5000.084",
    "outcomes": [],
    "createdAt": "2026-10-13T10:15:00Z",
    "updatedAt": "2026-10-13T10:15:00Z"
  }
}
```

---

### 3.2 Creating a Yarn Intake With a Custom `setNo` (User Provided)

#### Request Payload:
```json
{
  "yarnName": "Cotton Warp 20/1",
  "yarnType": "Warp",
  "yarnCount": "20/1",
  "setNo": "LOT-IMPORT-2026",
  "supplier": 1,
  "intakeDate": "2026-10-13",
  "bags": 20,
  "conesPerBag": 24,
  "weightPerBagKg": "45.360",
  "ratePerLb": "165.0000"
}
```

#### Response (`201 Created`):
```json
{
  "success": true,
  "message": "Yarn intake created successfully.",
  "data": {
    "id": 16,
    "setNo": "LOT-IMPORT-2026"
  }
}
```

---

## 4. Automated Test Verification

Unit tests located in `factory/tests/test_yarn_intake_set_no.py` verify:
1. **`test_model_auto_generate_first_batch`**:
   * First intake generates `BATCH-01`.
   * Second intake generates `BATCH-02`.
   * Explicit empty string generates `BATCH-03`.
2. **`test_manual_set_no_preserved`**:
   * Custom manual `set_no` (e.g. `CUSTOM-LOT-88`) is preserved.
   * If manual `BATCH-05` is created, next auto-generated intake increments to `BATCH-06`.
3. **`test_api_create_without_set_no`**:
   * `POST /api/v1/yarn-intakes/` without `setNo` succeeds with HTTP 201 and auto-generates `BATCH-XX`.
   * Subsequent API call increments sequence.
4. **`test_api_create_with_custom_set_no`**:
   * `POST /api/v1/yarn-intakes/` with custom `setNo` preserves the value.
5. **`test_filter_by_set_no`**:
   * `GET /api/v1/yarn-intakes/?set_no=BATCH-01` correctly filters records.

### Execution Command & Results:
```bash
python manage.py test factory.tests.test_yarn_intake_set_no --keepdb
```
**Output:** `Ran 5 tests in 4.692s - OK`
