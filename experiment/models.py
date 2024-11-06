from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField 

class Participant(models.Model):
    age = models.IntegerField()
    is_right_handed = models.BooleanField(default=True)
    has_music_background = models.BooleanField(default=False)
    email = models.EmailField(blank=True, null=True)
    agreed_to_terms = models.BooleanField()

    def __str__(self):
        return f"Participant {self.id}"

class ExperimentSession(models.Model):
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(blank=True, null=True)
    complexity_level = models.CharField(max_length=50, choices=[('simple', 'Simple'), ('complex', 'Complex')], default='simple')
    ear_order = models.CharField(max_length=50, choices=[('left_first', 'Left First'), ('right_first', 'Right First')], default='left_first')

    def __str__(self):
        return f"Session {self.id} for Participant {self.participant.id}"

class RhythmSequence(models.Model):
    RHYTHM_TYPE_CHOICES = [
        ('simple', 'Simple'),
        ('complex', 'Complex'),
    ]

    name = models.CharField(max_length=100, unique=True)
    rhythm_type = models.CharField(max_length=10, choices=RHYTHM_TYPE_CHOICES, default='simple')  # Use default as a parameter here
    sequence_data = models.JSONField(help_text="Enter the rhythm sequence in JSON format")

    def __str__(self):
        return f"{self.name} ({self.rhythm_type})"

class Trial(models.Model):
    session = models.ForeignKey(ExperimentSession, on_delete=models.CASCADE)
    trial_number = models.IntegerField()
    rhythm_sequence = models.ForeignKey(RhythmSequence, on_delete=models.CASCADE)
    is_practice = models.BooleanField(default=False)
    sequence_order = models.IntegerField(default=1)  # Manual sequence control

    def __str__(self):
        return f"Trial {self.trial_number} - Session {self.session.id}"

class Analysis(models.Model):
    trial = models.OneToOneField(Trial, on_delete=models.CASCADE)
    reaction_time = models.DurationField(blank=True, null=True)
    response = models.TextField(blank=True, null=True)  # Store JSON or plain text response data

    def __str__(self):
        return f"Analysis for Trial {self.trial.trial_number}"


# New model for TapRecord
class TapRecord(models.Model):
    trial = models.ForeignKey(Trial, on_delete=models.CASCADE, related_name='tap_records')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    tap_times = models.JSONField(help_text="List of tap timestamps")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TapRecord for Trial {self.trial.trial_number} by Participant {self.participant.id}"