# core/migrations/000X_remove_old_auditlog_perms.py
from django.db import migrations

def remove_unwanted_permissions(apps, schema_editor):
    Permission   = apps.get_model('auth', 'Permission')
    ContentType  = apps.get_model('contenttypes', 'ContentType')

    try:
        ct = ContentType.objects.get(app_label='core', model='auditlog')
    except ContentType.DoesNotExist:
        return

    # delete everything except the view_ permission
    Permission.objects.filter(content_type=ct) \
                      .exclude(codename__startswith='view_') \
                      .delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0032_alter_auditlog_options'),
    ]

    operations = [
        migrations.RunPython(remove_unwanted_permissions),
    ]
