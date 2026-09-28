# User Management & Authentication Module – Django REST API Specification

## 1. Overview & Architecture

This document specifies the backend API requirements for the **User Management**, **Role-Based Access Control (RBAC)**, and **Audit Activity Log** systems of the **ABC Weaving Factory ERP**.

### Key Architectural Guidelines
- **Framework**: Django 4.2+ or 5.0+ with Django REST Framework (DRF).
- **Authentication**: **JWT (JSON Web Tokens)** using `djangorestframework-simplejwt`.
- **Sign-up Flow**: **NO public registration / sign-up**. User accounts are created exclusively by authorized administrators via the User Management module.
- **Login Flow**: Users log in using their `username` or `email` and password. Upon successful login, SimpleJWT returns an `access` token and a `refresh` token along with the user's profile and granted permissions.
- **Role & Permissions**: Dynamic permission system where roles are assigned a list of permission codes corresponding to factory ERP modules.

---

## 2. Recommended Django Packages

```bash
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers django-filter pillow
```

### `settings.py` Configuration

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    
    # Local apps
    'accounts',
    'organization',
    'audit_logs',
]

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}
```

---

## 3. Database Schema & Django Models

### 3.1 `accounts/models.py`

```python
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

class UserManager(BaseUserManager):
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
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active'
    )
    is_system = models.BooleanField(default=False)  # System roles cannot be deleted
    permissions = models.JSONField(default=list, help_text="List of permission codenames (e.g. ['users.view', 'mfg.add'])")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
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
    gender = models.CharField(max_length=30, choices=GenderChoices.choices, default=GenderChoices.MALE)

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
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.ACTIVE)
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
```

---

### 3.2 `audit_logs/models.py`

```python
from django.db import models
from django.conf import settings

class ActivityLog(models.Model):
    class ActionChoices(models.TextChoices):
        LOGIN = 'Login', 'Login'
        LOGOUT = 'Logout', 'Logout'
        PROFILE_UPDATED = 'Profile Updated', 'Profile Updated'
        PASSWORD_CHANGED = 'Password Changed', 'Password Changed'
        ROLE_CHANGED = 'Role Changed', 'Role Changed'
        PERMISSION_UPDATED = 'Permission Updated', 'Permission Updated'
        USER_CREATED = 'User Created', 'User Created'
        USER_ACTIVATED = 'User Activated', 'User Activated'
        USER_DEACTIVATED = 'User Deactivated', 'User Deactivated'
        USER_DELETED = 'User Deleted', 'User Deleted'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    username = models.CharField(max_length=150)
    user_full_name = models.CharField(max_length=255)
    action = models.CharField(max_length=50, choices=ActionChoices.choices)
    description = models.TextField()
    module = models.CharField(max_length=100, default='User Management')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, default='Success')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.action} at {self.created_at}"
