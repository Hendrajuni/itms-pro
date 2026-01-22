from django.core.management.base import BaseCommand
from django.utils import timezone
from network.models import NetworkNode
from network.utils import check_ping

class Command(BaseCommand):
    help = 'Scans all NetworkNodes with an IP address using Ping'

    def handle(self, *args, **kwargs):
        nodes = NetworkNode.objects.filter(ip_address__isnull=False).exclude(ip_address='')
        total = nodes.count()
        online_count = 0
        offline_count = 0

        self.stdout.write(f"Starting Ping Scan for {total} nodes...")

        for node in nodes:
            is_online = check_ping(node.ip_address)
            
            if is_online:
                node.status = 'Online'
                online_count += 1
            else:
                node.status = 'Offline'
                offline_count += 1
            
            node.last_checked = timezone.now()
            node.save(update_fields=['status', 'last_checked'])
            
            status_str = "ONLINE" if is_online else "OFFLINE"
            self.stdout.write(f"  [{status_str}] {node.name} ({node.ip_address})")

        self.stdout.write(self.style.SUCCESS(f"\nScan Completed. Online: {online_count}, Offline: {offline_count}"))
