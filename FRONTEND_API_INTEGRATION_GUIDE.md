# ABC Weaving Factory ERP – Frontend API Integration Guide
**Version**: 1.0.0  
**Backend Framework**: Django 5.0 + Django REST Framework + SimpleJWT  
**Base URL**: `http://localhost:8000/api/v1` (Development) / `https://api.erp.fahadweaving.com/api/v1` (Production)  

---

## 1. Quick Start & Server Environments

### 1.1 Base URLs & Headers
| Environment | Base URL |
| :--- | :--- |
| **Local Development** | `http://127.0.0.1:8000/api/v1` |
| **Staging** | `https://staging-api.erp.fahadweaving.com/api/v1` |
| **Production** | `https://api.erp.fahadweaving.com/api/v1` |

Every authenticated request must include the JWT token in the `Authorization` header:
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### 1.2 Default Test Credentials (Pre-seeded)
| Account Role | Username / Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` or `admin@fahadweaving.com` | `Admin@123456` | Full ERP access (All 39 permissions) |
| **Production Manager** | `ali.raza` or `production@fahadweaving.com` | `Production@123` | Manufacturing, Sizing, Beams, Looms, Yarn |
| **QC Inspector** | `tariq.mehmood` or `qc@fahadweaving.com` | `Quality@123` | Yarn, Sizing, Looms inspection |

---

## 2. Standardized Response Formats

All backend endpoints strictly follow standardized JSON envelopes so frontend code never has to guess response structures.

### 2.1 Standard Success Response (Single Object / Action)
```json
{
  "success": true,
  "message": "Operation completed successfully.",
  "data": { ... }
}
```

### 2.2 Standard Paginated List Response
```json
{
  "success": true,
  "count": 128,
  "totalPages": 13,
  "currentPage": 1,
  "pageSize": 10,
  "results": [ ... ]
}
```

### 2.3 Standard Error Response (`400`, `401`, `403`, `404`)
```json
{
  "success": false,
  "message": "Validation failed.",
  "errors": {
    "username": ["This username is already registered."],
    "email": ["Enter a valid email address."],
    "detail": "Additional error details if available."
  }
}
```

---

## 3. Module 1: Authentication API (`/auth/`)

> **Note on Registration**: Public sign-up is disabled by design. User accounts are created exclusively by administrators through the User Management API.

---

### 3.1 Login (Obtain Tokens & User Profile)
- **Method**: `POST`
- **Endpoint**: `/auth/login/`
- **Auth Required**: `No`

#### Request Body
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `username` | String | **Yes** | Username **or** Email address |
| `password` | String | **Yes** | User password |

```json
{
  "username": "admin",
  "password": "Admin@123456"
}
```

#### Success Response (`200 OK`)
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
      "rawId": 1,
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
      "notes": "Primary ERP administrator with unrestricted access.",
      "avatar": null,
      "accountExpiry": "2030-12-31",
      "lastLogin": "28 Sep 2026, 10:42 AM",
      "createdDate": "2019-01-15",
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

---

### 3.2 Refresh JWT Access Token
- **Method**: `POST`
- **Endpoint**: `/auth/refresh/`
- **Auth Required**: `No`

#### Request Body
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Success Response (`200 OK`)
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

### 3.3 Logout
- **Method**: `POST`
- **Endpoint**: `/auth/logout/`
- **Auth Required**: `Yes` (`Bearer <access_token>`)

#### Request Body
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Successfully logged out."
}
```

---