```

---

## 4. Complete Permissions Matrix Schema

The backend must seed / maintain the following standard permissions:

| Module Code | Module Name | Permission Code | Description |
| :--- | :--- | :--- | :--- |
| `dashboard` | Dashboard | `dashboard.view` | View dashboard KPIs and statistics |
| `dashboard` | Dashboard | `dashboard.export` | Export analytics summary reports |
| `user_management` | User Management | `users.view` | View user lists and detailed user profiles |
| `user_management` | User Management | `users.add` | Create/onboard new user accounts |
| `user_management` | User Management | `users.edit` | Update user profile and work data |
| `user_management` | User Management | `users.delete` | Delete/deactivate user accounts |
| `user_management` | User Management | `users.status` | Toggle status (Active/Inactive/Suspended/Pending) |
| `user_management` | User Management | `users.reset_pwd` | Admin reset password |
| `user_management` | User Management | `roles.manage` | Create/Edit roles and assign permissions |
| `user_management` | User Management | `activity.view` | Inspect audit trail activity logs |
| `raw_manufacturing` | Raw Manufacturing | `mfg.view` | View raw manufacturing flow & stats |
| `raw_manufacturing` | Raw Manufacturing | `mfg.add` | Add new manufacturing batch records |
| `raw_manufacturing` | Raw Manufacturing | `mfg.edit` | Modify active manufacturing entries |
| `raw_manufacturing` | Raw Manufacturing | `mfg.delete` | Delete manufacturing batch records |
| `raw_manufacturing` | Raw Manufacturing | `mfg.assign` | Assign warp beams to looms |
| `raw_manufacturing` | Raw Manufacturing | `mfg.status` | Update machine / batch operational status |
| `raw_material` | Raw Material | `yarn.view` | View yarn stock and lot numbers |
| `raw_material` | Raw Material | `yarn.add` | Record yarn arrivals and vendor intake |
| `raw_material` | Raw Material | `yarn.edit` | Modify yarn counts, bag rates, weights |
| `raw_material` | Raw Material | `yarn.delete` | Delete raw material intake entries |
| `sizing` | Sizing | `sizing.view` | View sizing records and sized beam logs |
| `sizing` | Sizing | `sizing.add` | Create new sizing batch |
| `sizing` | Sizing | `sizing.edit` | Edit sizing chemicals and parameters |
| `sizing` | Sizing | `sizing.delete` | Delete sizing records |
| `beams` | Warp Beams | `beams.view` | View available and mounted warp beams |
| `beams` | Warp Beams | `beams.add` | Register new warp beams |
| `beams` | Warp Beams | `beams.edit` | Edit beam length and cuts |
| `beams` | Warp Beams | `beams.delete` | Delete beam entries |
| `beams` | Warp Beams | `beams.assign` | Mount beam on active loom machine |
| `looms` | Looms | `looms.view` | Monitor looms & daily meterage output |
| `looms` | Looms | `looms.add` | Register new loom machines |
| `looms` | Looms | `looms.edit` | Modify loom RPM, model, or status |
| `looms` | Looms | `looms.delete` | Decommission / remove loom |
| `looms` | Looms | `looms.assign_beam` | Mount / Dismount beam from loom |
| `looms` | Looms | `looms.production` | Log daily fabric meters produced |
| `purchases` | Purchases | `po.view` | View purchase orders & vendor invoices |
| `purchases` | Purchases | `po.add` | Create purchase orders |
| `purchases` | Purchases | `po.edit` | Modify purchase order details |
| `purchases` | Purchases | `po.delete` | Cancel purchase orders |
| `purchases` | Purchases | `po.approve` | Authorize purchase order payments |
| `sales` | Sales | `sale.view` | View sales orders & fabric billing |
| `sales` | Sales | `sale.add` | Create client sales invoices |
| `sales` | Sales | `sale.edit` | Edit sales invoices |
| `sales` | Sales | `sale.delete` | Void sales orders |
| `sales` | Sales | `sale.dispatch` | Issue gate passes and mark dispatched |
| `inventory` | Inventory | `inv.view` | Inspect spare parts and fabric store |
| `inventory` | Inventory | `inv.add` | Add inventory SKUs |
| `inventory` | Inventory | `inv.edit` | Edit items and minimum stock limits |
| `inventory` | Inventory | `inv.delete` | Delete inventory items |
| `inventory` | Inventory | `inv.adjust` | Perform stock balance adjustments |
| `workforce` | Workforce | `emp.view` | View employee directory & wages |
| `workforce` | Workforce | `emp.add` | Onboard factory workers |
| `workforce` | Workforce | `emp.edit` | Update employee designations & wages |
| `workforce` | Workforce | `emp.delete` | Offboard workers |
| `workforce` | Workforce | `payroll.process` | Calculate and generate monthly payroll |
| `attendance` | Attendance | `att.view` | View daily biometric clock-ins |
| `attendance` | Attendance | `att.mark` | Record manual check-in / late entries |
| `attendance` | Attendance | `att.edit` | Edit clock-in / clock-out timestamps |
| `attendance` | Attendance | `att.export` | Export attendance sheets |
| `reports` | Reports | `rep.view` | Access reporting analytics |
| `reports` | Reports | `rep.generate` | Run date-range financial & mfg queries |
| `reports` | Reports | `rep.export` | Download formal balance & stock PDFs |
| `settings` | Settings | `settings.view` | View ERP configuration |
| `settings` | Settings | `settings.company` | Update company registration & address |
| `settings` | Settings | `settings.security` | Configure 2FA, session timeouts & audit rules |

---

## 5. API Endpoints Specification

### 5.1 Authentication API (`/api/v1/auth/`)

#### 5.1.1 Login (JWT Obtain Token)
- **Method**: `POST`
- **URL**: `/api/v1/auth/login/`
- **Auth Required**: No (Public)
- **Description**: Authenticate user via username or email and return JWT access/refresh tokens along with profile details and permissions.

**Request Body:**
```json
{
  "username": "admin",      // Required (string: username or email)
  "password": "SecretPassword123!" // Required (string)
}
```

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "tokens": {
      "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    },
    "user": {
      "id": "USR-001",
      "username": "admin",
      "fullName": "Muhammad Ahmed",
      "email": "admin@fahadweaving.com",
      "phone": "+92 300 8492011",
      "role": "Super Admin",
      "department": "Administration",
      "designation": "System Administrator",
      "employeeId": "EMP-001",
      "company": "ABC Weaving Mills Ltd",
      "branch": "Head Office - Karachi",
      "status": "Active",
      "avatar": "https://domain.com/media/avatars/admin.jpg",
      "twoFactorEnabled": true,
      "permissions": [
        "dashboard.view",
        "dashboard.export",
        "users.view",
        "users.add",
        "users.edit",
        "users.delete",
        "users.status",
        "users.reset_pwd",
        "roles.manage",
        "activity.view"
      ]
    }
  }
}
```

