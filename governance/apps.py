from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    name = 'governance'

    def ready(self):
        import governance.signals
