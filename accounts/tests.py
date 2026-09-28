"""
Comprehensive API test suite for Authentication, Users, Roles, and Activity Logs.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import User, Role
from audit_logs.models import ActivityLog


class AuthAndUserManagementAPITests(APITestCase):

    def setUp(self):
        # Create Super Admin Role
        self.super_admin_role = Role.objects.create(
            name="Super Admin",
            slug="super_admin",
            description="System Admin",
            is_system=True,
            status="Active",
            permissions=["dashboard.view", "users.view", "users.add", "users.edit", "users.delete", "users.status", "users.reset_pwd", "roles.manage", "activity.view"]
        )

        # Create Production Manager Role
        self.prod_role = Role.objects.create(
            name="Production Manager",
            slug="production_manager",
            description="Production management",
            is_system=False,
            status="Active",
            permissions=["dashboard.view", "mfg.view", "mfg.add"]
        )

        # Create Admin User
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@fahadweaving.com",
            password="Admin@123456",
            full_name="Muhammad Ahmed",
            phone="+92 300 8492011",
            role=self.super_admin_role,
            status="Active"
        )

        # Create Regular User
        self.worker = User.objects.create_user(
            username="ali.raza",
            email="ali@fahadweaving.com",
            password="Password@123",
            full_name="Ali Raza",
            phone="+92 321 0000000",
            role=self.prod_role,
            status="Active"
        )

    # ------------------------------------------------------------------------
    # 1. Authentication Tests
    # ------------------------------------------------------------------------
    def test_login_with_username_success(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin',
            'password': 'Admin@123456'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('tokens', response.data['data'])
        self.assertIn('access', response.data['data']['tokens'])
        self.assertIn('refresh', response.data['data']['tokens'])
        self.assertEqual(response.data['data']['user']['username'], 'admin')

    def test_login_with_email_success(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin@fahadweaving.com',
            'password': 'Admin@123456'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['user']['email'], 'admin@fahadweaving.com')

    def test_login_invalid_password(self):
        url = reverse('auth-login')
        response = self.client.post(url, {
            'username': 'admin',
            'password': 'WrongPassword!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])

    def test_current_user_me_endpoint(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('auth-me')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['user']['username'], 'admin')
        self.assertIn('permissions', response.data['data']['user'])

    def test_logout(self):
        # Obtain tokens first
        login_url = reverse('auth-login')
        login_resp = self.client.post(login_url, {
            'username': 'admin',
            'password': 'Admin@123456'
        }, format='json')
        refresh_token = login_resp.data['data']['tokens']['refresh']
        access_token = login_resp.data['data']['tokens']['access']

        logout_url = reverse('auth-logout')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post(logout_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

    # ------------------------------------------------------------------------
    # 2. User Management Tests
    # ------------------------------------------------------------------------
    def test_user_stats(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-stats')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('totalUsers', response.data['data'])
        self.assertIn('activeUsers', response.data['data'])
        self.assertIn('totalRoles', response.data['data'])
        self.assertEqual(response.data['data']['totalUsers'], 2)

    def test_list_users(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-list-create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['count'], 2)
        self.assertIsInstance(response.data['results'], list)

    def test_create_user(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-list-create')
        payload = {
            "username": "usman.khan",
            "fullName": "Usman Khan",
            "email": "usman@fahadweaving.com",
            "password": "Password123!",
            "role": "Production Manager",
            "department": "Production",
            "status": "Active",
            "phone": "+92 345 1122334",
            "employeeId": "EMP-088"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['username'], 'usman.khan')

        # Verify created in DB
        created_user = User.objects.get(username='usman.khan')
        self.assertEqual(created_user.full_name, 'Usman Khan')
        self.assertEqual(created_user.role.name, 'Production Manager')

    def test_get_user_by_formatted_id(self):
        self.client.force_authenticate(user=self.admin)
        formatted_id = self.worker.formatted_id
        url = reverse('users-detail', kwargs={'pk': formatted_id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['username'], self.worker.username)

    def test_update_user_status(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-status-change', kwargs={'pk': self.worker.id})
        response = self.client.post(url, {
            'status': 'Inactive',
            'reason': 'Leave of absence'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.status, 'Inactive')
        self.assertFalse(self.worker.is_active)

    def test_admin_reset_password(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-reset-password', kwargs={'pk': self.worker.id})
        response = self.client.post(url, {
            'newPassword': 'BrandNewPassword123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.worker.refresh_from_db()
        self.assertTrue(self.worker.check_password('BrandNewPassword123!'))

    def test_prevent_self_deletion(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('users-detail', kwargs={'pk': self.admin.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])

    # ------------------------------------------------------------------------
    # 3. Roles & Permissions Tests
    # ------------------------------------------------------------------------
    def test_list_roles(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('roles-list-create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['data']), 2)

    def test_create_custom_role(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('roles-list-create')
        payload = {
            "name": "Warehouse Supervisor",
            "description": "Store supervisor",
            "status": "Active",
            "permissions": ["inv.view", "inv.add"]
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['name'], 'Warehouse Supervisor')

    def test_prevent_system_role_deletion(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('roles-detail', kwargs={'pk': self.super_admin_role.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("System protected roles cannot be deleted", response.data['message'])

    def test_permissions_list(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('permissions-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIsInstance(response.data['data'], list)
        # Check first module is dashboard
        self.assertEqual(response.data['data'][0]['module'], 'dashboard')

    # ------------------------------------------------------------------------
    # 4. Activity Logs Tests
    # ------------------------------------------------------------------------
    def test_activity_logs_list(self):
        self.client.force_authenticate(user=self.admin)
        # Trigger an action that creates an activity log
        url = reverse('activities-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('results', response.data)