### 3.4 Get Current Authenticated User (`/me`)
- **Method**: `GET`
- **Endpoint**: `/auth/me/`
- **Auth Required**: `Yes` (`Bearer <access_token>`)

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "USR-001",
      "rawId": 1,
      "username": "admin",
      "fullName": "Muhammad Ahmed",
      "email": "admin@fahadweaving.com",
      "role": "Super Admin",
      "permissions": [ ... ]
    }
  }
}
```

---

## 4. Module 2: User Management API (`/users/`)

### 4.1 Summary Statistics
- **Method**: `GET`
- **Endpoint**: `/users/stats/`
- **Permission**: `users.view`

#### Success Response (`200 OK`)
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

### 4.2 List Users (Filters, Search & Pagination)
- **Method**: `GET`
- **Endpoint**: `/users/`
- **Permission**: `users.view`

#### Query Parameters
| Parameter | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `search` | String | `?search=Ali` or `?search=USR-001` | Matches username, name, email, phone, employee ID |
| `role` | String / Int | `?role=Production Manager` or `?role=2` | Filter by role name or ID |
| `department` | String | `?department=Production` | Filter by department |
| `status` | String | `?status=Active` | `Active`, `Inactive`, `Suspended`, `Pending` |
| `company` | String | `?company=ABC Weaving` | Filter by company name |
| `branch` | String | `?branch=Karachi` | Filter by branch name |
| `ordering` | String | `?ordering=-createdDate` | `fullName`, `-fullName`, `createdDate`, `-createdDate` |
| `page` | Integer | `?page=1` | Page number (default: 1) |
| `page_size` | Integer | `?page_size=10` | Page size (default: 10, max: 100) |

#### Success Response (`200 OK`)
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
      "rawId": 1,
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
      "avatar": null,
      "accountExpiry": "2030-12-31",
      "lastLogin": "28 Sep 2026, 10:42 AM",
      "createdDate": "2019-01-15",
      "twoFactorEnabled": true
    }
  ]
}
```

---

### 4.3 Create User (Onboard Employee)
- **Method**: `POST`
- **Endpoint**: `/users/`
- **Permission**: `users.add`
- **Note**: Both `camelCase` and `snake_case` input keys are accepted.

#### Request Body Schema
```json
{
  "username": "ali.raza",
  "fullName": "Ali Raza",
  "email": "production@fahadweaving.com",
  "password": "SecurePassword123!",
  "role": "Production Manager",
  "department": "Production",
  "status": "Active",
  "phone": "+92 321 9988771",
  "altPhone": "+92 300 4433221",
  "dob": "1985-08-22",
  "gender": "Male",
  "designation": "Production Manager",
  "employeeId": "EMP-025",
  "company": "ABC Weaving Mills Ltd",
  "branch": "Factory 01 - SITE Industrial Area",
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

#### Success Response (`201 Created`)
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

### 4.4 Retrieve Single User Details
- **Method**: `GET`
- **Endpoint**: `/users/{id}/` (Accepts numeric ID `1` or formatted ID `USR-001`)
- **Permission**: `users.view`

#### Success Response (`200 OK`)
Returns full user profile details including granted permissions.

---

### 4.5 Update User Details
- **Method**: `PUT` or `PATCH`
- **Endpoint**: `/users/{id}/`
- **Permission**: `users.edit`

#### Request Body
Provide only the fields you wish to update:
```json
{
  "fullName": "Ali Raza Siddiqui",
  "designation": "Senior Production Manager",
  "phone": "+92 321 9988772",
  "role": "Production Manager"
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "User details updated successfully.",
  "data": { ... }
}
```

---

### 4.6 Change User Status
- **Method**: `POST`
- **Endpoint**: `/users/{id}/status/`
- **Permission**: `users.status`

#### Request Body
```json
{
  "status": "Inactive",
  "reason": "Employee on leave until Dec 2026"
}
```

#### Success Response (`200 OK`)
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

### 4.7 Admin Password Reset
- **Method**: `POST`
- **Endpoint**: `/users/{id}/reset-password/`
- **Permission**: `users.reset_pwd`

#### Request Body
```json
{
  "newPassword": "BrandNewSecurePassword123!"
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Password has been successfully updated."
}
```

---

### 4.8 Delete User
- **Method**: `DELETE`
- **Endpoint**: `/users/{id}/`
- **Permission**: `users.delete`

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "User account permanently removed."
}
```

---

## 5. Module 3: Roles & Permissions API (`/roles/` & `/permissions/`)

