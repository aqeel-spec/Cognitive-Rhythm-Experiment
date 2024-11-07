from django.apps import AppConfig


class ExperimentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "experiment"
    
    def ready(self):
        import experiment.signals  # Ensure signals are imported

