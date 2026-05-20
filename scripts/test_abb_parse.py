"""Quick test: parse ACS880 PDF and show names for truncated params."""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from scripts.audit_pdf import parse_abb
from pathlib import Path

pdf_path = Path('manuals/ACS880_Primary_Firmware_Manual.pdf')
if not pdf_path.exists():
    print("PDF not found:", pdf_path)
    sys.exit(1)

print("Parsing ACS880 PDF (first 300 params)...")
params = parse_abb(pdf_path)
print(f"Total params found: {len(params)}")

# Check the truncated params
truncated_codes = [
    '14.19', '14.20', '15.20', '16.20', '19.20',
    '21.12', '22.14', '22.51', '22.71', '22.72',
]
print("\nNames for previously truncated params:")
for code in truncated_codes:
    p = params.get(code)
    if p:
        print(f"  {code}: [{p['name']}]")
    else:
        print(f"  {code}: NOT FOUND")

# Count remaining with '-' at end
still_truncated = [(c, p['name']) for c, p in params.items() if p['name'].endswith('-')]
print(f"\nStill truncated (ends with '-'): {len(still_truncated)}")
for c, n in still_truncated[:10]:
    print(f"  {c}: [{n}]")

# Check hyphenation in descriptions
hyph_count = sum(1 for p in params.values() if re.search(r'\w+- +[a-z]', p.get('description', '')))
print(f"\nDescriptions with hyphenation artifacts: {hyph_count}")
