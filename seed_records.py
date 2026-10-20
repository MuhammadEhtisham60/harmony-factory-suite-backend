import os
import django
from decimal import Decimal
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User
from factory.purchase.supplier.models import Supplier, SupplierBankAccount
from factory.sales.customer.models import Customer, CustomerBankAccount
from factory.yarn.sizing.models import Sizing
from factory.loom.models import Loom
from factory.beam.models import Beam

superuser = User.objects.filter(is_superuser=True).first()

print(f"Using superuser: {superuser.username if superuser else 'None'}")

# 1. 10 Suppliers
suppliers_data = [
    {
        "supplier_name": "Crescent Spinning Mills Ltd",
        "company_name": "Crescent Group of Companies",
        "phone": "+92 41 8765431",
        "contact_person": "Tariq Mehmood",
        "email": "crescent.spinning@crescent.com.pk",
        "address": "Kotwali Road, Industrial Area, Faisalabad",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-0812345-1",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Habib Bank Limited", "account_title": "Crescent Spinning Mills", "account_number": "00427901234567", "branch_name": "Clock Tower Branch, Faisalabad"}
    },
    {
        "supplier_name": "Kohinoor Textile & Yarn Supplies",
        "company_name": "Kohinoor Mills Ltd",
        "phone": "+92 42 35871234",
        "contact_person": "Muhammad Asif",
        "email": "yarn.sales@kohinoor.com.pk",
        "address": "Peshawar Road, Rawalpindi / Lahore Sales Office",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-1428570-3",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "MCB Bank Limited", "account_title": "Kohinoor Textile Mills", "account_number": "01123456789012", "branch_name": "Gulberg Branch, Lahore"}
    },
    {
        "supplier_name": "Nishat Chunian Spinning Division",
        "company_name": "Nishat Chunian Group",
        "phone": "+92 42 35761730",
        "contact_person": "Bilal Ahmed",
        "email": "orders@nishat.net",
        "address": "31-Q Gulberg II, Lahore",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-2549810-7",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Meezan Bank", "account_title": "Nishat Chunian Ltd", "account_number": "02010103456789", "branch_name": "Main Market Gulberg, Lahore"}
    },
    {
        "supplier_name": "Sapphire Fibres Spinning Unit",
        "company_name": "Sapphire Textile Mills",
        "phone": "+92 42 111-000-100",
        "contact_person": "Shahid Khan",
        "email": "fibres.sales@sapphire.com.pk",
        "address": "7-A/K Main Boulevard, Gulberg II, Lahore",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-3184920-4",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "United Bank Limited", "account_title": "Sapphire Fibres Ltd", "account_number": "09876543210123", "branch_name": "Liberty Market, Lahore"}
    },
    {
        "supplier_name": "Al-Karam Chemical & Sizing Auxiliaries",
        "company_name": "Al-Karam Studio & Aux",
        "phone": "+92 21 35060410",
        "contact_person": "Imran Rafiq",
        "email": "chemicals@alkaram.com",
        "address": "Sector 15, Korangi Industrial Area, Karachi",
        "supplier_type": Supplier.SupplierType.DYES_CHEMICALS,
        "registration_number": "NTN-4912038-9",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Bank Alfalah", "account_title": "Al-Karam Chemicals", "account_number": "01451006789123", "branch_name": "Korangi Branch, Karachi"}
    },
    {
        "supplier_name": "Fazal Cloth Mills Supply Corp",
        "company_name": "Fazal Group",
        "phone": "+92 61 4512345",
        "contact_person": "Khurram Shahzad",
        "email": "fazal.yarn@fazalcloth.com",
        "address": "Khanewal Road, Multan",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-5820194-2",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Allied Bank Limited", "account_title": "Fazal Cloth Mills Ltd", "account_number": "00100456789012", "branch_name": "Abdali Road, Multan"}
    },
    {
        "supplier_name": "Toyota & Tsudakoma Loom Spares PK",
        "company_name": "Weaving Machinery & Spares Co.",
        "phone": "+92 41 8540912",
        "contact_person": "Rizwan Ullah",
        "email": "spares@weavingparts.pk",
        "address": "Samundri Road, Industrial Estate, Faisalabad",
        "supplier_type": Supplier.SupplierType.SPARE_PARTS,
        "registration_number": "NTN-6729104-5",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Faysal Bank", "account_title": "Weaving Spares PK", "account_number": "03140028912345", "branch_name": "D-Ground, Faisalabad"}
    },
    {
        "supplier_name": "Gadoon Weaving Yarn Corporation",
        "company_name": "Yunus Brothers Group (YBG)",
        "phone": "+92 21 38701234",
        "contact_person": "Usman Ali",
        "email": "sales@gadoontextile.com",
        "address": "7-A Muhammad Ali Housing Society, Karachi",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-7391024-8",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Standard Chartered Bank", "account_title": "Gadoon Textile Mills", "account_number": "01728394019283", "branch_name": "I.I. Chundrigar Road, Karachi"}
    },
    {
        "supplier_name": "Pak Poly Packaging & Cones",
        "company_name": "Pak Poly Industrial Packaging",
        "phone": "+92 41 8721900",
        "contact_person": "Nadeem Akhtar",
        "email": "sales@pakpolypackaging.pk",
        "address": "Small Industrial Estate, Sargodha Road, Faisalabad",
        "supplier_type": Supplier.SupplierType.PACKAGING,
        "registration_number": "NTN-8401923-6",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Askari Bank", "account_title": "Pak Poly Packaging", "account_number": "00281920192834", "branch_name": "University Road, Faisalabad"}
    },
    {
        "supplier_name": "Suraj Cotton Mills Yarn Distribution",
        "company_name": "Crescent / Suraj Group",
        "phone": "+92 42 35756000",
        "contact_person": "Zahid Hussain",
        "email": "suraj.yarn@suraj.com.pk",
        "address": "7-B3 Aziz Avenue, Canal Bank, Gulberg V, Lahore",
        "supplier_type": Supplier.SupplierType.YARN,
        "registration_number": "NTN-9501928-1",
        "status": Supplier.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Bank of Punjab", "account_title": "Suraj Cotton Mills", "account_number": "60100928374619", "branch_name": "Main Boulevard, Lahore"}
    }
]

