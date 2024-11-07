# experiment/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ExperimentSession, Trial, RhythmSequence

TRIAL_COUNT = 12  # Define the number of trials per session

@receiver(post_save, sender=ExperimentSession)
def create_trials_for_session(sender, instance, created, **kwargs):
    if created:
        print(f"Signal triggered for ExperimentSession {instance.id}")
        try:
            # Choose the appropriate rhythm sequence based on session complexity level
            rhythm_sequence = RhythmSequence.objects.filter(rhythm_type=instance.complexity_level).first()
            if not rhythm_sequence:
                raise ValueError("No RhythmSequence found for specified complexity level.")

            # Create trials and associate them with both session and participant
            for i in range(1, TRIAL_COUNT + 1):
                Trial.objects.create(
                    session=instance,
                    participant=instance.participant,  # Set the participant explicitly
                    trial_number=i,
                    rhythm_sequence=rhythm_sequence
                )
            print(f"Created {TRIAL_COUNT} trials for ExperimentSession {instance.id}")
        
        except Exception as e:
            print(f"Error creating trials: {e}")
