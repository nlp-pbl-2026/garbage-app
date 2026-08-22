"""Verify translation models can be imported successfully."""
import sys
sys.path.insert(0, r"c:\dev\garbage-app\backend")

from app.models import GarbageItemTranslation, BulkyWasteItemTranslation, MunicipalityRomanization

print("All translation models imported successfully!")
print(f"  GarbageItemTranslation table: {GarbageItemTranslation.__tablename__}")
print(f"  BulkyWasteItemTranslation table: {BulkyWasteItemTranslation.__tablename__}")
print(f"  MunicipalityRomanization table: {MunicipalityRomanization.__tablename__}")

# Verify table args (constraints)
git_args = GarbageItemTranslation.__table_args__
print(f"\nGarbageItemTranslation constraints:")
for arg in git_args:
    print(f"  {arg}")

bwit_args = BulkyWasteItemTranslation.__table_args__
print(f"\nBulkyWasteItemTranslation constraints:")
for arg in bwit_args:
    print(f"  {arg}")

# Verify columns
git_cols = [c.name for c in GarbageItemTranslation.__table__.columns]
print(f"\nGarbageItemTranslation columns: {git_cols}")

bwit_cols = [c.name for c in BulkyWasteItemTranslation.__table__.columns]
print(f"\nBulkyWasteItemTranslation columns: {bwit_cols}")

mr_cols = [c.name for c in MunicipalityRomanization.__table__.columns]
print(f"\nMunicipalityRomanization columns: {mr_cols}")

print("\nAll verifications passed!")
