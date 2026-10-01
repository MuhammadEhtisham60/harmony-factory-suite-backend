"""
Complete Permissions Matrix Schema for ABC Weaving Factory ERP.
"""

MODULE_PERMISSIONS = [
    {
        "module": "dashboard",
        "name": "Dashboard",
        "permissions": [
            {"code": "dashboard.view", "name": "View Dashboard", "description": "View dashboard KPIs and statistics"},
            {"code": "dashboard.export", "name": "Export Dashboard", "description": "Export analytics summary reports"},
        ]
    },
    {
        "module": "user_management",
        "name": "User Management",
        "permissions": [
            {"code": "users.view", "name": "View Users", "description": "View user lists and detailed user profiles"},
            {"code": "users.add", "name": "Add Users", "description": "Create/onboard new user accounts"},
            {"code": "users.edit", "name": "Edit Users", "description": "Update user profile and work data"},
            {"code": "users.delete", "name": "Delete Users", "description": "Delete/deactivate user accounts"},
            {"code": "users.status", "name": "Manage User Status", "description": "Toggle status (Active/Inactive/Suspended/Pending)"},
            {"code": "users.reset_pwd", "name": "Reset Password", "description": "Admin reset password"},
            {"code": "roles.manage", "name": "Manage Roles", "description": "Create/Edit roles and assign permissions"},
            {"code": "activity.view", "name": "View Activities", "description": "Inspect audit trail activity logs"},
        ]
    },
    {
        "module": "raw_manufacturing",
        "name": "Raw Manufacturing",
        "permissions": [
            {"code": "mfg.view", "name": "View Manufacturing", "description": "View raw manufacturing flow & stats"},
            {"code": "mfg.add", "name": "Add Manufacturing Batch", "description": "Add new manufacturing batch records"},
            {"code": "mfg.edit", "name": "Edit Manufacturing Batch", "description": "Modify active manufacturing entries"},
            {"code": "mfg.delete", "name": "Delete Manufacturing Batch", "description": "Delete manufacturing batch records"},
            {"code": "mfg.assign", "name": "Assign Warp Beams", "description": "Assign warp beams to looms"},
            {"code": "mfg.status", "name": "Update Machine Status", "description": "Update machine / batch operational status"},
        ]
    },
    {
        "module": "raw_material",
        "name": "Raw Material",
        "permissions": [
            {"code": "yarn.view", "name": "View Yarn", "description": "View yarn stock and lot numbers"},
            {"code": "yarn.add", "name": "Add Yarn Intake", "description": "Record yarn arrivals and vendor intake"},
            {"code": "yarn.edit", "name": "Edit Yarn Details", "description": "Modify yarn counts, bag rates, weights"},
            {"code": "yarn.delete", "name": "Delete Yarn Intake", "description": "Delete raw material intake entries"},
        ]
    },
    {
        "module": "yarn_buyer",
        "name": "Yarn Buyers",
        "permissions": [
            {"code": "yarn_buyer.view", "name": "View Yarn Buyers", "description": "View yarn buyer list and details"},
            {"code": "yarn_buyer.add", "name": "Add Yarn Buyer", "description": "Create new yarn buyer records"},
            {"code": "yarn_buyer.edit", "name": "Edit Yarn Buyer", "description": "Update yarn buyer details"},
            {"code": "yarn_buyer.delete", "name": "Delete Yarn Buyer", "description": "Delete yarn buyer records"},
        ]
    },
    {
        "module": "sizing",
        "name": "Sizing",
        "permissions": [
            {"code": "sizing.view", "name": "View Sizing Units", "description": "View sizing unit list and details"},
            {"code": "sizing.add", "name": "Add Sizing Unit", "description": "Create new sizing unit records"},
            {"code": "sizing.edit", "name": "Edit Sizing Unit", "description": "Update sizing unit details"},
            {"code": "sizing.delete", "name": "Delete Sizing Unit", "description": "Delete sizing unit records"},
        ]
    },
    {
        "module": "yarn_intake",
        "name": "Yarn Intake",
        "permissions": [
            {"code": "yarn_intake.view", "name": "View Yarn Intakes", "description": "View yarn intake records and stock summary"},
            {"code": "yarn_intake.add", "name": "Add Yarn Intake", "description": "Record new yarn intake from supplier"},
            {"code": "yarn_intake.edit", "name": "Edit Yarn Intake", "description": "Modify yarn intake quantities and rates"},
            {"code": "yarn_intake.delete", "name": "Delete Yarn Intake", "description": "Delete yarn intake records"},
        ]
    },
    {
        "module": "yarn_outcome",
        "name": "Yarn Outcome",
        "permissions": [
            {"code": "yarn_outcome.view", "name": "View Yarn Outcomes", "description": "View yarn outcome (sizing/weft/sold) records"},
            {"code": "yarn_outcome.add", "name": "Add Yarn Outcome", "description": "Record yarn dispatched for sizing, weft, or sold"},
            {"code": "yarn_outcome.edit", "name": "Edit Yarn Outcome", "description": "Modify yarn outcome quantities and type"},
            {"code": "yarn_outcome.delete", "name": "Delete Yarn Outcome", "description": "Delete yarn outcome records and return stock"},
        ]
    },
    {
        "module": "sizing",
        "name": "Sizing",
        "permissions": [
            {"code": "sizing.view", "name": "View Sizing", "description": "View sizing records and sized beam logs"},
            {"code": "sizing.add", "name": "Add Sizing Batch", "description": "Create new sizing batch"},
            {"code": "sizing.edit", "name": "Edit Sizing Batch", "description": "Edit sizing chemicals and parameters"},
            {"code": "sizing.delete", "name": "Delete Sizing Batch", "description": "Delete sizing records"},
        ]
    },
    {
        "module": "beams",
        "name": "Warp Beams",
        "permissions": [
            {"code": "beams.view", "name": "View Warp Beams", "description": "View available and mounted warp beams"},
            {"code": "beams.add", "name": "Add Warp Beam", "description": "Register new warp beams"},
            {"code": "beams.edit", "name": "Edit Warp Beam", "description": "Edit beam length and cuts"},
            {"code": "beams.delete", "name": "Delete Warp Beam", "description": "Delete beam entries"},
            {"code": "beams.assign", "name": "Mount Beam to Loom", "description": "Mount beam on active loom machine"},
        ]
    },
    {
        "module": "looms",
        "name": "Looms",
        "permissions": [
            {"code": "looms.view", "name": "Monitor Looms", "description": "Monitor looms & daily meterage output"},
            {"code": "looms.add", "name": "Register Loom", "description": "Register new loom machines"},
            {"code": "looms.edit", "name": "Edit Loom Info", "description": "Modify loom RPM, model, or status"},
            {"code": "looms.delete", "name": "Decommission Loom", "description": "Decommission / remove loom"},
            {"code": "looms.assign_beam", "name": "Loom Beam Mount/Dismount", "description": "Mount / Dismount beam from loom"},
            {"code": "looms.production", "name": "Log Daily Production", "description": "Log daily fabric meters produced"},
        ]
    },
    {
        "module": "purchases",
        "name": "Purchases",
        "permissions": [
            {"code": "po.view", "name": "View Purchases", "description": "View purchase orders & vendor invoices"},
            {"code": "po.add", "name": "Create Purchase Order", "description": "Create purchase orders"},
            {"code": "po.edit", "name": "Edit Purchase Order", "description": "Modify purchase order details"},
            {"code": "po.delete", "name": "Cancel Purchase Order", "description": "Cancel purchase orders"},
            {"code": "po.approve", "name": "Approve Purchase Order", "description": "Authorize purchase order payments"},
        ]
    },
    {
        "module": "sales",
        "name": "Sales",
        "permissions": [
            {"code": "sale.view", "name": "View Sales", "description": "View sales orders & fabric billing"},
            {"code": "sale.add", "name": "Create Sales Invoice", "description": "Create client sales invoices"},
            {"code": "sale.edit", "name": "Edit Sales Invoice", "description": "Edit sales invoices"},
            {"code": "sale.delete", "name": "Void Sales Order", "description": "Void sales orders"},
            {"code": "sale.dispatch", "name": "Dispatch Sales Order", "description": "Issue gate passes and mark dispatched"},
        ]
    },
    {
        "module": "inventory",
        "name": "Inventory",
        "permissions": [
            {"code": "inv.view", "name": "Inspect Inventory", "description": "Inspect spare parts and fabric store"},
            {"code": "inv.add", "name": "Add Inventory SKU", "description": "Add inventory SKUs"},
            {"code": "inv.edit", "name": "Edit Inventory SKU", "description": "Edit items and minimum stock limits"},
            {"code": "inv.delete", "name": "Delete Inventory SKU", "description": "Delete inventory items"},
            {"code": "inv.adjust", "name": "Adjust Stock Balance", "description": "Perform stock balance adjustments"},
        ]
    },
    {
        "module": "workforce",
        "name": "Workforce",
        "permissions": [
            {"code": "emp.view", "name": "View Workforce", "description": "View employee directory & wages"},
            {"code": "emp.add", "name": "Onboard Worker", "description": "Onboard factory workers"},
            {"code": "emp.edit", "name": "Edit Worker Details", "description": "Update employee designations & wages"},
            {"code": "emp.delete", "name": "Offboard Worker", "description": "Offboard workers"},
            {"code": "payroll.process", "name": "Process Payroll", "description": "Calculate and generate monthly payroll"},
        ]
    },
    {
        "module": "attendance",
        "name": "Attendance",
        "permissions": [
            {"code": "att.view", "name": "View Attendance", "description": "View daily biometric clock-ins"},
            {"code": "att.mark", "name": "Record Manual Attendance", "description": "Record manual check-in / late entries"},
            {"code": "att.edit", "name": "Edit Clock Timestamps", "description": "Edit clock-in / clock-out timestamps"},
            {"code": "att.export", "name": "Export Attendance", "description": "Export attendance sheets"},
        ]
    },
    {
        "module": "reports",
        "name": "Reports",
        "permissions": [
            {"code": "rep.view", "name": "Access Reports", "description": "Access reporting analytics"},
            {"code": "rep.generate", "name": "Generate Reports", "description": "Run date-range financial & mfg queries"},
            {"code": "rep.export", "name": "Export Reports", "description": "Download formal balance & stock PDFs"},
        ]
    },
    {
        "module": "settings",
        "name": "Settings",
        "permissions": [
            {"code": "settings.view", "name": "View Settings", "description": "View ERP configuration"},
            {"code": "settings.company", "name": "Company Settings", "description": "Update company registration & address"},
            {"code": "settings.security", "name": "Security Settings", "description": "Configure 2FA, session timeouts & audit rules"},
        ]
    },
]

# Flat list of all valid permission codes
ALL_PERMISSION_CODES = [
    perm["code"]
    for group in MODULE_PERMISSIONS
    for perm in group["permissions"]
]

# Lookup map from permission code to metadata
PERMISSION_LOOKUP = {
    perm["code"]: {
        "code": perm["code"],
        "name": perm["name"],
        "description": perm["description"],
        "module": group["module"],
        "module_name": group["name"],
    }
    for group in MODULE_PERMISSIONS
    for perm in group["permissions"]
}
