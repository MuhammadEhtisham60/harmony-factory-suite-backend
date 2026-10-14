
import os
import re

files_to_update = [
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\RawMaterialFormModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\RawMaterialFormPage.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\SizingOutcomeFormModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\YarnOutcomeModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\beam\components\BeamModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\loom\components\LoomModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\BeamLoadingModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\ProductionLogModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\BeamFormModal.jsx",
    r"e:\loom\harmony-factory-suite\src\container\production\raw-manufacturing\form\SizingFormModal.jsx",
]

pattern = re.compile(r'step=["\'](?:0\.01|0\.0001|0\.001|0\.1)["\']')

for filepath in files_to_update:
    if not os.path.exists(filepath):
        print(f"Skipping not found: {filepath}")
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    new_content, count = pattern.subn('step="any"', content)
    if count > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {count} step instances in {filepath}")
    else:
        print(f"No step pattern match in {filepath}")
