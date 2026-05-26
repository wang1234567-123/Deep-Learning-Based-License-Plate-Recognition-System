from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='LprDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('root_folder_path', models.TextField()),
                ('train_folder_path', models.TextField()),
                ('test_folder_path', models.TextField()),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='PlateRecognitionRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('detection_record_id', models.BigIntegerField(db_index=True)),
                ('user_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('user_name', models.CharField(blank=True, default='', max_length=150)),
                ('plate_number', models.CharField(blank=True, default='', max_length=32)),
                ('plate_confidence', models.FloatField(blank=True, null=True)),
                ('bbox', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'indexes': [
                    models.Index(fields=['detection_record_id', 'created_at'], name='hertz_stud_detection_9325b1_idx'),
                    models.Index(fields=['user_id', 'created_at'], name='hertz_stud_user_id_3b8d70_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='LprTrainingJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('queued', 'queued'),
                            ('running', 'running'),
                            ('canceling', 'canceling'),
                            ('completed', 'completed'),
                            ('failed', 'failed'),
                            ('canceled', 'canceled'),
                        ],
                        default='queued',
                        max_length=16,
                    ),
                ),
                ('max_epoch', models.IntegerField(default=15)),
                ('train_batch_size', models.IntegerField(default=128)),
                ('test_batch_size', models.IntegerField(default=120)),
                ('learning_rate', models.FloatField(default=0.1)),
                ('dropout_rate', models.FloatField(default=0.5)),
                ('device', models.CharField(default='cuda:0', max_length=32)),
                ('use_cuda', models.BooleanField(default=True)),
                ('pretrained_model_path', models.TextField(blank=True, default='')),
                ('save_folder', models.TextField(blank=True, default='')),
                ('logs_path', models.TextField(blank=True, default='')),
                ('output_model_path', models.TextField(blank=True, default='')),
                ('pid', models.IntegerField(blank=True, null=True)),
                ('progress', models.FloatField(default=0.0)),
                ('last_metrics', models.JSONField(blank=True, default=dict)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                (
                    'dataset',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='hertz_studio_django_lpr.lprdataset'),
                ),
            ],
        ),
    ]

