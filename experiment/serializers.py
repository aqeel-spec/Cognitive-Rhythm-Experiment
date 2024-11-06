from rest_framework import serializers
from .models import RhythmSequence, Participant, ExperimentSession, Trial, Analysis


class RhythmSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RhythmSequence
        fields = ['id', 'name', 'rhythm_type', 'sequence_data']  # Exclude 'audio_file'


class StartExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentSession
        fields = ['id', 'participant', 'start_time', 'complexity_level', 'ear_order']
        read_only_fields = ['id', 'start_time']


class RecordTapSerializer(serializers.ModelSerializer):
    response = serializers.JSONField(required=True)

    class Meta:
        model = Analysis
        fields = ['id', 'trial', 'response']
        read_only_fields = ['id', 'trial']

    def validate_response(self, value):
        """Ensure response data is a list of tap times (float or integer timestamps)."""
        if not isinstance(value, list) or not all(isinstance(item, (float, int)) for item in value):
            raise serializers.ValidationError("Response must be a list of timestamps (float or int).")
        return value


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = '__all__'


class ExperimentSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentSession
        fields = '__all__'


class TrialSerializer(serializers.ModelSerializer):
    trial_number = serializers.IntegerField()

    class Meta:
        model = Trial
        fields = ['id', 'session', 'trial_number', 'rhythm_sequence', 'is_practice', 'sequence_order']
        read_only_fields = ['id']


class AnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analysis
        fields = '__all__'
