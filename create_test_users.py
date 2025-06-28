"""
Script to create test users for different roles
Run this after migrations to have users to test with
"""

import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'omnichannel_core.settings.dev')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from agent_hub.models import AgentProfile

User = get_user_model()

def create_test_users():
    """Create test users with different roles"""
    print("Creating test users with different roles...")
    
    # Create or get groups
    agent_group, _ = Group.objects.get_or_create(name='Agent')
    supervisor_group, _ = Group.objects.get_or_create(name='Supervisor')
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    
    # Create admin user
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@example.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'is_staff': True,
        }
    )
    
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        admin_profile, _ = AgentProfile.objects.get_or_create(
            user=admin_user,
            defaults={'status': 'available'}
        )
        admin_group.user_set.add(admin_user)
        print("Created admin user: admin / admin123")
    else:
        print("Admin user already exists")
    
    # Create supervisor user
    supervisor_user, created = User.objects.get_or_create(
        username='supervisor',
        defaults={
            'email': 'supervisor@example.com',
            'first_name': 'Super',
            'last_name': 'Visor',
        }
    )
    
    if created:
        supervisor_user.set_password('super123')
        supervisor_user.save()
        supervisor_profile, _ = AgentProfile.objects.get_or_create(
            user=supervisor_user,
            defaults={'status': 'available'}
        )
        supervisor_group.user_set.add(supervisor_user)
        print("Created supervisor user: supervisor / super123")
    else:
        print("Supervisor user already exists")
    
    # Create agent user
    agent_user, created = User.objects.get_or_create(
        username='agent',
        defaults={
            'email': 'agent@example.com',
            'first_name': 'Test',
            'last_name': 'Agent',
        }
    )
    
    if created:
        agent_user.set_password('agent123')
        agent_user.save()
        agent_profile, _ = AgentProfile.objects.get_or_create(
            user=agent_user,
            defaults={'status': 'available'}
        )
        agent_group.user_set.add(agent_user)
        print("Created agent user: agent / agent123")
    else:
        print("Agent user already exists")
    
    print("Test users created successfully!")

if __name__ == "__main__":
    create_test_users()
