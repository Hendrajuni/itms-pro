import platform
import subprocess
from django.core.management.base import BaseCommand
from django.utils import timezone
from network.models import NetworkNode, DowntimeEvent

class Command(BaseCommand):
    help = 'Pings all network nodes and updates their status'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Network Ping...")
        
        # Determine Ping Parameters based on OS
        sys_os = platform.system().lower()
        param_count = '-n' if sys_os == 'windows' else '-c'
        param_wait = '-w' if sys_os == 'windows' else '-W'
        wait_value = '1000' if sys_os == 'windows' else '1' # 1000ms or 1s

        # Fetch Nodes (Exclude Maintenance/Null IP)
        nodes = NetworkNode.objects.filter(
            ip_address__isnull=False
        ).exclude(status='Maintenance').exclude(ip_address='')

        count_online = 0
        count_offline = 0

        for node in nodes:
            # Construct Command
            cmd = ['ping', param_count, '1', param_wait, wait_value, node.ip_address]
            
            try:
                # Run Ping (Hide Output)
                # subprocess.call returns 0 on Success (Active), non-zero on Failure (Offline)
                is_up = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
                
                now = timezone.now()
                
                if is_up:
                    if node.status == 'Offline':
                        self.stdout.write(self.style.SUCCESS(f"[RECOVERY] {node.name} ({node.ip_address}) is now ONLINE"))
                        
                        # Auto-close open incidents
                        open_incidents = DowntimeEvent.objects.filter(node=node, is_resolved=False)
                        for inc in open_incidents:
                            inc.end_time = now
                            inc.resolution = "Auto-resolved by Ping Monitor"
                            inc.save()
                            
                    node.status = 'Online'
                    count_online += 1
                else:
                    if node.status == 'Online' or node.status == 'Unknown':
                        self.stdout.write(self.style.ERROR(f"[DOWN] {node.name} ({node.ip_address}) is OFFLINE"))
                        
                        # Auto-create incident if none exists
                        if not DowntimeEvent.objects.filter(node=node, is_resolved=False).exists():
                            DowntimeEvent.objects.create(
                                node=node,
                                title=f"Auto-Detected: {node.name} Unreachable",
                                start_time=now,
                                impact='High' if node.type in ['Router', 'Firewall', 'Server'] else 'Medium',
                                root_cause='Other',
                                description=f"System failed to ping {node.ip_address}. Status changed to Offline."
                            )
                    
                    node.status = 'Offline'
                    count_offline += 1
                
                node.last_checked = now
                node.save(update_fields=['status', 'last_checked'])
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error pinging {node.name}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"Ping Completed. Online: {count_online}, Offline: {count_offline}"))
