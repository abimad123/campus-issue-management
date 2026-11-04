from django.db import migrations, models


def copy_queue_priority_to_routing_priority(apps, schema_editor):
    Issue = apps.get_model("issues", "Issue")
    Issue.objects.filter(routing_priority__isnull=True).update(routing_priority=models.F("priority"))


class Migration(migrations.Migration):
    dependencies = [("issues", "0007_issue_priority_request_reason_and_more")]

    operations = [
        migrations.AddField(
            model_name="issue",
            name="routing_priority",
            field=models.CharField(blank=True, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("CRITICAL", "Critical")], editable=False, max_length=8, null=True),
        ),
        migrations.RunPython(copy_queue_priority_to_routing_priority, migrations.RunPython.noop),
    ]