created_suppliers = []
for s_data in suppliers_data:
    bank_info = s_data.pop("bank")
    supplier, _ = Supplier.objects.get_or_create(
        supplier_name=s_data["supplier_name"],
        defaults={**s_data, "created_by": superuser}
    )
    if bank_info and not supplier.bank_accounts.exists():
        SupplierBankAccount.objects.create(
            supplier=supplier,
            bank_name=bank_info["bank_name"],
            account_title=bank_info["account_title"],
            account_number=bank_info["account_number"],
            branch_name=bank_info["branch_name"],
            is_primary=True
        )
    created_suppliers.append(supplier)

print(f"Successfully processed {len(created_suppliers)} Suppliers.")

# 2. 10 Customers
customers_data = [
    {
        "customer_name": "Gul Ahmed Textile Mills Export",
        "company_name": "Gul Ahmed Group",
        "phone": "+92 21 111-485-485",
        "contact_person": "Zubair Ahmed",
        "email": "procurement@gulahmed.com",
        "address": "Plot 82, Landhi Industrial Area, Karachi",
        "customer_type": Customer.CustomerType.EXPORTER,
        "registration_number": "STRN-0102938-4",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Habib Bank Limited", "account_title": "Gul Ahmed Textile Mills", "account_number": "00192837465012", "branch_name": "Landhi Branch, Karachi"}
    },
    {
        "customer_name": "Artistic Milliners Denim Division",
        "company_name": "Artistic Milliners Corp",
        "phone": "+92 21 35050800",
        "contact_person": "Farhan Saeed",
        "email": "fabric.sourcing@artisticmilliners.com",
        "address": "Plot 43/1, Sector 23, Korangi Industrial Area, Karachi",
        "customer_type": Customer.CustomerType.MANUFACTURER,
        "registration_number": "STRN-1293847-5",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Standard Chartered Bank", "account_title": "Artistic Milliners Pvt Ltd", "account_number": "01928374659201", "branch_name": "Clifton Branch, Karachi"}
    },
    {
        "customer_name": "Chenab Fabrics & Garments International",
        "company_name": "Chenab Group Limited",
        "phone": "+92 41 8754472",
        "contact_person": "Kamran Baig",
        "email": "purchasing@chenab.com",
        "address": "Nishatabad, Sheikhupura Road, Faisalabad",
        "customer_type": Customer.CustomerType.EXPORTER,
        "registration_number": "STRN-2384950-6",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Meezan Bank", "account_title": "Chenab Fabrics & Garments", "account_number": "03019283746501", "branch_name": "Kotwali Road, Faisalabad"}
    },
    {
        "customer_name": "Sadaqat Global Home Textiles",
        "company_name": "Sadaqat Limited",
        "phone": "+92 41 8784801",
        "contact_person": "Salman Butt",
        "email": "greige.purchase@sadaqat.com.pk",
        "address": "2-KM Sahianwala Road, Khurrianwala, Faisalabad",
        "customer_type": Customer.CustomerType.MANUFACTURER,
        "registration_number": "STRN-3495061-7",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "MCB Bank Limited", "account_title": "Sadaqat Limited", "account_number": "04829102938475", "branch_name": "Khurrianwala, Faisalabad"}
    },
    {
        "customer_name": "Interloop Apparel & Weaving Division",
        "company_name": "Interloop Limited",
        "phone": "+92 41 4360400",
        "contact_person": "Adnan Malik",
        "email": "weaving.orders@interloop.com.pk",
        "address": "Al-Sadiq Plaza, P-193, Railway Road, Faisalabad",
        "customer_type": Customer.CustomerType.EXPORTER,
        "registration_number": "STRN-4506172-8",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "United Bank Limited", "account_title": "Interloop Limited", "account_number": "05910293847561", "branch_name": "Circular Road, Faisalabad"}
    },
    {
        "customer_name": "Style Textile Performance Fabrics",
        "company_name": "Style Textile (Pvt) Ltd",
        "phone": "+92 42 111-22-33-44",
        "contact_person": "Aamir Sohail",
        "email": "procurement@styletextile.com",
        "address": "126/3, Industrial Area, Kot Lakhpat, Lahore",
        "customer_type": Customer.CustomerType.MANUFACTURER,
        "registration_number": "STRN-5617283-9",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Bank Alfalah", "account_title": "Style Textile Pvt Ltd", "account_number": "06029384756102", "branch_name": "Kot Lakhpat, Lahore"}
    },
    {
        "customer_name": "Faisal Weaving & Cloth Wholesalers",
        "company_name": "Faisal Trading Corp",
        "phone": "+92 41 8541289",
        "contact_person": "Waseem Akram",
        "email": "faisal.cloth@gmail.com",
        "address": "Gole Cloth Market, Rail Bazaar, Faisalabad",
        "customer_type": Customer.CustomerType.WHOLESALER,
        "registration_number": "STRN-6728394-0",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Allied Bank", "account_title": "Faisal Trading Corp", "account_number": "07139485761029", "branch_name": "Rail Bazaar, Faisalabad"}
    },
    {
        "customer_name": "Master Textile Mills Grey Fabric Co",
        "company_name": "Master Group",
        "phone": "+92 42 35391621",
        "contact_person": "Hamza Javed",
        "email": "greyfabric@mastertextiles.com",
        "address": "3.5-KM Raiwind Bypass, Manga Road, Lahore",
        "customer_type": Customer.CustomerType.DISTRIBUTOR,
        "registration_number": "STRN-7839405-1",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Habib Metropolitan Bank", "account_title": "Master Textile Mills Ltd", "account_number": "08240596871234", "branch_name": "Raiwind Road, Lahore"}
    },
    {
        "customer_name": "Liberty Mills Karachi Fabric Hub",
        "company_name": "Liberty Mills Limited",
        "phone": "+92 21 35012541",
        "contact_person": "Omer Sheikh",
        "email": "orders.grey@libertymills.com",
        "address": "A/51-A, S.I.T.E., Manghopir Road, Karachi",
        "customer_type": Customer.CustomerType.EXPORTER,
        "registration_number": "STRN-8940516-2",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Faysal Bank", "account_title": "Liberty Mills Limited", "account_number": "09351607982345", "branch_name": "SITE Branch, Karachi"}
    },
    {
        "customer_name": "Afroze Textile Industries Buying House",
        "company_name": "Afroze Textile Group",
        "phone": "+92 21 36322301",
        "contact_person": "Babar Azam",
        "email": "afroze.sourcing@afroze.com",
        "address": "Plot LA 1/A, Block 22, F.B. Area, Karachi",
        "customer_type": Customer.CustomerType.MANUFACTURER,
        "registration_number": "STRN-9051627-3",
        "status": Customer.StatusChoices.ACTIVE,
        "bank": {"bank_name": "Askari Bank", "account_title": "Afroze Textile Industries", "account_number": "10462718093456", "branch_name": "FB Area Branch, Karachi"}
    }
]

