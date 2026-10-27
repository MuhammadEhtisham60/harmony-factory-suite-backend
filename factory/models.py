"""
Aggregated models for the factory app.
Imports all models from subpackages so Django core commands (e.g. dumpdata) recognize them.
"""

from factory.purchase.supplier.models import Supplier, SupplierBankAccount
from factory.sales.customer.models import Customer, CustomerBankAccount
from factory.loom.models import Loom
from factory.beam.models import Beam, BeamLoading, Production, BeamDismountReconciliation
from factory.yarn.yarn_buyer.models import YarnBuyer
from factory.yarn.yarn_name.models import YarnName
from factory.yarn.yarn_type.models import YarnType
from factory.yarn.yarn_count.models import YarnCount
from factory.yarn.yarn_stock.models import YarnStock
from factory.yarn.yarn_intake.models import YarnIntake, YarnOutcome, YarnOutcomeItem, YarnOutcomeBGradeItem
from factory.yarn.sizing.models import Sizing, SizingOutcome, SizingBeamAssignment
from factory.yarn.warping.models import Warping
from factory.yarn.b_grade_yarn.models import BGradeYarn
from factory.cloth.models import ClothName, ClothPatch, ClothStock, CleanClothStock, DefectedClothStock
from factory.bank_account.models import BankAccount, BankTransaction
