"""
Serializers for the Supplier module (including nested Bank Accounts).
"""

from rest_framework import serializers
from .models import Supplier, SupplierBankAccount


# ============================================================================
# Bank Account Serializer
# ============================================================================

class SupplierBankAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for SupplierBankAccount – used as a nested writable field.

    On write (create / update) the caller may include an optional `id` field:
        - No id  → new bank account will be created.
        - id present, matches existing account → account is updated.
        - Existing accounts whose id is NOT present in the list → deleted.
    """
    bankName = serializers.CharField(source="bank_name")
    accountTitle = serializers.CharField(source="account_title")
    accountNumber = serializers.CharField(source="account_number")
    iban = serializers.CharField(required=False, allow_blank=True, default="")
    branchName = serializers.CharField(
        source="branch_name", required=False, allow_blank=True, default=""
    )
    branchCode = serializers.CharField(
        source="branch_code", required=False, allow_blank=True, default=""
    )
    swiftCode = serializers.CharField(
        source="swift_code", required=False, allow_blank=True, default=""
    )
    isPrimary = serializers.BooleanField(source="is_primary", required=False, default=False)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = SupplierBankAccount
        fields = [
            "id",
            "bankName",
            "accountTitle",
            "accountNumber",
            "iban",
            "branchName",
            "branchCode",
            "swiftCode",
            "isPrimary",
            "createdAt",
            "updatedAt",
        ]
        # id is read-only by default in ModelSerializer, but we need it
        # writable so the client can identify which accounts to update.
        extra_kwargs = {
            "id": {"read_only": False, "required": False},
        }


# ============================================================================
# Supplier List Serializer  (lightweight – no nested banks)
# ============================================================================

class SupplierListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing suppliers (table views).
    Includes a summary count of bank accounts but not the full detail.
    """
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()
    supplierCode = serializers.CharField(source="supplier_code", read_only=True)
    supplierName = serializers.CharField(source="supplier_name")
    companyName = serializers.CharField(source="company_name", required=False, allow_blank=True)
    contactPerson = serializers.CharField(source="contact_person")
    supplierType = serializers.ChoiceField(
        source="supplier_type",
        choices=Supplier.SupplierType.choices,
        required=False
    )
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    bankAccountCount = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            "id",
            "supplierCode",
            "supplierName",
            "companyName",
            "phone",
            "email",
            "contactPerson",
            "supplierType",
            "status",
            "registrationNumber",
            "bankAccountCount",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_bankAccountCount(self, obj):
        # use prefetched cache when available to avoid extra queries
        if hasattr(obj, "_prefetched_objects_cache") and "bank_accounts" in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache["bank_accounts"])
        return obj.bank_accounts.count()

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None


# ============================================================================
# Supplier Detail Serializer  (full CRUD, with nested bank accounts)
# ============================================================================

class SupplierDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer for create / retrieve / update operations.

    Bank accounts are handled as a **writable nested list** under the key
    `bankAccounts`.  The update strategy is *replace-and-reconcile*:

        1. Accounts that exist in DB but are missing from the payload → deleted.
        2. Accounts in the payload with an existing `id`              → updated.
        3. Accounts in the payload without an `id` (or id=null)      → created.

    On create, any accounts supplied in `bankAccounts` are bulk-created after
    the supplier record is saved.
    """
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()
    supplierCode = serializers.CharField(source="supplier_code", read_only=True)
    supplierName = serializers.CharField(source="supplier_name")
    companyName = serializers.CharField(
        source="company_name", required=False, allow_blank=True, default=""
    )
    address = serializers.CharField(required=False, allow_blank=True, default="")
    contactPerson = serializers.CharField(source="contact_person")
    supplierType = serializers.ChoiceField(
        source="supplier_type",
        choices=Supplier.SupplierType.choices,
        required=False
    )
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True, default=""
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    # Nested writable bank accounts
    bankAccounts = SupplierBankAccountSerializer(
        source="bank_accounts",
        many=True,
        required=False,
        default=list,
    )

    class Meta:
        model = Supplier
        fields = [
            "id",
            "supplierCode",
            "supplierName",
            "companyName",
            "address",
            "phone",
            "email",
            "contactPerson",
            "supplierType",
            "status",
            "registrationNumber",
            "bankAccounts",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id", "supplierCode", "createdAt", "updatedAt", "createdBy", "updatedBy"
        ]

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    def get_createdBy(self, obj):
        if obj.created_by:
            return {
                "id": obj.created_by.id,
                "username": obj.created_by.username,
                "fullName": getattr(obj.created_by, "full_name", obj.created_by.username),
            }
        return None

    def get_updatedBy(self, obj):
        if obj.updated_by:
            return {
                "id": obj.updated_by.id,
                "username": obj.updated_by.username,
                "fullName": getattr(obj.updated_by, "full_name", obj.updated_by.username),
            }
        return None

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate_supplierName(self, value):  # noqa: N802
        supplier_id = self.instance.id if self.instance else None
        if Supplier.objects.filter(supplier_name__iexact=value).exclude(id=supplier_id).exists():
            raise serializers.ValidationError("A supplier with this name already exists.")
        return value

    def validate_email(self, value):
        if not value:
            return value
        supplier_id = self.instance.id if self.instance else None
        if Supplier.objects.filter(email__iexact=value).exclude(id=supplier_id).exists():
            raise serializers.ValidationError("A supplier with this email already exists.")
        return value

    def validate(self, attrs):
        bank_accounts = attrs.get("bank_accounts", [])
        primary_count = sum(1 for b in bank_accounts if b.get("is_primary", False))
        if primary_count > 1:
            raise serializers.ValidationError(
                {"bankAccounts": "Only one bank account can be marked as primary."}
            )
        return attrs

    # ------------------------------------------------------------------ #
    # Internal: sync bank accounts
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sync_bank_accounts(supplier, bank_accounts_data):
        """
        Reconcile the incoming bank account list against the supplier's
        existing accounts:
          • Delete accounts no longer in the payload.
          • Update accounts whose id is in the payload.
          • Create accounts that have no id in the payload.
        """
        incoming_ids = set()
        for item in bank_accounts_data:
            item_id = item.get("id")
            if item_id:
                incoming_ids.add(item_id)

        # 1. Delete removed accounts
        supplier.bank_accounts.exclude(pk__in=incoming_ids).delete()

        # 2. Update / create
        for item in bank_accounts_data:
            item_id = item.pop("id", None)
            if item_id:
                SupplierBankAccount.objects.filter(
                    pk=item_id, supplier=supplier
                ).update(**item)
            else:
                SupplierBankAccount.objects.create(supplier=supplier, **item)

    # ------------------------------------------------------------------ #
    # Create / Update
    # ------------------------------------------------------------------ #

    def create(self, validated_data):
        bank_accounts_data = validated_data.pop("bank_accounts", [])

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        supplier = Supplier.objects.create(**validated_data)

        # Create all supplied bank accounts
        for account_data in bank_accounts_data:
            account_data.pop("id", None)  # strip id on create
            SupplierBankAccount.objects.create(supplier=supplier, **account_data)

        return supplier

    def update(self, instance, validated_data):
        bank_accounts_data = validated_data.pop("bank_accounts", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user

        # Update supplier fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Sync bank accounts only when the key was explicitly provided
        if bank_accounts_data is not None:
            self._sync_bank_accounts(instance, bank_accounts_data)

        return instance