### 5.1 List All Roles
- **Method**: `GET`
- **Endpoint**: `/roles/`
- **Auth Required**: `Yes`

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Super Admin",
      "slug": "super_admin",
      "description": "Unrestricted system access across all ERP modules.",
      "userCount": 1,
      "status": "Active",
      "isSystem": true,
      "permissions": [ ... ],
      "created_at": "2026-09-28T08:00:00Z",
      "updated_at": "2026-09-28T08:00:00Z"
    }
  ]
}
```

---

### 5.2 Create Custom Role
- **Method**: `POST`
- **Endpoint**: `/roles/`
- **Permission**: `roles.manage`

#### Request Body
```json
{
  "name": "Warehouse Supervisor",
  "description": "Supervises raw yarn intakes and spare parts.",
  "status": "Active",
  "permissions": [
    "dashboard.view",
    "yarn.view",
    "yarn.add",
    "inv.view",
    "inv.add"
  ]
}
```

#### Success Response (`201 Created`)
```json
{
  "success": true,
  "message": "Role created successfully.",
  "data": {
    "id": 5,
    "name": "Warehouse Supervisor",
    "slug": "warehouse_supervisor",
    "description": "Supervises raw yarn intakes and spare parts.",
    "userCount": 0,
    "status": "Active",
    "isSystem": false,
    "permissions": [
      "dashboard.view",
      "yarn.view",
      "yarn.add",
      "inv.view",
      "inv.add"
    ]
  }
}
```

---

### 5.3 Update Role & Permission Matrix
- **Method**: `PUT` or `PATCH`
- **Endpoint**: `/roles/{id}/`
- **Permission**: `roles.manage`

#### Request Body
```json
{
  "description": "Updated role description",
  "permissions": [
    "dashboard.view",
    "yarn.view",
    "yarn.add",
    "yarn.edit",
    "inv.view",
    "inv.add"
  ]
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Role updated successfully.",
  "data": { ... }
}
```

---

### 5.4 Delete Custom Role
- **Method**: `DELETE`
- **Endpoint**: `/roles/{id}/`
- **Permission**: `roles.manage`
- **Safety Protection**: System-protected roles (`is_system: true`) return `400 Bad Request` and cannot be deleted.

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Role deleted successfully."
}
```

---

### 5.5 Get Available System Permissions (For Matrix Rendering)
- **Method**: `GET`
- **Endpoint**: `/permissions/`
- **Auth Required**: `Yes`

Returns the hierarchical taxonomy of ERP modules and granular action checkboxes.

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "data": [
    {
      "module": "dashboard",
      "name": "Dashboard",
      "permissions": [
        {
          "code": "dashboard.view",
          "name": "View Dashboard",
          "description": "View dashboard KPIs and statistics"
        },
        {
          "code": "dashboard.export",
          "name": "Export Dashboard",
          "description": "Export analytics summary reports"
        }
      ]
    },
    {
      "module": "user_management",
      "name": "User Management",
      "permissions": [
        {
          "code": "users.view",
          "name": "View Users",
          "description": "View user lists and detailed user profiles"
        },
        {
          "code": "users.add",
          "name": "Add Users",
          "description": "Create/onboard new user accounts"
        },
        {
          "code": "users.edit",
          "name": "Edit Users",
          "description": "Update user profile and work data"
        },
        {
          "code": "users.delete",
          "name": "Delete Users",
          "description": "Delete/deactivate user accounts"
        },
        {
          "code": "users.status",
          "name": "Manage User Status",
          "description": "Toggle status (Active/Inactive/Suspended/Pending)"
        },
        {
          "code": "users.reset_pwd",
          "name": "Reset Password",
          "description": "Admin reset password"
        },
        {
          "code": "roles.manage",
          "name": "Manage Roles",
          "description": "Create/Edit roles and assign permissions"
        },
        {
          "code": "activity.view",
          "name": "View Activities",
          "description": "Inspect audit trail activity logs"
        }
      ]
    }
  ]
}
```

---

## 6. Module 4: Activity & Audit Logs API (`/activities/`)

### 6.1 List Audit Trail Logs
- **Method**: `GET`
- **Endpoint**: `/activities/`
- **Permission**: `activity.view`

#### Query Parameters
| Parameter | Type | Example | Description |
| :--- | :--- | :--- | :--- |
| `search` | String | `?search=logged in` | Search description, username, IP |
| `action` | String | `?action=Login` | `Login`, `Logout`, `User Created`, `Password Changed`, etc. |
| `username` | String | `?username=admin` | Filter by user username |
| `date_from` | Date (`YYYY-MM-DD`) | `?date_from=2026-09-01` | Filter start date |
| `date_to` | Date (`YYYY-MM-DD`) | `?date_to=2026-09-30` | Filter end date |
| `page` | Integer | `?page=1` | Page number |
| `page_size` | Integer | `?page_size=20` | Page size (default: 20) |

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "count": 110,
  "totalPages": 6,
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
      "description": "Muhammad Ahmed logged in successfully.",
      "module": "Authentication",
      "ipAddress": "192.168.1.10",
      "device": "Chrome on macOS",
      "status": "Success"
    }
  ]
}
```

