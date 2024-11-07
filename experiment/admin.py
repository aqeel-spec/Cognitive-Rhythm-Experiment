from django.contrib import admin
from .models import Participant, ExperimentSession, RhythmSequence, Trial, Analysis
from django import forms
from django.contrib.postgres.fields import JSONField  # For JSON handling

class RhythmSequenceAdminForm(forms.ModelForm):
    sequence_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'cols': 50}),
        help_text="Enter the rhythm sequence in JSON format, e.g., [0, 520, 260, 260, 520, 260, 260, 520, 520]"
    )

    class Meta:
        model = RhythmSequence
        fields = ['name', 'rhythm_type', 'sequence_data']


@admin.register(RhythmSequence)
class RhythmSequenceAdmin(admin.ModelAdmin):
    form = RhythmSequenceAdminForm
    list_display = ('id', 'name', 'rhythm_type', 'sequence_data_display')
    search_fields = ('name',)
    list_filter = ('rhythm_type',)

    def sequence_data_display(self, obj):
        return str(obj.sequence_data)[:75] + '...' if len(str(obj.sequence_data)) > 75 else obj.sequence_data
    sequence_data_display.short_description = 'Sequence Data'


class TrialAdminForm(forms.ModelForm):
    sequence_order = forms.IntegerField(help_text="Specify the sequence order for this trial.")

    class Meta:
        model = Trial
        fields = ['session', 'trial_number', 'rhythm_sequence', 'is_practice', 'sequence_order']


@admin.register(Trial)
class TrialAdmin(admin.ModelAdmin):
    form = TrialAdminForm
    list_display = ('id', 'session', 'trial_number', 'rhythm_sequence', 'is_practice', 'sequence_order')
    ordering = ('trial_number',)
    list_filter = ('is_practice', 'session', 'rhythm_sequence')
    search_fields = ('session__participant__id',)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('id', 'age', 'is_right_handed', 'has_music_background', 'email', 'agreed_to_terms')
    list_filter = ('is_right_handed', 'has_music_background', 'agreed_to_terms', 'age')
    search_fields = ('email',)


@admin.register(ExperimentSession)
class ExperimentSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'participant', 'start_time', 'end_time', 'complexity_level', 'ear_order')
    list_filter = ('complexity_level', 'ear_order', 'start_time')
    search_fields = ('participant__id',)


@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'trial', 'reaction_time', 'short_response')
    search_fields = ('trial__id',)
    list_filter = ('reaction_time',)

    def short_response(self, obj):
        """Display a truncated version of the response for readability."""
        return str(obj.response)[:75] + '...' if obj.response and len(obj.response) > 75 else obj.response
    short_response.short_description = 'Response'