**Error Response (`401 Unauthorized`):**
```json
{
  "success": false,
  "message": "Invalid username or password.",
  "errors": {
    "detail": "No active account found with the given credentials."
  }
}
```

---

#### 5.1.2 Refresh JWT Token
- **Method**: `POST`
- **URL**: `/api/v1/auth/refresh/`
- **Auth Required**: No
- **Request Body:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // Required
}
```
- **Success Response (`200 OK`):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

#### 5.1.3 Logout
- **Method**: `POST`
- **URL**: `/api/v1/auth/logout/`
- **Auth Required**: Yes (`Bearer <token>`)
- **Request Body:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." // Required
}
```
- **Success Response (`200 OK`):**
```json
{
  "success": true,
  "message": "Successfully logged out."
}
```

---

#### 5.1.4 Get Current Authenticated User (`/me`)
- **Method**: `GET`
- **URL**: `/api/v1/auth/me/`
- **Auth Required**: Yes (`Bearer <token>`)
- **Response (`200 OK`):** Returns profile, role, and permissions of the token owner.

---

### 5.2 User Management API (`/api/v1/users/`)

#### 5.2.1 Users Summary Statistics
- **Method**: `GET`
- **URL**: `/api/v1/users/stats/`
- **Auth Required**: Yes (`users.view` permission)
- **Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": {
    "totalUsers": 128,
    "activeUsers": 112,
    "inactiveUsers": 10,
    "pendingUsers": 4,
    "suspendedUsers": 2,
    "totalRoles": 10
  }
}
```

---

#### 5.2.2 List Users (with Multi-Filters, Search & Pagination)
- **Method**: `GET`
- **URL**: `/api/v1/users/`
- **Query Parameters**:
  - `search`: Filter across `username`, `fullName`, `email`, `phone`, `employeeId`.
  - `role`: Filter by role name (e.g. `Admin`, `Production Manager`).
  - `department`: Filter by department (e.g. `Production`, `Accounts`).
  - `company`: Filter by company name.
  - `branch`: Filter by branch name.
  - `status`: Filter by `Active`, `Inactive`, `Suspended`, `Pending`.
  - `page`: Page number (default `1`).
  - `page_size`: Page size (default `10`).
  - `ordering`: Sort by field (e.g. `full_name`, `-created_date`, `last_login_at`).

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "count": 16,
  "totalPages": 2,
  "currentPage": 1,
  "pageSize": 10,
  "results": [
    {
      "id": "USR-001",
      "username": "admin",
      "fullName": "Muhammad Ahmed",
      "firstName": "Muhammad",
      "lastName": "Ahmed",
      "email": "admin@fahadweaving.com",
      "phone": "+92 300 8492011",
      "altPhone": "+92 42 35918800",
      "dob": "1988-04-14",
      "gender": "Male",
      "role": "Super Admin",
      "roleId": 1,
      "department": "Administration",
      "designation": "System Administrator",
      "employeeId": "EMP-001",
      "company": "ABC Weaving Mills Ltd",
      "branch": "Head Office - Karachi",
      "status": "Active",
      "joiningDate": "2019-01-15",
      "manager": "Board of Directors",
      "shift": "General (09:00 - 18:00)",
      "address": "Plot 21, SITE Area, Karachi",
      "city": "Karachi",
      "state": "Sindh",
      "country": "Pakistan",
      "postalCode": "74000",
      "notes": "Primary ERP administrator.",
      "avatar": "https://domain.com/media/avatars/admin.jpg",
      "accountExpiry": "2030-12-31",
      "lastLogin": "28 Sep 2026, 10:42 AM",
      "createdDate": "2019-01-15",
      "twoFactorEnabled": true
    }
  ]
}
```