---

## 7. Complete ERP Permissions Matrix Reference

| Module | Code | Description |
| :--- | :--- | :--- |
| **Dashboard** | `dashboard.view` | View dashboard KPIs and statistics |
| | `dashboard.export` | Export analytics summary reports |
| **User Management** | `users.view` | View user directory & detailed profiles |
| | `users.add` | Create / onboard new user accounts |
| | `users.edit` | Update user personal & organizational info |
| | `users.delete` | Delete / purge user accounts |
| | `users.status` | Change user status (Active / Inactive / Suspended) |
| | `users.reset_pwd` | Administrator password reset |
| | `roles.manage` | Create, update, or remove roles and assign permissions |
| | `activity.view` | Inspect audit trail activity logs |
| **Manufacturing** | `mfg.view` | View raw manufacturing flow & stats |
| | `mfg.add` | Add manufacturing batch records |
| | `mfg.edit` | Modify active manufacturing entries |
| | `mfg.delete` | Delete manufacturing batch records |
| | `mfg.assign` | Assign warp beams to looms |
| | `mfg.status` | Update machine / batch operational status |
| **Raw Material** | `yarn.view` | View yarn stock and lot numbers |
| | `yarn.add` | Record yarn arrivals and vendor intake |
| | `yarn.edit` | Modify yarn counts, bag rates, weights |
| | `yarn.delete` | Delete raw material intake entries |
| **Sizing** | `sizing.view` | View sizing records and sized beam logs |
| | `sizing.add` | Create new sizing batch |
| | `sizing.edit` | Edit sizing chemicals and parameters |
| | `sizing.delete` | Delete sizing records |
| **Warp Beams** | `beams.view` | View available and mounted warp beams |
| | `beams.add` | Register new warp beams |
| | `beams.edit` | Edit beam length and cuts |
| | `beams.delete` | Delete beam entries |
| | `beams.assign` | Mount beam on active loom machine |
| **Looms** | `looms.view` | Monitor looms & daily meterage output |
| | `looms.add` | Register new loom machines |
| | `looms.edit` | Modify loom RPM, model, or status |
| | `looms.delete` | Decommission / remove loom |
| | `looms.assign_beam`| Mount / Dismount beam from loom |
| | `looms.production` | Log daily fabric meters produced |
| **Purchases** | `po.view` | View purchase orders & vendor invoices |
| | `po.add` | Create purchase orders |
| | `po.edit` | Modify purchase order details |
| | `po.delete` | Cancel purchase orders |
| | `po.approve` | Authorize purchase order payments |
| **Sales** | `sale.view` | View sales orders & fabric billing |
| | `sale.add` | Create client sales invoices |
| | `sale.edit` | Edit sales invoices |
| | `sale.delete` | Void sales orders |
| | `sale.dispatch` | Issue gate passes and mark dispatched |
| **Inventory** | `inv.view` | Inspect spare parts and fabric store |
| | `inv.add` | Add inventory SKUs |
| | `inv.edit` | Edit items and minimum stock limits |
| | `inv.delete` | Delete inventory items |
| | `inv.adjust` | Perform stock balance adjustments |
| **Workforce** | `emp.view` | View employee directory & wages |
| | `emp.add` | Onboard factory workers |
| | `emp.edit` | Update employee designations & wages |
| | `emp.delete` | Offboard workers |
| | `payroll.process` | Calculate and generate monthly payroll |
| **Attendance** | `att.view` | View daily biometric clock-ins |
| | `att.mark` | Record manual check-in / late entries |
| | `att.edit` | Edit clock-in / clock-out timestamps |
| | `att.export` | Export attendance sheets |
| **Reports** | `rep.view` | Access reporting analytics |
| | `rep.generate` | Run date-range financial & mfg queries |
| | `rep.export` | Download formal balance & stock PDFs |
| **Settings** | `settings.view` | View ERP configuration |
| | `settings.company` | Update company registration & address |
| | `settings.security`| Configure 2FA, session timeouts & audit rules |

---

## 8. Frontend Integration Code Snippets (TypeScript / Axios)

