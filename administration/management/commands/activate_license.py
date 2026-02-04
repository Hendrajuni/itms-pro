from django.core.management.base import BaseCommand, CommandError
from core.models import SiteSetting
from core.license import LICENSE_ENTERPRISE, LICENSE_ESSENTIAL

class Command(BaseCommand):
    help = 'Activates the ITMS Edition (Essential/Enterprise)'

    def add_arguments(self, parser):
        parser.add_argument('key', type=str, help='The License Hash Key')

    def handle(self, *args, **options):
        key = options['key']
        
        setting = SiteSetting.get_solo()
        
        if key == LICENSE_ENTERPRISE:
            setting.activation_code = key
            setting.save()
            self.stdout.write(self.style.SUCCESS('Successfully activated ENTERPRISE Edition! 🚀'))
            self.stdout.write(self.style.SUCCESS('Please restart the server or refresh browser.'))
        
        elif key == LICENSE_ESSENTIAL:
            setting.activation_code = key
            setting.save()
            self.stdout.write(self.style.SUCCESS('Reverted to ESSENTIAL Edition.'))
            
        else:
             self.stdout.write(self.style.ERROR('Invalid License Key.'))
             # Optional: Allow custom keys if you implement new logic later
             # setting.activation_code = key
             # setting.save()