---

#### 5.2.3 Create User (Onboarding)
- **Method**: `POST`
- **URL**: `/api/v1/users/`
- **Auth Required**: Yes (`users.add` permission)
- **Description**: Create a new user account with hashed password. Automatically logs an audit activity event.

**Field Specifications Table:**

| Field Name | Type | Required / Optional | Validation Rules & Defaults |
| :--- | :--- | :--- | :--- |
| `username` | String | **Required** | Unique, min 3 chars, alphanumeric + `.` `-` `_` |
| `fullName` | String | **Required** | Full display name (e.g. `Ali Raza`) |
| `email` | String | **Required** | Valid email format, unique |
| `password` | String | **Required** | Min 6 characters |
| `role` | String / Int | **Required** | Role name or Role ID |
| `department` | String | **Required** | Selected from active departments |
| `status` | String | **Required** | `Active`, `Inactive`, `Suspended`, `Pending` (default `Active`) |
| `phone` | String | **Required** | Valid phone number string |
| `firstName` | String | Optional | First name |
| `lastName` | String | Optional | Last name |
| `altPhone` | String | Optional | Alternate contact number |
| `dob` | Date | Optional | `YYYY-MM-DD` |
| `gender` | String | Optional | `Male`, `Female`, `Other`, `Prefer not to say` |
| `designation` | String | Optional | Job title (e.g. `Machine Operator`) |
| `employeeId` | String | Optional | Unique Employee ID (e.g. `EMP-025`) |
| `company` | String | Optional | Default `ABC Weaving Mills Ltd` |
| `branch` | String | Optional | Default `Head Office - Karachi` |
| `shift` | String | Optional | Default `Morning (08:00 - 17:00)` |
| `joiningDate` | Date | Optional | `YYYY-MM-DD` |
| `manager` | String | Optional | Reporting manager name |
| `address` | String | Optional | Residential / Street address |
| `city` | String | Optional | City name |
| `state` | String | Optional | State / Province |
| `country` | String | Optional | Default `Pakistan` |
| `postalCode` | String | Optional | Postal code |
| `notes` | String | Optional | Internal admin remarks |
| `accountExpiry`| Date | Optional | `YYYY-MM-DD` |
| `twoFactorEnabled` | Boolean | Optional | Default `false` |
| `avatar` | File / URL | Optional | Image upload (PNG, JPG, WebP) |

