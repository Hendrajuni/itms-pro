
import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from maintenance.models import AssetMaintenance, InfraMaintenance

print("--- DEBUGGING MAINTENANCE WIDGET LOGIC ---")

# 1. Check Date Range
start_date = timezone.localdate()
end_date = start_date + timedelta(days=7)

print(f"Current Local Date: {start_date}")
print(f"End Date (Next 7 Days): {end_date}")
print(f"Range: [{start_date} TO {end_date}]")

# 2. Check Asset Maintenance
print("\n--- ASSET MAINTENANCE ---")
asset_maint_query = AssetMaintenance.objects.filter(
    scheduled_date__range=[start_date, end_date], 
    status='Scheduled'
)
print(f"Query Count: {asset_maint_query.count()}")
for m in asset_maint_query:
    print(f" - [{m.scheduled_date}] {m.title} (Status: {m.status})")

# Check potential near-misses (e.g. wrong status or just outside date)
print("\n--- NEAR MISSES (Asset) ---")
near_misses = AssetMaintenance.objects.filter(
    scheduled_date__range=[start_date - timedelta(days=2), end_date + timedelta(days=2)]
).exclude(id__in=asset_maint_query.values_list('id', flat=True))

for m in near_misses:
    print(f" - [{m.scheduled_date}] {m.title} (Status: {m.status})")


# 3. Check Infra Maintenance
print("\n--- INFRA MAINTENANCE ---")
infra_maint_query = InfraMaintenance.objects.filter(
    scheduled_date__range=[start_date, end_date], 
    status='Scheduled'
)
print(f"Query Count: {infra_maint_query.count()}")
for m in infra_maint_query:
    print(f" - [{m.scheduled_date}] {m.title} (Status: {m.status})")

# 4. Create Dummy Maintenance for Verification
print("\n--- CREATE DUMMY MAINTENANCE ---")
from assets.models import Asset
from django.contrib.auth import get_user_model

try:
    # Get prerequisites
    user = get_user_model().objects.first()
    asset = Asset.objects.first()
    
    if user and asset:
        dummy_date = start_date + timedelta(days=2)
        print(f"Creating dummy task for {dummy_date}...")
        
        dummy = AssetMaintenance.objects.create(
            asset=asset,
            technician=user,
            title="DUMMY TEST MAINTENANCE",
            maintenance_type="Preventive",
            scheduled_date=dummy_date,
            status="Scheduled",
            priority="Medium"
        )
        print(f"Created: {dummy.title} (ID: {dummy.id})")
        
        # Query again
        count = AssetMaintenance.objects.filter(scheduled_date__range=[start_date, end_date]).count()
        print(f"Re-Query Count (Should be >= 1): {count}")
        
        # Cleanup
        print("Deleting dummy task...")
        dummy.delete()
        print("Deleted.")
    else:
        print("Skipping dummy creation: No User or Asset found.")

except Exception as e:
    print(f"Error creating dummy: {e}")

# 4. Create Dummy Maintenance for Verification
print("\n--- CREATE DUMMY MAINTENANCE ---")
from assets.models import Asset
from django.contrib.auth import get_user_model

try:
    # Get prerequisites
    user = get_user_model().objects.first()
    asset = Asset.objects.first()
    
    if user and asset:
        dummy_date = start_date + timedelta(days=2)
        print(f"Creating dummy task for {dummy_date}...")
        
        dummy = AssetMaintenance.objects.create(
            asset=asset,
            technician=user,
            title="DUMMY TEST MAINTENANCE",
            maintenance_type="Preventive",
            scheduled_date=dummy_date,
            status="Scheduled",
            priority="Medium"
        )
        print(f"Created: {dummy.title} (ID: {dummy.id})")
        
        # Query again
        count = AssetMaintenance.objects.filter(scheduled_date__range=[start_date, end_date]).count()
        print(f"Re-Query Count (Should be >= 1): {count}")
        
        # Cleanup
        print("Deleting dummy task...")
        dummy.delete()
        print("Deleted.")
    else:
        print("Skipping dummy creation: No User or Asset found.")

except Exception as e:
    print(f"Error creating dummy: {e}")

# 4. Create Dummy Maintenance for Verification
print("\n--- CREATE DUMMY MAINTENANCE ---")
from assets.models import Asset
from django.contrib.auth import get_user_model

try:
    # Get prerequisites
    user = get_user_model().objects.first()
    asset = Asset.objects.first()
    
    if user and asset:
        dummy_date = start_date + timedelta(days=2)
        print(f"Creating dummy task for {dummy_date}...")
        
        dummy = AssetMaintenance.objects.create(
            asset=asset,
            technician=user,
            title="DUMMY TEST MAINTENANCE",
            maintenance_type="Preventive",
            scheduled_date=dummy_date,
            status="Scheduled",
            priority="Medium"
        )
        print(f"Created: {dummy.title} (ID: {dummy.id})")
        
        # Query again
        count = AssetMaintenance.objects.filter(scheduled_date__range=[start_date, end_date]).count()
        print(f"Re-Query Count (Should be >= 1): {count}")
        
        # Cleanup
        print("Deleting dummy task...")
        dummy.delete()
        print("Deleted.")
    else:
        print("Skipping dummy creation: No User or Asset found.")

except Exception as e:
    print(f"Error creating dummy: {e}")
