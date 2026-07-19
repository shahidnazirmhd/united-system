# Importing the Celery app here ensures it is loaded when Django starts,
# so that `@shared_task` decorators registered anywhere in the project
# work without each module needing to import celery.py itself.
from config.celery import app as celery_app

__all__ = ["celery_app"]
