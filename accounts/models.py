from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from .constants import ALL_PERMISSION_CODES


class UserManager(BaseUserManager):
    """
    Custom manager for User model where username and email are required.
    """
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError(_('The Username field must be set.'))
        if not email:
            raise ValueError(_('The Email field must be set.'))
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'Active')
        return self.create_user(username, email, password, **extra_fields)


class Role(models.Model):
    """
    Role model for Dynamic Role-Based Access Control (RBAC).
    """
    class StatusChoices(models.TextChoices):
        ACTIVE = 'Active', _('Active')
        INACTIVE = 'Inactive', _('Inactive')

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    is_system = models.BooleanField(
        default=False,
        help_text="System roles are protected and cannot be deleted."
    )
    permissions = models.JSONField(
        default=list,
        help_text="List of permission codenames (e.g. ['users.view', 'mfg.add'])"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def user_count(self):
        return self.users.count()


class User(AbstractUser):
    """
    Simplified User Model with only essential fields.
    """
    class StatusChoices(models.TextChoices):
        ACTIVE = 'Active', _('Active')
        INACTIVE = 'Inactive', _('Inactive')
        SUSPENDED = 'Suspended', _('Suspended')
        PENDING = 'Pending', _('Pending')

    class GenderChoices(models.TextChoices):
        MALE = 'Male', _('Male')
        FEMALE = 'Female', _('Female')
        OTHER = 'Other', _('Other')
        PREFER_NOT_TO_SAY = 'Prefer not to say', _('Prefer not to say')

    # Remove unused AbstractUser fields
    first_name = None
    last_name = None

    # Core user fields
    email = models.EmailField(_('email address'), unique=True)
    phone = models.CharField(max_length=50, blank=True, default='')
    address = models.TextField(blank=True, default='')
    gender = models.CharField(
        max_length=30,
        choices=GenderChoices.choices,
        default=GenderChoices.MALE
    )
    designation = models.CharField(max_length=150, blank=True, default='')

    # Role & Access
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.ACTIVE
    )
    two_factor_enabled = models.BooleanField(default=False)

    objects = UserManager()

    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"@{self.username}"

    @property
    def formatted_id(self):
        """Returns standard ERP user ID representation, e.g. USR-001"""
        if isinstance(self.id, int):
            return f"USR-{self.id:03d}"
        return f"USR-{str(self.id)}"

    def get_permissions(self):
        """
        Returns list of permission strings.
        Superuser gets all system permissions.
        Otherwise permissions are retrieved from assigned Role.
        """
        if self.is_superuser:
            return ALL_PERMISSION_CODES
        if self.role and self.role.status == 'Active':
            return self.role.permissions or []
        return []

    def has_perm_code(self, perm_code):
        """
        Check if user has a specific permission code.
        """
        if self.is_superuser:
            return True
        return perm_code in self.get_permissions()
