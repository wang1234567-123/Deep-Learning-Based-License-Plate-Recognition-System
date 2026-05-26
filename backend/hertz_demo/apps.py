from django.apps import AppConfig


class DemoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hertz_demo'

    def ready(self):
        try:
            from django.db.utils import OperationalError, ProgrammingError
            from hertz_studio_django_log.models import OperationLog
        except Exception:
            return

        original_create_log = getattr(OperationLog, 'create_log', None)
        if not callable(original_create_log):
            return

        def safe_create_log(*args, **kwargs):
            try:
                return original_create_log(*args, **kwargs)
            except (OperationalError, ProgrammingError):
                return None
            except Exception:
                return None

        OperationLog.create_log = staticmethod(safe_create_log)
