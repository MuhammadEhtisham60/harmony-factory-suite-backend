"""
Serializers for Authentication, Users, and Roles modules.
"""

from rest_framework import serializers
from django.utils.text import slugify
from django.contrib.auth import authenticate
from .models import User, Role
from .constants import ALL_PERMISSION_CODES


class RoleSerializer(serializers.ModelSerializer):
    userCount = serializers.IntegerField(source='user_count', read_only=True)
    isSystem = serializers.BooleanField(source='is_system', default=False, required=False)
    slug = serializers.SlugField(required=False, allow_blank=True)

    class Meta:
        model = Role
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'userCount',
            'status',
            'isSystem',
            'permissions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        role_id = self.instance.id if self.instance else None
        if Role.objects.filter(name__iexact=value).exclude(id=role_id).exists():
            raise serializers.ValidationError("A role with this name already exists.")
        return value

    def create(self, validated_data):
        name = validated_data.get('name')
        if 'slug' not in validated_data or not validated_data['slug']:
            base_slug = slugify(name).replace('-', '_')
            slug = base_slug
            counter = 1
            while Role.objects.filter(slug=slug).exists():
                slug = f"{base_slug}_{counter}"
                counter += 1
            validated_data['slug'] = slug
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if instance.is_system:
            # Protect system slug and is_system flag
            validated_data.pop('slug', None)
            validated_data.pop('is_system', None)
        return super().update(instance, validated_data)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the current user representation (e.g. login, /me, user profile)
    """
    id = serializers.CharField(source='formatted_id', read_only=True)
    rawId = serializers.CharField(source='id', read_only=True)
    fullName = serializers.CharField(source='full_name')
    firstName = serializers.CharField(source='first_name')
    lastName = serializers.CharField(source='last_name')
    altPhone = serializers.CharField(source='alt_phone', allow_blank=True)
    role = serializers.SerializerMethodField()
    roleId = serializers.SerializerMethodField()
    employeeId = serializers.CharField(source='employee_id', allow_null=True)
    manager = serializers.CharField(source='manager_name', allow_blank=True)
    postalCode = serializers.CharField(source='postal_code', allow_blank=True)
    joiningDate = serializers.DateField(source='joining_date', allow_null=True)
    accountExpiry = serializers.DateField(source='account_expiry', allow_null=True)
    lastLogin = serializers.SerializerMethodField()
    createdDate = serializers.DateField(source='created_date', read_only=True)
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled')
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'rawId',
            'username',
            'fullName',
            'firstName',
            'lastName',
            'email',
            'phone',
            'altPhone',
            'dob',
            'gender',
            'role',
            'roleId',
            'department',
            'designation',
            'employeeId',
            'company',
            'branch',
            'status',
            'joiningDate',
            'manager',
            'shift',
            'address',
            'city',
            'state',
            'country',
            'postalCode',
            'notes',
            'avatar',
            'accountExpiry',
            'lastLogin',
            'createdDate',
            'twoFactorEnabled',
            'permissions',
        ]

    def get_role(self, obj):
        return obj.role.name if obj.role else None

    def get_roleId(self, obj):
        return obj.role.id if obj.role else None

    def get_lastLogin(self, obj):
        if obj.last_login_at:
            return obj.last_login_at.strftime('%d %b %Y, %I:%M %p')
        if obj.last_login:
            return obj.last_login.strftime('%d %b %Y, %I:%M %p')
        return None

    def get_permissions(self, obj):
        return obj.get_permissions()


class UserListSerializer(UserProfileSerializer):
    """Alias for listing users in User Management table"""
    pass


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/onboarding a new user.
    Supports both camelCase and snake_case input fields.
    """
    fullName = serializers.CharField(source='full_name', required=True)
    firstName = serializers.CharField(source='first_name', required=False, allow_blank=True, default='')
    lastName = serializers.CharField(source='last_name', required=False, allow_blank=True, default='')
    altPhone = serializers.CharField(source='alt_phone', required=False, allow_blank=True, default='')
    employeeId = serializers.CharField(source='employee_id', required=False, allow_null=True, allow_blank=True, default=None)
    joiningDate = serializers.DateField(source='joining_date', required=False, allow_null=True, default=None)
    manager = serializers.CharField(source='manager_name', required=False, allow_blank=True, default='')
    postalCode = serializers.CharField(source='postal_code', required=False, allow_blank=True, default='')
    accountExpiry = serializers.DateField(source='account_expiry', required=False, allow_null=True, default=None)
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled', required=False, default=False)
    role = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            'username',
            'fullName',
            'firstName',
            'lastName',
            'email',
            'password',
            'role',
            'department',
            'status',
            'phone',
            'altPhone',
            'dob',
            'gender',
            'designation',
            'employeeId',
            'company',
            'branch',
            'shift',
            'joiningDate',
            'manager',
            'address',
            'city',
            'state',
            'country',
            'postalCode',
            'notes',
            'accountExpiry',
            'twoFactorEnabled',
            'avatar',
        ]

    def to_internal_value(self, data):
        # Support snake_case keys if provided
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        mappings = {
            'full_name': 'fullName',
            'first_name': 'firstName',
            'last_name': 'lastName',
            'alt_phone': 'altPhone',
            'employee_id': 'employeeId',
            'joining_date': 'joiningDate',
            'manager_name': 'manager',
            'postal_code': 'postalCode',
            'account_expiry': 'accountExpiry',
            'two_factor_enabled': 'twoFactorEnabled',
        }
        for snake, camel in mappings.items():
            if snake in data_copy and camel not in data_copy:
                data_copy[camel] = data_copy[snake]
        return super().to_internal_value(data_copy)

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Username must be at least 3 characters long.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already registered.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email address is already in use.")
        return value

    def validate_employeeId(self, value):
        if value:
            if User.objects.filter(employee_id__iexact=value).exists():
                raise serializers.ValidationError("This Employee ID is already registered.")
        return value

    def validate_role(self, value):
        # Resolve role by ID or Name
        role = None
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            role = Role.objects.filter(id=int(value)).first()
        else:
            role = Role.objects.filter(name__iexact=value).first()

        if not role:
            raise serializers.ValidationError(f"Role '{value}' not found.")
        return role

    def create(self, validated_data):
        password = validated_data.pop('password')
        role = validated_data.pop('role')

        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        full_name = validated_data.get('full_name', '')

        if not first_name and full_name:
            parts = full_name.split(' ', 1)
            validated_data['first_name'] = parts[0]
            if len(parts) > 1 and not last_name:
                validated_data['last_name'] = parts[1]

        user = User(**validated_data)
        user.role = role
        user.set_password(password)
        user.is_active = (user.status == 'Active')
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing user profile & work details.
    """
    fullName = serializers.CharField(source='full_name', required=False)
    firstName = serializers.CharField(source='first_name', required=False, allow_blank=True)
    lastName = serializers.CharField(source='last_name', required=False, allow_blank=True)
    altPhone = serializers.CharField(source='alt_phone', required=False, allow_blank=True)
    employeeId = serializers.CharField(source='employee_id', required=False, allow_null=True, allow_blank=True)
    joiningDate = serializers.DateField(source='joining_date', required=False, allow_null=True)
    manager = serializers.CharField(source='manager_name', required=False, allow_blank=True)
    postalCode = serializers.CharField(source='postal_code', required=False, allow_blank=True)
    accountExpiry = serializers.DateField(source='account_expiry', required=False, allow_null=True)
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled', required=False)
    role = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            'username',
            'fullName',
            'firstName',
            'lastName',
            'email',
            'role',
            'department',
            'status',
            'phone',
            'altPhone',
            'dob',
            'gender',
            'designation',
            'employeeId',
            'company',
            'branch',
            'shift',
            'joiningDate',
            'manager',
            'address',
            'city',
            'state',
            'country',
            'postalCode',
            'notes',
            'accountExpiry',
            'twoFactorEnabled',
            'avatar',
        ]

    def to_internal_value(self, data):
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        mappings = {
            'full_name': 'fullName',
            'first_name': 'firstName',
            'last_name': 'lastName',
            'alt_phone': 'altPhone',
            'employee_id': 'employeeId',
            'joining_date': 'joiningDate',
            'manager_name': 'manager',
            'postal_code': 'postalCode',
            'account_expiry': 'accountExpiry',
            'two_factor_enabled': 'twoFactorEnabled',
        }
        for snake, camel in mappings.items():
            if snake in data_copy and camel not in data_copy:
                data_copy[camel] = data_copy[snake]
        return super().to_internal_value(data_copy)

    def validate_username(self, value):
        user_id = self.instance.id if self.instance else None
        if User.objects.filter(username__iexact=value).exclude(id=user_id).exists():
            raise serializers.ValidationError("This username is already registered.")
        return value

    def validate_email(self, value):
        user_id = self.instance.id if self.instance else None
        if User.objects.filter(email__iexact=value).exclude(id=user_id).exists():
            raise serializers.ValidationError("This email address is already in use.")
        return value

    def validate_employeeId(self, value):
        if value:
            user_id = self.instance.id if self.instance else None
            if User.objects.filter(employee_id__iexact=value).exclude(id=user_id).exists():
                raise serializers.ValidationError("This Employee ID is already registered.")
        return value

    def validate_role(self, value):
        if value is None:
            return None
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
            role = Role.objects.filter(id=int(value)).first()
        else:
            role = Role.objects.filter(name__iexact=value).first()

        if not role:
            raise serializers.ValidationError(f"Role '{value}' not found.")
        return role

    def update(self, instance, validated_data):
        if 'role' in validated_data:
            instance.role = validated_data.pop('role')

        if 'status' in validated_data:
            new_status = validated_data.get('status')
            instance.is_active = (new_status == 'Active')

        return super().update(instance, validated_data)


class UserStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=User.StatusChoices.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default='')


class AdminPasswordResetSerializer(serializers.Serializer):
    newPassword = serializers.CharField(min_length=6, required=False)
    new_password = serializers.CharField(min_length=6, required=False)
    requireChangeOnLogin = serializers.BooleanField(required=False, default=False)
    require_change_on_login = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        password = attrs.get('newPassword') or attrs.get('new_password')
        if not password:
            raise serializers.ValidationError({"newPassword": ["This field is required."]})
        attrs['password'] = password
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
