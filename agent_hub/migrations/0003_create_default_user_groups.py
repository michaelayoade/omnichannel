from django.db import migrations
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def create_default_groups(apps, schema_editor):
    """
    Create default user role groups with appropriate permissions
    """
    # Create groups
    agent_group, _ = Group.objects.get_or_create(name='Agent')
    supervisor_group, _ = Group.objects.get_or_create(name='Supervisor')
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    
    # Get content types for our models
    agent_profile_ct = ContentType.objects.get(app_label='agent_hub', model='agentprofile')
    conversation_ct = ContentType.objects.get(app_label='agent_hub', model='conversation')
    message_ct = ContentType.objects.get(app_label='agent_hub', model='message')
    quickreply_ct = ContentType.objects.get(app_label='agent_hub', model='quickreplytemplate')
    performance_ct = ContentType.objects.get(app_label='agent_hub', model='agentperformancesnapshot')
    
    # Agent permissions (can view and manage their own conversations and messages)
    agent_permissions = [
        Permission.objects.get(codename='view_conversation', content_type=conversation_ct),
        Permission.objects.get(codename='change_conversation', content_type=conversation_ct),
        Permission.objects.get(codename='view_message', content_type=message_ct),
        Permission.objects.get(codename='add_message', content_type=message_ct),
        Permission.objects.get(codename='view_agentprofile', content_type=agent_profile_ct),
        Permission.objects.get(codename='change_agentprofile', content_type=agent_profile_ct),
        Permission.objects.get(codename='view_quickreplytemplate', content_type=quickreply_ct),
        Permission.objects.get(codename='add_quickreplytemplate', content_type=quickreply_ct),
        Permission.objects.get(codename='change_quickreplytemplate', content_type=quickreply_ct),
        Permission.objects.get(codename='delete_quickreplytemplate', content_type=quickreply_ct),
    ]
    agent_group.permissions.set(agent_permissions)
    
    # Supervisor permissions (can manage agents, view performance, reassign conversations)
    supervisor_permissions = agent_permissions + [
        # Inherit all agent permissions plus:
        Permission.objects.get(codename='add_conversation', content_type=conversation_ct),
        Permission.objects.get(codename='delete_conversation', content_type=conversation_ct),
        Permission.objects.get(codename='change_message', content_type=message_ct),
        Permission.objects.get(codename='delete_message', content_type=message_ct),
        Permission.objects.get(codename='view_agentperformancesnapshot', content_type=performance_ct),
        # Can see all agent profiles but not create/delete them
        Permission.objects.get(codename='view_agentprofile', content_type=agent_profile_ct),
        Permission.objects.get(codename='change_agentprofile', content_type=agent_profile_ct),
    ]
    supervisor_group.permissions.set(supervisor_permissions)
    
    # Admin gets all permissions
    admin_permissions = supervisor_permissions + [
        # All remaining permissions
        Permission.objects.get(codename='add_agentprofile', content_type=agent_profile_ct),
        Permission.objects.get(codename='delete_agentprofile', content_type=agent_profile_ct),
        Permission.objects.get(codename='add_agentperformancesnapshot', content_type=performance_ct),
        Permission.objects.get(codename='change_agentperformancesnapshot', content_type=performance_ct),
        Permission.objects.get(codename='delete_agentperformancesnapshot', content_type=performance_ct),
    ]
    admin_group.permissions.set(admin_permissions)


def remove_default_groups(apps, schema_editor):
    """
    Remove default groups (reverse migration)
    """
    Group.objects.filter(name__in=['Agent', 'Supervisor', 'Admin']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('agent_hub', '0002_add_performance_indexes'),
    ]

    operations = [
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
