from django.core.management.base import BaseCommand
from tickets.models import TicketTopic

class Command(BaseCommand):
    help = 'Initialize common ticket topics (Master Data)'

    def handle(self, *args, **kwargs):
        topics_data = {
            'Hardware': [
                ("PC Won't Turn On", 'High'),
                ("Monitor Black/No Signal", 'Medium'),
                ("Blue Screen (BSOD)", 'High'),
                ("Keyboard/Mouse Not Working", 'Medium'),
                ("PC Overheating/Noisy", 'Medium'),
            ],
            'Hardware': [ # Printer/Scanner - User categorized as 'Printer/Scanner' but category choices are likely 'Hardware' or 'Other'. Actually the choices in models.py don't have 'Printer'. Let's map to 'Hardware' or closest found.
                # Categories: Hardware, Software, Network, Access_Request, Daily_Check_Fail, Other.
                # User's suggested list groups by "Printer/Scanner". I'll put them in Hardware.
                ("Printer Won't Print", 'Medium'),
                ("Paper Jam", 'Medium'),
                ("Poor Print Quality", 'Low'),
                ("Toner/Ink Empty", 'Low'),
                ("Scanner Not Detected", 'Medium'),
            ],
            'Network': [
                ("Cannot Connect to WiFi", 'High'),
                ("Intermittent Internet", 'Medium'),
                ("Slow Internet", 'Medium'),
                ("Cannot Access Server/Shared Folder", 'High'),
            ],
            'Software': [ # Application
                ("App Not Opening", 'High'),
                ("App Not Responding/Crash", 'Medium'),
                ("Microsoft Office Error", 'Medium'),
                ("Browser Issue", 'Low'),
            ],
            'Access_Request': [ # Account
                ("Forgot PC Password", 'High'),
                ("Forgot Email Password", 'High'),
                ("Account Locked", 'Critical'),
            ],
            'Other': [ # Service
                ("Request New App Installation", 'Medium'),
                ("Request New Hardware", 'Medium'),
                ("Zoom/Meeting Setup Help", 'Low'),
            ]
        }
        
        # Merge lists if key duplicated above? Python dict keys overwrite.
        # I should have merged the Hardware list manually.
        
        # Proper list construction
        data = [
            # Hardware
            ("PC Won't Turn On", 'Hardware', 'High'),
            ("Monitor Black/No Signal", 'Hardware', 'Medium'),
            ("Blue Screen (BSOD)", 'Hardware', 'High'),
            ("Keyboard/Mouse Not Working", 'Hardware', 'Medium'),
            ("PC Overheating/Noisy", 'Hardware', 'Medium'),
            # Printer (Mapping to Hardware as per standard choices)
            ("Printer Won't Print", 'Hardware', 'Medium'),
            ("Paper Jam", 'Hardware', 'Medium'),
            ("Poor Print Quality", 'Hardware', 'Low'),
            ("Toner/Ink Empty", 'Hardware', 'Low'),
            ("Scanner Not Detected", 'Hardware', 'Medium'),
            # Network
            ("Cannot Connect to WiFi", 'Network', 'High'),
            ("Intermittent Internet", 'Network', 'Medium'),
            ("Slow Internet", 'Network', 'Medium'),
            ("Cannot Access Server/Shared Folder", 'Network', 'High'),
            # Software
            ("App Not Opening", 'Software', 'High'),
            ("App Not Responding/Crash", 'Software', 'Medium'),
            ("Microsoft Office Error", 'Software', 'Medium'),
            ("Browser Issue", 'Software', 'Low'),
            # Access/Account
            ("Forgot PC Password", 'Access_Request', 'High'),
            ("Forgot Email Password", 'Access_Request', 'High'),
            ("Account Locked", 'Access_Request', 'Critical'),
            # Service -> Other
            ("Request New App Installation", 'Other', 'Medium'),
            ("Request New Hardware", 'Other', 'Medium'),
            ("Zoom/Meeting Setup Help", 'Other', 'Low'),
        ]

        count = 0
        for name, category, priority in data:
            topic, created = TicketTopic.objects.get_or_create(
                name=name,
                defaults={'category': category, 'priority': priority}
            )
            if created:
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Created topic: {name}'))
            else:
                self.stdout.write(f'Topic exists: {name}')

        self.stdout.write(self.style.SUCCESS(f'Successfully initialized {count} new topics.'))
