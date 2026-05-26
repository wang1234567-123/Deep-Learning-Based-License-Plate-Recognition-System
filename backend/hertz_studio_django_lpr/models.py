from django.db import models


class LprDataset(models.Model):
    name = models.CharField(max_length=128)
    root_folder_path = models.TextField()
    train_folder_path = models.TextField()
    test_folder_path = models.TextField()
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class LprTrainingJob(models.Model):
    STATUS_CHOICES = [
        ('queued', 'queued'),
        ('running', 'running'),
        ('canceling', 'canceling'),
        ('completed', 'completed'),
        ('failed', 'failed'),
        ('canceled', 'canceled'),
    ]

    dataset = models.ForeignKey(LprDataset, on_delete=models.CASCADE, related_name='jobs')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='queued')

    max_epoch = models.IntegerField(default=15)
    train_batch_size = models.IntegerField(default=128)
    test_batch_size = models.IntegerField(default=120)
    learning_rate = models.FloatField(default=0.1)
    dropout_rate = models.FloatField(default=0.5)
    device = models.CharField(max_length=32, default='cuda:0')
    use_cuda = models.BooleanField(default=True)
    pretrained_model_path = models.TextField(blank=True, default='')

    save_folder = models.TextField(blank=True, default='')
    logs_path = models.TextField(blank=True, default='')
    output_model_path = models.TextField(blank=True, default='')
    pid = models.IntegerField(null=True, blank=True)
    progress = models.FloatField(default=0.0)
    last_metrics = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f'LprTrainingJob#{self.pk}'


class PlateRecognitionRecord(models.Model):
    detection_record_id = models.BigIntegerField(db_index=True)
    user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    user_name = models.CharField(max_length=150, blank=True, default='')
    plate_number = models.CharField(max_length=32, blank=True, default='')
    plate_confidence = models.FloatField(null=True, blank=True)
    bbox = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['detection_record_id', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
        ]

    def __str__(self) -> str:
        return self.plate_number or f'PlateRecognitionRecord#{self.pk}'

