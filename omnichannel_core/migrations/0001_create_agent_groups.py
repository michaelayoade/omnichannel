from django.db import migrations

def create_groups(apps, schema_editor):
    """
    Create default Agent, Supervisor, and Admin groups
    """
    Group = apps.get_model('auth', 'Group')
    
    # Create groups if they don't exist
    for group_name in ['Agent', 'Supervisor', 'Admin']:
        Group.objects.get_or_create(name=group_name)
    
class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_groups),
    ]