**Sample Request Payload:**
```json
{
  "username": "ali.raza",
  "fullName": "Ali Raza",
  "firstName": "Ali",
  "lastName": "Raza",
  "email": "production@fahadweaving.com",
  "password": "SecurePassword123!",
  "role": "Production Manager",
  "department": "Production",
  "designation": "Production Manager",
  "employeeId": "EMP-025",
  "company": "ABC Weaving Mills Ltd",
  "branch": "Factory 01 - SITE Industrial Area",
  "status": "Active",
  "phone": "+92 321 9988771",
  "altPhone": "+92 300 4433221",
  "dob": "1985-08-22",
  "gender": "Male",
  "shift": "Morning (08:00 - 17:00)",
  "joiningDate": "2020-03-01",
  "manager": "Muhammad Ahmed",
  "address": "Plot 18, Block B, North Nazimabad",
  "city": "Karachi",
  "state": "Sindh",
  "country": "Pakistan",
  "postalCode": "74600",
  "notes": "Supervises 48 Tsudakoma looms and raw yarn quality.",
  "accountExpiry": "2028-12-31",
  "twoFactorEnabled": true
}
```

**Success Response (`201 Created`):**
```json
{
  "success": true,
  "message": "User account created successfully.",
  "data": {
    "id": "USR-017",
    "username": "ali.raza",
    "fullName": "Ali Raza",
    "email": "production@fahadweaving.com",
    "role": "Production Manager",
    "status": "Active",
    "createdDate": "2026-09-28"
  }
}
```

---

#### 5.2.4 Retrieve Single User Details
- **Method**: `GET`
- **URL**: `/api/v1/users/{id}/`
- **Auth Required**: Yes (`users.view`)
- **Success Response (`200 OK`):** Returns full user details, organization data, permissions breakdown, and security status.

---

#### 5.2.5 Update User Details
- **Method**: `PUT` or `PATCH`
- **URL**: `/api/v1/users/{id}/`
- **Auth Required**: Yes (`users.edit`)
- **Description**: Update user profile information. Password updates should not be passed here (use dedicated password reset endpoint).

---

#### 5.2.6 Delete User
- **Method**: `DELETE`
- **URL**: `/api/v1/users/{id}/`
- **Auth Required**: Yes (`users.delete`)
- **Description**: Soft delete or permanently remove user account. Automatically writes an audit log event.
- **Success Response (`200 OK` or `204 No Content`):**
```json
{
  "success": true,
  "message": "User account permanently removed."
}
```

---

#### 5.2.7 Change User Status (Activate / Deactivate / Suspend)
- **Method**: `POST`
- **URL**: `/api/v1/users/{id}/status/`
- **Auth Required**: Yes (`users.status`)

**Request Body:**
```json
{
  "status": "Inactive", // Required ('Active', 'Inactive', 'Suspended', 'Pending')
  "reason": "Employee on approved maternity leave until Dec 2026" // Optional string
}
```

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "message": "User status updated to Inactive.",
  "data": {
    "id": "USR-007",
    "status": "Inactive"
  }
}
```

---

#### 5.2.8 Reset Password (Admin Initiated)
- **Method**: `POST`
- **URL**: `/api/v1/users/{id}/reset-password/`
- **Auth Required**: Yes (`users.reset_pwd`)

**Request Body:**
```json
{
  "newPassword": "NewStrongPassword456!", // Required (string, min 6 chars)
  "requireChangeOnLogin": true           // Optional (boolean, default false)
}
```

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "message": "Password has been successfully updated."
}
```

---

### 5.3 Roles & Permissions API (`/api/v1/roles/`)

