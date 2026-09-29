from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'status', 'is_system', 'user_count', 'created_at')
    list_filter = ('status', 'is_system')
    search_fields = ('name', 'slug', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        'username', 'full_name', 'email', 'role',
        'department', 'status', 'is_active', 'is_staff'
    )
    list_filter = ('status', 'role', 'department', 'is_active', 'is_staff')
    search_fields = ('username', 'full_name', 'email', 'phone', 'employee_id')
    ordering = ('-id',)

    # Fields for viewing / editing existing users
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {
            'fields': (
                'full_name', 'first_name', 'last_name', 'email', 'avatar',
                'phone', 'alt_phone', 'dob', 'gender'
            )
        }),
        ('Organization & Work', {
            'fields': (
                'employee_id', 'company', 'branch', 'department',
                'designation', 'shift', 'joining_date', 'manager_name'
            )
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Role & Permissions', {
            'fields': (
                'role', 'status', 'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Security & Audit', {
            'fields': (
                'two_factor_enabled', 'account_expiry', 'last_login_at',
                'password_last_changed', 'notes'
            )
        }),
    )

    # Fields for creating a new user in admin panel
    add_fieldsets = (
        ('Authentication', {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Personal Info', {
            'fields': (
                'full_name', 'email', 'avatar',
                'phone', 'alt_phone', 'dob', 'gender'
            )
        }),
        ('Organization & Work', {
            'fields': (
                'employee_id', 'company', 'branch', 'department',
                'designation', 'shift', 'joining_date', 'manager_name'
            )
        }),
        ('Address', {
            'fields': ('address', 'city', 'state', 'country', 'postal_code')
        }),
        ('Role & Status', {
            'fields': (
                'role', 'status', 'is_active', 'is_staff', 'is_superuser',
                'two_factor_enabled', 'account_expiry', 'notes'
            )
        }),
    )

