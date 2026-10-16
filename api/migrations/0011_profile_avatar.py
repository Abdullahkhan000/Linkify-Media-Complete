from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0010_remove_auditlog_user_delete_billingevent_and_more')]
    operations = [
        migrations.AddField(
            model_name='profile', name='avatar_url',
            field=models.URLField(max_length=500, blank=True, default=''),
        ),
        migrations.AddField(
            model_name='profile', name='avatar_public_id',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
    ]