#### 5.3.1 List All Roles
- **Method**: `GET`
- **URL**: `/api/v1/roles/`
- **Auth Required**: Yes
- **Success Response (`200 OK`):**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Super Admin",
      "slug": "super_admin",
      "description": "Unrestricted system access.",
      "userCount": 2,
      "status": "Active",
      "isSystem": true,
      "permissions": [
        "dashboard.view", "dashboard.export",
        "users.view", "users.add", "users.edit", "users.delete", "users.status", "users.reset_pwd", "roles.manage", "activity.view",
        "mfg.view", "mfg.add", "mfg.edit", "mfg.delete", "mfg.assign", "mfg.status"
      ]
    },
    {
      "id": 2,
      "name": "Production Manager",
      "slug": "production_manager",
      "description": "Comprehensive control over manufacturing, sizing, beams, and looms.",
      "userCount": 4,
      "status": "Active",
      "isSystem": false,
      "permissions": [
        "dashboard.view", "dashboard.export",
        "mfg.view", "mfg.add", "mfg.edit", "mfg.assign", "mfg.status",
        "yarn.view", "yarn.add", "yarn.edit",
        "sizing.view", "sizing.add", "sizing.edit",
        "beams.view", "beams.add", "beams.assign",
        "looms.view", "looms.add", "looms.edit", "looms.production"
      ]
    }
  ]
}
```

---

#### 5.3.2 Create Custom Role
- **Method**: `POST`
- **URL**: `/api/v1/roles/`
- **Auth Required**: Yes (`roles.manage`)

**Request Body:**
```json
{
  "name": "Quality Control Inspector",       // Required (string)
  "description": "Performs yarn CSP audits.", // Optional (string)
  "status": "Active",                         // Optional ('Active' | 'Inactive')
  "permissions": [                           // Required (array of permission strings)
    "dashboard.view",
    "yarn.view",
    "sizing.view",
    "looms.view"
  ]
}
```

---

#### 5.3.3 Update Role & Permission Matrix
- **Method**: `PUT` or `PATCH`
- **URL**: `/api/v1/roles/{id}/`
- **Auth Required**: Yes (`roles.manage`)
- **Description**: Update role title, description, and list of permission codes.

---

#### 5.3.4 Delete Custom Role
- **Method**: `DELETE`
- **URL**: `/api/v1/roles/{id}/`
- **Auth Required**: Yes (`roles.manage`)
- **Rule**: If `role.is_system == True`, return `400 Bad Request` with message `"System protected roles cannot be deleted."`

---

#### 5.3.5 Get All Available System Permissions
- **Method**: `GET`
- **URL**: `/api/v1/permissions/`
- **Auth Required**: Yes
- **Success Response (`200 OK`):** Returns the structured list of modules and granular actions for rendering the permission matrix.

---

### 5.4 Activity & Audit Logs API (`/api/v1/activities/`)

#### 5.4.1 List Activity Logs
- **Method**: `GET`
- **URL**: `/api/v1/activities/`
- **Auth Required**: Yes (`activity.view`)
- **Query Parameters**:
  - `search`: Keyword search in description, username, IP address.
  - `action`: Filter by action (e.g. `Login`, `User Created`, `Password Changed`).
  - `username`: Filter by specific username.
  - `date_from` / `date_to`: Date range query (`YYYY-MM-DD`).
  - `page`: Page number (default `1`).

**Success Response (`200 OK`):**
```json
{
  "success": true,
  "count": 110,
  "currentPage": 1,
  "pageSize": 20,
  "results": [
    {
      "id": 101,
      "timestamp": "28 Sep 2026, 10:42 AM",
      "date": "2026-09-28",
      "userId": "USR-001",
      "username": "admin",
      "userFullName": "Muhammad Ahmed",
      "action": "Login",
      "description": "Muhammad Ahmed logged in via 2FA authentication.",
      "module": "Authentication",
      "ipAddress": "192.168.1.10",
      "device": "Chrome on macOS",
      "status": "Success"
    }
  ]
}
```

---

## 6. Audit Logging Middleware / Helper

The backend should automatically record audit logs on key operations:

```python
# audit_logs/utils.py
from .models import ActivityLog

def log_activity(request, action, description, module="User Management", status="Success", user=None):
    target_user = user or getattr(request, 'user', None)
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    username = target_user.username if (target_user and target_user.is_authenticated) else 'anonymous'
    full_name = getattr(target_user, 'full_name', username)

    ActivityLog.objects.create(
        user=target_user if (target_user and target_user.is_authenticated) else None,
        username=username,
        user_full_name=full_name,
        action=action,
        description=description,
        module=module,
        ip_address=ip,
        device=user_agent[:250],
        status=status,
    )
```

---

## 7. Standard Error Response Format

All error responses from Django REST Framework should follow this standardized format for frontend consistency:

```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "username": ["This username is already registered."],
    "email": ["Enter a valid email address."]
  }
}
```
