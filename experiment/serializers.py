from rest_framework import serializers
from .models import RhythmSequence, Participant, ExperimentSession, Trial, Analysis

class RhythmSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = RhythmSequence
        fields = ['id', 'name', 'rhythm_type', 'sequence_data']
        # Future field for audio if needed: 'audio_url'
        

class StartExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentSession
        fields = ['id', 'participant', 'start_time', 'complexity_level', 'ear_order']
        read_only_fields = ['id', 'start_time']

    def validate_complexity_level(self, value):
        if value not in ['simple', 'complex']:
            raise serializers.ValidationError("Complexity level must be 'simple' or 'complex'.")
        return value

    def validate_ear_order(self, value):
        if value not in ['left_first', 'right_first']:
            raise serializers.ValidationError("Ear order must be 'left_first' or 'right_first'.")
        return value


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
        read_only_fields = ['id', 'created_at']  # Add created_at if included in model


class ExperimentSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentSession
        fields = '__all__'
        read_only_fields = ['id', 'start_time', 'end_time']


class TrialSerializer(serializers.ModelSerializer):
    trial_number = serializers.IntegerField()
    participant = serializers.PrimaryKeyRelatedField(read_only=True, source='session.participant')

    class Meta:
        model = Trial
        fields = ['id', 'session', 'trial_number', 'rhythm_sequence', 'is_practice', 'sequence_order', 'participant']
        read_only_fields = ['id']


class AnalysisSerializer(serializers.ModelSerializer):
    reaction_time = serializers.DurationField(required=False, allow_null=True)
    response_data = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = Analysis
        fields = ['id', 'trial', 'reaction_time', 'response_data']
        read_only_fields = ['id']