created_customers = []
for c_data in customers_data:
    bank_info = c_data.pop("bank")
    customer, _ = Customer.objects.get_or_create(
        customer_name=c_data["customer_name"],
        defaults={**c_data, "created_by": superuser}
    )
    if bank_info and not customer.bank_accounts.exists():
        CustomerBankAccount.objects.create(
            customer=customer,
            bank_name=bank_info["bank_name"],
            account_title=bank_info["account_title"],
            account_number=bank_info["account_number"],
            branch_name=bank_info["branch_name"],
            is_primary=True
        )
    created_customers.append(customer)

print(f"Successfully processed {len(created_customers)} Customers.")

# 3. 10 Sizing Units
sizings_data = [
    {
        "sizing_name": "Al-Madina High-Speed Sizing & Warp",
        "contact_person": "Haji Abdul Rehman",
        "phone_no": "+92 300 8645210",
        "email": "almadina.sizing@gmail.com",
        "address": "Millat Road, Near Dry Port, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "Equipped with Karl Mayer high-speed sizing machine. Handles 20s to 60s count. Capacity: 15,000 gaz/day."
    },
    {
        "sizing_name": "Rehman Sizing & Slasher Industry",
        "contact_person": "Mian Shahid",
        "phone_no": "+92 301 7891234",
        "email": "rehman.sizing@yahoo.com",
        "address": "Samundri Road, Industrial Estate, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "Specializes in coarse and medium counts (10s - 30s). Rapid set turnarounds."
    },
    {
        "sizing_name": "Sitara Textile Sizing Unit",
        "contact_person": "Chaudhry Akram",
        "phone_no": "+92 302 4567890",
        "email": "sitara.sizing@sitara.com.pk",
        "address": "Jhang Road, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "State of the art automated slurry preparation, continuous moisture controls."
    },
    {
        "sizing_name": "Universal Warp & Sizing Plant",
        "contact_person": "Sheikh Noman",
        "phone_no": "+92 303 1239874",
        "email": "universal.sizing@outlook.com",
        "address": "Sargodha Road, Bypass Chowk, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "Equipped for heavy reed warp beams up to 7,500 total ends."
    },
    {
        "sizing_name": "Millat Sizing Works",
        "contact_person": "Rana Waqas",
        "phone_no": "+92 304 9876543",
        "email": "millat.sizing@gmail.com",
        "address": "Chak 204 RB, Millat Town, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "High speed Karl Mayer and Tsudakoma compatible beams."
    },
    {
        "sizing_name": "Prime Textile Sizing Services",
        "contact_person": "Malik Farooq",
        "phone_no": "+92 305 6543210",
        "email": "primesizing@primegroup.pk",
        "address": "Sheikhupura Road, Khurrianwala Industrial Zone",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "ISO certified starching processes, zero yarn break promise."
    },
    {
        "sizing_name": "Ittefaq Modern Sizing Mills",
        "contact_person": "Sardar Naveed",
        "phone_no": "+92 306 3210987",
        "email": "ittefaq.sizing@hotmail.com",
        "address": "Dijkot Road, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "Caters to high-density poplin and twill warp sets."
    },
    {
        "sizing_name": "Punjab Warp & Sizing Co.",
        "contact_person": "Javed Iqbal",
        "phone_no": "+92 307 2345678",
        "email": "punjab.sizing@punjabtextile.com",
        "address": "Main Canal Road, Saeedabad, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "10 beam creel capacity with dual size boxes."
    },
    {
        "sizing_name": "Faisalabad Sizing & Creel Center",
        "contact_person": "Rashid Minhas",
        "phone_no": "+92 308 3456789",
        "email": "fsd.sizingcenter@gmail.com",
        "address": "Madina Town Industrial Zone, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "Poly-cotton and 100% cotton specialized recipes."
    },
    {
        "sizing_name": "Haseeb Sizing Mill Ltd",
        "contact_person": "Abdul Sattar",
        "phone_no": "+92 309 4567891",
        "email": "haseeb.sizing@haseebtextile.com",
        "address": "Chiniot Road, Faisalabad",
        "status": Sizing.StatusChoices.ACTIVE,
        "notes": "High-volume contract sizing for air jet and rapier weaving."
    }
]