### 8.1 TypeScript Types (`types/erp.ts`)
```typescript
export interface UserProfile {
  id: string; // e.g. "USR-001"
  rawId: number;
  username: string;
  fullName: string;
  firstName?: string;
  lastName?: string;
  email: string;
  phone: string;
  altPhone?: string;
  dob?: string | null;
  gender: 'Male' | 'Female' | 'Other' | 'Prefer not to say';
  role: string;
  roleId: number;
  department: string;
  designation?: string;
  employeeId?: string;
  company?: string;
  branch?: string;
  status: 'Active' | 'Inactive' | 'Suspended' | 'Pending';
  joiningDate?: string | null;
  manager?: string;
  shift?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postalCode?: string;
  notes?: string;
  avatar?: string | null;
  accountExpiry?: string | null;
  lastLogin?: string | null;
  createdDate: string;
  twoFactorEnabled: boolean;
  permissions: string[];
}

export interface RoleItem {
  id: number;
  name: string;
  slug: string;
  description: string;
  userCount: number;
  status: 'Active' | 'Inactive';
  isSystem: boolean;
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface ActivityLogItem {
  id: number;
  timestamp: string;
  date: string;
  userId?: string;
  username: string;
  userFullName: string;
  action: string;
  description: string;
  module: string;
  ipAddress?: string;
  device?: string;
  status: 'Success' | 'Failed';
}

export interface PaginatedResponse<T> {
  success: boolean;
  count: number;
  totalPages: number;
  currentPage: number;
  pageSize: number;
  results: T[];
}

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data: T;
  errors?: Record<string, string[]>;
}
```

---

### 8.2 Axios Client with Automatic Token Refresh (`api/client.ts`)
```typescript
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request Interceptor: Attach Access Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const accessToken = localStorage.getItem('access_token');
    if (accessToken && config.headers) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Auto Refresh on 401
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: AxiosError | null, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Ignore 401 from login or refresh endpoints
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login/') &&
      !originalRequest.url?.includes('/auth/refresh/')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        // Clear local storage and redirect to login
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
          refresh: refreshToken,
        });

        const newAccessToken = data.access;
        localStorage.setItem('access_token', newAccessToken);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        }

        processQueue(null, newAccessToken);
        return apiClient(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr as AxiosError, null);
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
```

---

### 8.3 Permission Guard Helper (`utils/permissions.ts`)
```typescript
import { UserProfile } from '../types/erp';

export const hasPermission = (user: UserProfile | null, permissionCode: string): boolean => {
  if (!user) return false;
  // Super Admin bypass
  if (user.role === 'Super Admin' || user.permissions?.includes('*')) return true;
  return user.permissions?.includes(permissionCode) ?? false;
};

export const hasAnyPermission = (user: UserProfile | null, permissionCodes: string[]): boolean => {
  return permissionCodes.some((code) => hasPermission(user, code));
};

export const hasAllPermissions = (user: UserProfile | null, permissionCodes: string[]): boolean => {
  return permissionCodes.every((code) => hasPermission(user, code));
};
```

---

### 8.4 Example: Permission Guard Component in React
```tsx
import React from 'react';
import { useAuth } from '@/context/AuthContext';
import { hasPermission } from '@/utils/permissions';

interface Props {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const Can: React.FC<Props> = ({ permission, children, fallback = null }) => {
  const { user } = useAuth();
  if (!hasPermission(user, permission)) {
    return <>{fallback}</>;
  }
  return <>{children}</>;
};

// Usage:
// <Can permission="users.add">
//   <Button onClick={openCreateUserModal}>Add New User</Button>
// </Can>
```

---

## 9. Common Questions & Troubleshooting

1. **How do I handle both username and email logins?**
   - Simply pass whatever string the user inputs into the `username` field in `POST /api/v1/auth/login/`. The backend automatically checks if it matches a username or an email.
2. **Can I use numeric ID `1` instead of `USR-001` in user endpoints?**
   - Yes! All user detail endpoints (`/users/{id}/`, `/users/{id}/status/`, etc.) accept both `1` and `USR-001`.
3. **What happens if a user is set to `Inactive` or `Suspended`?**
   - Their active session is blocked, and any subsequent login attempts will receive a `403 Forbidden` response explaining that the account is suspended/inactive.
4. **How do I upload user avatars?**
   - Use `multipart/form-data` with an `avatar` file field when calling `POST /api/v1/users/` or `PATCH /api/v1/users/{id}/`.
