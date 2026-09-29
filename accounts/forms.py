from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """
    Form for creating new users in Django Admin.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            'username',
            'email',
            'phone',
            'gender',
            'designation',
            'address',
            'role',
            'status',
            'two_factor_enabled',
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
