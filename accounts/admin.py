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
        'username', 'email', 'phone', 'gender', 'designation',
        'role', 'status', 'is_active', 'is_staff'
    )
    list_filter = ('status', 'role', 'gender', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'phone', 'designation', 'address')
    ordering = ('-id',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('User Details', {
            'fields': (
                'email', 'phone', 'gender', 'designation', 'address'
            )
        }),
        ('Role & Status', {
            'fields': (
                'role', 'status', 'two_factor_enabled',
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        ('Authentication', {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('User Details', {
            'fields': (
                'email', 'phone', 'gender', 'designation', 'address', 'role', 'status', 'two_factor_enabled'
            )
        }),
    )
