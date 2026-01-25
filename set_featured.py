import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from assets.models import InfrastructureType

# The requested 4
FEATURED = ['Tower Nodes', 'Server Racks', 'Wallmount Racks', 'Box Panels']

def run():
    print("Updating InfrastructureType visibility...")
    
    # Reset all to False
    InfrastructureType.objects.all().update(is_featured=False)
    
    # Set requested to True
    updated = InfrastructureType.objects.filter(name__in=FEATURED).update(is_featured=True)
    
    print(f"Set {updated} types to Featured.")
    print("Done.")

if __name__ == '__main__':
    run()
