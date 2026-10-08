from celery import shared_task


@shared_task(name="apps.sla.tasks.process_sla_sweep")
def process_sla_sweep():
    from .services import process_sla_sweep as sweep
    return sweep()
