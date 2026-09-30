"""
Serializers for Authentication, Users, and Roles modules.
"""

from rest_framework import serializers
from django.utils.text import slugify
from django.contrib.auth import authenticate
from .models import User, Role
from .constants import ALL_PERMISSION_CODES


class RoleSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
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
    Serializer for user profile representation (login, /me, user list, user detail).
    """
    id = serializers.CharField(source='formatted_id', read_only=True)
    rawId = serializers.IntegerField(source='id', read_only=True)
    role = serializers.SerializerMethodField()
    roleId = serializers.SerializerMethodField()
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled', read_only=True)
    permissions = serializers.SerializerMethodField()
    lastLogin = serializers.SerializerMethodField()
    dateJoined = serializers.DateTimeField(source='date_joined', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'rawId',
            'username',
            'email',
            'phone',
            'address',
            'gender',
            'designation',
            'role',
            'roleId',
            'status',
            'twoFactorEnabled',
            'permissions',
            'lastLogin',
            'dateJoined',
            'is_active',
            'is_staff',
            'is_superuser',
        ]

    def get_role(self, obj):
        return obj.role.name if obj.role else None

    def get_roleId(self, obj):
        return str(obj.role.id) if obj.role else None

    def get_lastLogin(self, obj):
        if obj.last_login:
            return obj.last_login.strftime('%d %b %Y, %I:%M %p')
        return None

    def get_permissions(self, obj):
        user_perms = obj.get_permissions()
        return {code: code in user_perms for code in ALL_PERMISSION_CODES}


class UserListSerializer(UserProfileSerializer):
    """Alias for listing users in User Management table"""
    pass


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/onboarding a new user.
    """
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled', required=False, default=False)
    role = serializers.CharField(required=True, write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'phone',
            'address',
            'gender',
            'designation',
            'role',
            'status',
            'twoFactorEnabled',
        ]

    def to_internal_value(self, data):
        # Support snake_case keys if provided
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        mappings = {
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

        user = User(**validated_data)
        user.role = role
        user.set_password(password)
        user.is_active = (user.status == 'Active')
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing user profile.
    """
    twoFactorEnabled = serializers.BooleanField(source='two_factor_enabled', required=False)
    role = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'phone',
            'address',
            'gender',
            'designation',
            'role',
            'status',
            'twoFactorEnabled',
        ]

    def to_internal_value(self, data):
        data_copy = data.copy() if hasattr(data, 'copy') else dict(data)
        mappings = {
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
