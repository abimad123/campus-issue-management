from celery import shared_task

@shared_task
def debug_task():
    """Infrastructure smoke task; no domain side effects."""
    return "Celery is connected."