created_sizings = []
for sz in sizings_data:
    sizing, _ = Sizing.objects.get_or_create(
        sizing_name=sz["sizing_name"],
        defaults={**sz, "created_by": superuser}
    )
    created_sizings.append(sizing)

print(f"Successfully processed {len(created_sizings)} Sizing units.")

# 4. 10 Looms
looms_data = [
    {
        "loom_code": "LM-001",
        "loom_name": "Toyota Air Jet JAT810 #1",
        "model_number": "JAT810-190",
        "width": Decimal("75.000000"),
        "installation_date": date(2023, 2, 10),
        "location": "Weaving Shed A - Line 1",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Air Jet Loom, 900 RPM operating speed. 4-color electronic weft insertion."
    },
    {
        "loom_code": "LM-002",
        "loom_name": "Toyota Air Jet JAT810 #2",
        "model_number": "JAT810-190",
        "width": Decimal("75.000000"),
        "installation_date": date(2023, 2, 10),
        "location": "Weaving Shed A - Line 1",
        "status": Loom.StatusChoices.PRODUCTION,
        "notes": "High-speed poplin & twill weaving. Excellent energy efficiency."
    },
    {
        "loom_code": "LM-003",
        "loom_name": "Toyota Air Jet JAT710 #3",
        "model_number": "JAT710-210",
        "width": Decimal("82.000000"),
        "installation_date": date(2022, 6, 15),
        "location": "Weaving Shed A - Line 2",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Wider reed space (82 inch) suitable for sheeting fabrics."
    },
    {
        "loom_code": "LM-004",
        "loom_name": "Toyota Air Jet JAT710 #4",
        "model_number": "JAT710-210",
        "width": Decimal("82.000000"),
        "installation_date": date(2022, 6, 15),
        "location": "Weaving Shed A - Line 2",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Equipped with positive cam motion and electronic let-off."
    },
    {
        "loom_code": "LM-005",
        "loom_name": "Tsudakoma ZAX9100 #5",
        "model_number": "ZAX9100-230",
        "width": Decimal("90.000000"),
        "installation_date": date(2023, 8, 20),
        "location": "Weaving Shed B - Line 1",
        "status": Loom.StatusChoices.PRODUCTION,
        "notes": "Tsudakoma Soft Weave system, 90 inch width for export bedding."
    },
    {
        "loom_code": "LM-006",
        "loom_name": "Tsudakoma ZAX9100 #6",
        "model_number": "ZAX9100-230",
        "width": Decimal("90.000000"),
        "installation_date": date(2023, 8, 20),
        "location": "Weaving Shed B - Line 1",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Electronic dobby with up to 16 harness frames."
    },
    {
        "loom_code": "LM-007",
        "loom_name": "Picanol OmniPlus Summum #7",
        "model_number": "OMNI-190",
        "width": Decimal("75.000000"),
        "installation_date": date(2024, 1, 12),
        "location": "Weaving Shed B - Line 2",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Picanol BlueBox electronic platform with Sumo direct drive motor."
    },
    {
        "loom_code": "LM-008",
        "loom_name": "Picanol OmniPlus Summum #8",
        "model_number": "OMNI-190",
        "width": Decimal("75.000000"),
        "installation_date": date(2024, 1, 12),
        "location": "Weaving Shed B - Line 2",
        "status": Loom.StatusChoices.PRODUCTION,
        "notes": "Optimized air nozzle consumption, automated relay nozzle tuning."
    },
    {
        "loom_code": "LM-009",
        "loom_name": "Picanol OptiMax-i Rapier #9",
        "model_number": "OPT-220",
        "width": Decimal("86.000000"),
        "installation_date": date(2024, 5, 18),
        "location": "Weaving Shed C - Heavy Weaves",
        "status": Loom.StatusChoices.ACTIVE,
        "notes": "Rapier loom for high-density heavy canvas, duck and fancy structures."
    },
    {
        "loom_code": "LM-010",
        "loom_name": "Sulzer Ruti G6200 #10",
        "model_number": "G6200-190",
        "width": Decimal("75.000000"),
        "installation_date": date(2021, 11, 5),
        "location": "Weaving Shed C - Heavy Weaves",
        "status": Loom.StatusChoices.MAINTENANCE,
        "notes": "Rapier loom scheduled for routine gripper replacement and oil change."
    }
]

