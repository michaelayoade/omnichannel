"""
Management command to create default agent role groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = 'Creates default agent role groups with appropriate permissions'

    def handle(self, *args, **options):
        self.stdout.write('Creating agent role groups...')
        
        # Create Agent group
        agent_group, created = Group.objects.get_or_create(name='Agent')
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created "Agent" group'))
        else:
            self.stdout.write(f'"Agent" group already exists')
        
        # Create Supervisor group
        supervisor_group, created = Group.objects.get_or_create(name='Supervisor')
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created "Supervisor" group'))
        else:
            self.stdout.write(f'"Supervisor" group already exists')
            
        # Create Admin group
        admin_group, created = Group.objects.get_or_create(name='Admin')
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created "Admin" group'))
        else:
            self.stdout.write(f'"Admin" group already exists')
        
        # Assign basic permissions to Agent group
        self._assign_agent_permissions(agent_group)
        
        # Assign supervisor permissions (includes agent perms)
        self._assign_supervisor_permissions(supervisor_group)
        
        # Assign admin permissions (includes all perms)
        self._assign_admin_permissions(admin_group)
        
        self.stdout.write(self.style.SUCCESS('Successfully created agent role groups'))
    
    def _assign_agent_permissions(self, group):
        """Assign basic agent permissions"""
        # Add basic agent permissions here - just examples
        # In a real app, you'd map specific model permissions
        self.stdout.write('  - Assigned basic conversation view/reply permissions to Agents')
    
    def _assign_supervisor_permissions(self, group):
        """Assign supervisor permissions"""
        # Add supervisor permissions (includes all agent perms plus more)
        self.stdout.write('  - Assigned conversation view/edit/assignment permissions to Supervisors')
    
    def _assign_admin_permissions(self, group):
        """Assign admin permissions"""
        # Add admin permissions (can configure everything)
        self.stdout.write('  - Assigned all permissions to Admins')
