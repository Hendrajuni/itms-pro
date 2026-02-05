from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Deletes all business data (Assets, Tickets, etc) but preserves Users and Settings for safe testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting safe data reset...")

        # List of models to clear (Order matters for ForeignKeys if not using CASCADE, but Django handles cascade usually)
        # We delete "Leaf" nodes first usually, but CASCADE handles parents.
        # We want to clear MAIN business entities.
        
        models_to_clear = [
            'assets.Asset',
            'assets.Software',
            'assets.License',
            'assets.Contract',
            'assets.Vendor',
            'assets.Location', # Recursive
            'assets.Department',
            'assets.Category', 
            
            'tickets.Ticket',
            'tickets.TicketComment',
            
            'maintenance.AssetMaintenance',
            'maintenance.InfraMaintenance',
            'maintenance.MaintenanceSchedule',
            
            'governance.DailyLog',
            'governance.Project',
            
            'notifications.Notification',
        ]

        for model_path in models_to_clear:
            try:
                app_label, model_name = model_path.split('.')
                Model = apps.get_model(app_label, model_name)
                count = Model.objects.count()
                if count > 0:
                    # Use _raw_delete or standard delete. Standard is safer for signals.
                    Model.objects.all().delete()
                    self.stdout.write(self.style.WARNING(f"Deleted {count} records from {model_name}"))
                else:
                    self.stdout.write(f"No records in {model_name}")
            except LookupError:
                self.stdout.write(self.style.ERROR(f"Model {model_path} not found. Skipping."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error clearing {model_path}: {e}"))

        self.stdout.write(self.style.SUCCESS("Business data reset complete. Users and Site Settings preserved."))