created_looms = []
for lm in looms_data:
    loom, _ = Loom.objects.get_or_create(
        loom_code=lm["loom_code"],
        defaults={**lm, "created_by": superuser}
    )
    created_looms.append(loom)

print(f"Successfully processed {len(created_looms)} Looms.")

# 5. 30 Beams
counts = ["20/1", "24/1", "30/1", "40/1", "52/1", "60/1", "16/1", "10/1"]
widths = [Decimal("68.000000"), Decimal("72.000000"), Decimal("75.000000"), Decimal("82.000000"), Decimal("86.000000"), Decimal("90.000000")]
lengths = [Decimal("1600.000000"), Decimal("1800.000000"), Decimal("2000.000000"), Decimal("2200.000000"), Decimal("2500.000000")]
weights = [Decimal("290.500000"), Decimal("320.000000"), Decimal("350.250000"), Decimal("380.000000"), Decimal("410.750000")]
ends = [4200, 4800, 5200, 5600, 6000, 6400, 7200]
statuses = [
    Beam.StatusChoices.AVAILABLE,
    Beam.StatusChoices.AVAILABLE,
    Beam.StatusChoices.LOADED,
    Beam.StatusChoices.IN_PRODUCTION,
    Beam.StatusChoices.AVAILABLE,
    Beam.StatusChoices.SIZING
]

