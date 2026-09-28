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
        extra_fields.setdefault('full_name', 'Super Admin')
        extra_fields.setdefault('phone', '+92 300 0000000')
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
    Custom User Model conforming to the ABC Weaving Factory ERP specifications.
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

    # Basic Info
    full_name = models.CharField(max_length=255)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=50)
    alt_phone = models.CharField(max_length=50, blank=True, default='')
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=30,
        choices=GenderChoices.choices,
        default=GenderChoices.MALE
    )

    # Work & Organization
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    company = models.CharField(max_length=255, default='ABC Weaving Mills Ltd')
    branch = models.CharField(max_length=255, default='Head Office - Karachi')
    department = models.CharField(max_length=100, default='Production')
    designation = models.CharField(max_length=150, blank=True, default='')
    shift = models.CharField(max_length=100, default='Morning (08:00 - 17:00)')
    joining_date = models.DateField(null=True, blank=True)
    manager_name = models.CharField(max_length=255, blank=True, default='')

    # Address / Contact
    address = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='Karachi')
    state = models.CharField(max_length=100, blank=True, default='Sindh')
    country = models.CharField(max_length=100, default='Pakistan')
    postal_code = models.CharField(max_length=20, blank=True, default='')

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
    account_expiry = models.DateField(null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    # Audit tracking
    created_date = models.DateField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_last_changed = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    REQUIRED_FIELDS = ['email', 'full_name']

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.full_name} (@{self.username})"

    @property
    def formatted_id(self):
        """Returns standard ERP user ID representation, e.g. USR-001"""
        return f"USR-{self.id:03d}"

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
