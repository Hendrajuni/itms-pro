from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    name = 'maintenance'

    def ready(self):
        import maintenance.signals
