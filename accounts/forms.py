from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users in Django Admin with all ERP fields.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username',
            'email',
            'full_name',
            'phone',
            'alt_phone',
            'avatar',
            'dob',
            'gender',
            'employee_id',
            'company',
            'branch',
            'department',
            'designation',
            'shift',
            'joining_date',
            'manager_name',
            'address',
            'city',
            'state',
            'country',
            'postal_code',
            'role',
            'status',
            'account_expiry',
            'two_factor_enabled',
            'notes',
            'is_active',
            'is_staff',
            'is_superuser',
        )


class CustomUserChangeForm(UserChangeForm):
    """
    Form for updating existing users in Django Admin.
    """
    class Meta:
        model = User
        fields = '__all__'
