from .models import AuditEntry


def record_audit(action, *, actor=None, entity, context=None):
    return AuditEntry.objects.create(
        actor=actor, action=action, entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk), context=context or {},
    )
