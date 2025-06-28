from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('agent_hub', '0001_initial'),
    ]

    operations = [
        # Conversation indexes for faster lookups and filtering
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(fields=['status', '-last_message_at'], name='conv_status_time_idx'),
        ),
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(fields=['assigned_agent', 'status'], name='agent_status_idx'),
        ),
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(fields=['customer', '-created_at'], name='customer_time_idx'),
        ),
        migrations.AddIndex(
            model_name='conversation',
            index=models.Index(fields=['channel', 'status'], name='channel_status_idx'),
        ),
        
        # Message indexes for faster conversation history loading
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['conversation', '-sent_at'], name='msg_conv_time_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['direction', 'read_at'], name='msg_dir_read_idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['channel_message_id'], name='msg_channel_id_idx'),
        ),
        
        # Quick reply template indexes
        migrations.AddIndex(
            model_name='quickreplytemplate',
            index=models.Index(fields=['agent', 'shortcut'], name='quick_reply_shortcut_idx'),
        ),
        
        # Agent performance snapshot indexes
        migrations.AddIndex(
            model_name='agentperformancesnapshot',
            index=models.Index(fields=['agent', '-period_end'], name='agent_perf_time_idx'),
        ),
    ]
