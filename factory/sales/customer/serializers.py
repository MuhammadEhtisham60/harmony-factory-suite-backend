"""
Serializers for the Customer module (including nested Bank Accounts).
"""

from rest_framework import serializers
from .models import Customer, CustomerBankAccount


# ============================================================================
# Bank Account Serializer
# ============================================================================

class CustomerBankAccountSerializer(serializers.ModelSerializer):
    """
    Nested writable serializer for CustomerBankAccount.

    Write strategy:
        - No id  → new account created.
        - id present, matches existing → account updated.
        - Existing accounts not in the payload → deleted (on update).
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
        model = CustomerBankAccount
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
        extra_kwargs = {
            # id must be writable so the client can identify which rows to update
            "id": {"read_only": False, "required": False},
        }


# ============================================================================
# Customer List Serializer  (lightweight – no nested banks)
# ============================================================================

class CustomerListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list / table views.
    Includes a bankAccountCount summary instead of the full account list.
    """
    customerCode = serializers.CharField(source="customer_code", read_only=True)
    customerName = serializers.CharField(source="customer_name")
    companyName = serializers.CharField(
        source="company_name", required=False, allow_blank=True
    )
    contactPerson = serializers.CharField(source="contact_person")
    customerType = serializers.ChoiceField(
        source="customer_type",
        choices=Customer.CustomerType.choices,
        required=False
    )
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()
    bankAccountCount = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "customerCode",
            "customerName",
            "companyName",
            "phone",
            "email",
            "contactPerson",
            "customerType",
            "status",
            "registrationNumber",
            "bankAccountCount",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]

    def get_bankAccountCount(self, obj):
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
# Customer Detail Serializer  (full CRUD + nested bank accounts)
# ============================================================================

class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Full serializer for create / retrieve / update operations.

    Bank accounts are a writable nested list under `bankAccounts`.

    Update strategy (replace-and-reconcile):
        1. Existing accounts missing from payload          → deleted.
        2. Payload accounts with a matching `id`           → updated.
        3. Payload accounts without an `id` (or id=null)  → created.

    On PATCH: if `bankAccounts` key is omitted entirely, banks are untouched.
    """
    customerCode = serializers.CharField(source="customer_code", read_only=True)
    customerName = serializers.CharField(source="customer_name")
    companyName = serializers.CharField(
        source="company_name", required=False, allow_blank=True, default=""
    )
    address = serializers.CharField(required=False, allow_blank=True, default="")
    contactPerson = serializers.CharField(source="contact_person")
    customerType = serializers.ChoiceField(
        source="customer_type",
        choices=Customer.CustomerType.choices,
        required=False
    )
    registrationNumber = serializers.CharField(
        source="registration_number", required=False, allow_blank=True, default=""
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)
    createdBy = serializers.SerializerMethodField()
    updatedBy = serializers.SerializerMethodField()

    # Nested writable bank accounts
    bankAccounts = CustomerBankAccountSerializer(
        source="bank_accounts",
        many=True,
        required=False,
        default=list,
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "customerCode",
            "customerName",
            "companyName",
            "address",
            "phone",
            "email",
            "contactPerson",
            "customerType",
            "status",
            "registrationNumber",
            "bankAccounts",
            "createdBy",
            "updatedBy",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = [
            "id", "customerCode", "createdAt", "updatedAt", "createdBy", "updatedBy"
        ]

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

    def validate_customerName(self, value):  # noqa: N802
        customer_id = self.instance.id if self.instance else None
        if (
            Customer.objects
            .filter(customer_name__iexact=value)
            .exclude(id=customer_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A customer with this name already exists."
            )
        return value

    def validate_email(self, value):
        if not value:
            return value
        customer_id = self.instance.id if self.instance else None
        if (
            Customer.objects
            .filter(email__iexact=value)
            .exclude(id=customer_id)
            .exists()
        ):
            raise serializers.ValidationError(
                "A customer with this email already exists."
            )
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
    def _sync_bank_accounts(customer, bank_accounts_data):
        """
        Reconcile the incoming bank account list against existing accounts:
          • Delete accounts no longer in the payload.
          • Update accounts whose id is in the payload.
          • Create accounts that have no id.
        """
        incoming_ids = {item["id"] for item in bank_accounts_data if item.get("id")}

        # 1. Delete removed accounts
        customer.bank_accounts.exclude(pk__in=incoming_ids).delete()

        # 2. Update / create
        for item in bank_accounts_data:
            item_id = item.pop("id", None)
            if item_id:
                CustomerBankAccount.objects.filter(
                    pk=item_id, customer=customer
                ).update(**item)
            else:
                CustomerBankAccount.objects.create(customer=customer, **item)

    # ------------------------------------------------------------------ #
    # Create / Update
    # ------------------------------------------------------------------ #

    def create(self, validated_data):
        bank_accounts_data = validated_data.pop("bank_accounts", [])

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
            validated_data["updated_by"] = request.user

        customer = Customer.objects.create(**validated_data)

        for account_data in bank_accounts_data:
            account_data.pop("id", None)  # strip any id on create
            CustomerBankAccount.objects.create(customer=customer, **account_data)

        return customer

    def update(self, instance, validated_data):
        bank_accounts_data = validated_data.pop("bank_accounts", None)

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["updated_by"] = request.user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Sync only when key was explicitly provided in the request
        if bank_accounts_data is not None:
            self._sync_bank_accounts(instance, bank_accounts_data)

        return instance
