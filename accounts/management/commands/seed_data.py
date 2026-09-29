"""
Management command to seed initial roles, permissions, administrative user, and sample users.
Usage:
    python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from accounts.models import User, Role
from accounts.constants import ALL_PERMISSION_CODES
from audit_logs.models import ActivityLog


class Command(BaseCommand):
    help = 'Seeds initial ERP roles, superuser, and sample accounts'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting ERP database seeding..."))

        # 1. Seed Roles
        super_admin_role, _ = Role.objects.get_or_create(
            slug='super_admin',
            defaults={
                'name': 'Super Admin',
                'description': 'Unrestricted system access across all ERP modules.',
                'status': 'Active',
                'is_system': True,
                'permissions': ALL_PERMISSION_CODES,
            }
        )
        if not super_admin_role.is_system or super_admin_role.permissions != ALL_PERMISSION_CODES:
            super_admin_role.is_system = True
            super_admin_role.permissions = ALL_PERMISSION_CODES
            super_admin_role.save()

        prod_mgr_perms = [
            "dashboard.view", "dashboard.export",
            "mfg.view", "mfg.add", "mfg.edit", "mfg.assign", "mfg.status",
            "yarn.view", "yarn.add", "yarn.edit",
            "sizing.view", "sizing.add", "sizing.edit",
            "beams.view", "beams.add", "beams.assign",
            "looms.view", "looms.add", "looms.edit", "looms.production"
        ]
        prod_mgr_role, _ = Role.objects.get_or_create(
            slug='production_manager',
            defaults={
                'name': 'Production Manager',
                'description': 'Comprehensive control over manufacturing, sizing, beams, and looms.',
                'status': 'Active',
                'is_system': False,
                'permissions': prod_mgr_perms,
            }
        )

        qc_perms = [
            "dashboard.view",
            "yarn.view",
            "sizing.view",
            "looms.view"
        ]
        qc_role, _ = Role.objects.get_or_create(
            slug='quality_control_inspector',
            defaults={
                'name': 'Quality Control Inspector',
                'description': 'Performs yarn CSP audits and fabric inspection.',
                'status': 'Active',
                'is_system': False,
                'permissions': qc_perms,
            }
        )

        inv_perms = [
            "dashboard.view",
            "yarn.view", "yarn.add", "yarn.edit",
            "inv.view", "inv.add", "inv.edit", "inv.delete", "inv.adjust",
            "po.view", "po.add", "po.edit"
        ]
        inv_role, _ = Role.objects.get_or_create(
            slug='inventory_manager',
            defaults={
                'name': 'Inventory Manager',
                'description': 'Manages raw material stores, spare parts, and inventory SKUs.',
                'status': 'Active',
                'is_system': False,
                'permissions': inv_perms,
            }
        )

        self.stdout.write(self.style.SUCCESS("[OK] Seeded standard ERP roles."))

        # 2. Seed Admin User
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@fahadweaving.com',
                password='Admin@123456',
                phone='+92 300 8492011',
                gender='Male',
                designation='System Administrator',
                address='Plot 21, SITE Area, Karachi',
                two_factor_enabled=True,
                role=super_admin_role,
                status='Active',
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created Super Admin user (admin / Admin@123456)."))
        else:
            admin_user.role = super_admin_role
            admin_user.is_superuser = True
            admin_user.is_staff = True
            admin_user.status = 'Active'
            admin_user.set_password('Admin@123456')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("[OK] Updated existing admin user credentials."))

        # 3. Seed Sample User 1: Ali Raza
        ali_user = User.objects.filter(username='ali.raza').first()
        if not ali_user:
            ali_user = User.objects.create_user(
                username='ali.raza',
                email='production@fahadweaving.com',
                password='Production@123',
                phone='+92 321 9988771',
                gender='Male',
                designation='Production Manager',
                address='Plot 18, Block B, North Nazimabad, Karachi',
                two_factor_enabled=True,
                role=prod_mgr_role,
                status='Active',
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created sample user ali.raza (Production@123)."))

        # 4. Seed Sample User 2: Tariq Mehmood
        tariq_user = User.objects.filter(username='tariq.mehmood').first()
        if not tariq_user:
            tariq_user = User.objects.create_user(
                username='tariq.mehmood',
                email='qc@fahadweaving.com',
                password='Quality@123',
                phone='+92 333 5544332',
                gender='Male',
                designation='QC Inspector',
                role=qc_role,
                status='Active',
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created sample user tariq.mehmood (Quality@123)."))

        # 5. Seed Initial Activity Logs
        if ActivityLog.objects.count() == 0:
            ActivityLog.objects.create(
                user=admin_user,
                username='admin',
                user_full_name='Admin',
                action='Login',
                description='Admin logged in via 2FA authentication.',
                module='Authentication',
                ip_address='192.168.1.10',
                device='Chrome on macOS',
                status='Success',
            )
            ActivityLog.objects.create(
                user=admin_user,
                username='admin',
                user_full_name='Admin',
                action='Role Created',
                description='Initialized standard ERP roles and permissions.',
                module='User Management',
                ip_address='127.0.0.1',
                device='System Seeder',
                status='Success',
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created initial activity audit trail entries."))

        self.stdout.write(self.style.SUCCESS("\n==> Seeding completed successfully!"))
