from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sla", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="slaescalationlevel",
            name="legacy_recipient_role",
            field=models.CharField(blank=True, editable=False, max_length=32),
        ),
    ]