created_beams = []
for i in range(1, 31):
    beam_num = f"BM-{i:03d}"
    cnt = counts[(i - 1) % len(counts)]
    w = widths[(i - 1) % len(widths)]
    l = lengths[(i - 1) % len(lengths)]
    wt = weights[(i - 1) % len(weights)]
    e = ends[(i - 1) % len(ends)]
    st = statuses[(i - 1) % len(statuses)]
    po = f"PO-2026-{(i % 8) + 1:03d}"
    
    beam_data = {
        "beam_name": f"Beam {cnt} Cotton - Flange #{i:02d}",
        "beam_number": beam_num,
        "yarn_count": cnt,
        "warp_count": e,
        "total_ends": e,
        "length": l,
        "width": w,
        "weight": wt,
        "production_order": po,
        "status": st,
        "notes": f"Standard Weaver Beam. Flange diameter 800mm, barrel 220mm, weight tare 85kg.",
        "created_by": superuser
    }
    
    beam, _ = Beam.objects.get_or_create(
        beam_number=beam_num,
        defaults=beam_data
    )
    created_beams.append(beam)

print(f"Successfully processed {len(created_beams)} Beams.")

# Summary Verification
print("=== Database Seed Summary ===")
print(f"Total Suppliers in DB: {Supplier.objects.count()}")
print(f"Total Customers in DB: {Customer.objects.count()}")
print(f"Total Sizing units in DB: {Sizing.objects.count()}")
print(f"Total Looms in DB: {Loom.objects.count()}")
print(f"Total Beams in DB: {Beam.objects.count()}")
