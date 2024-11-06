from django.contrib import admin
from .models import Participant, ExperimentSession, RhythmSequence, Trial, Analysis
from django import forms
from django.contrib.postgres.fields import JSONField  # For JSON handling, if using Postgres


class RhythmSequenceAdminForm(forms.ModelForm):
    sequence_data = forms.CharField(widget=forms.Textarea, help_text="Enter the rhythm sequence in JSON format, e.g., [0, 520, 260, 260, 520, 260, 260, 520, 520]")

    class Meta:
        model = RhythmSequence
        fields = ['name', 'rhythm_type', 'sequence_data']

@admin.register(RhythmSequence)
class RhythmSequenceAdmin(admin.ModelAdmin):
    form = RhythmSequenceAdminForm
    list_display = ('id', 'name', 'rhythm_type', 'sequence_data_display')
    search_fields = ('name',)

    def sequence_data_display(self, obj):
        # Display JSON sequence as a string for readability in admin list view
        return obj.sequence_data
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
    list_filter = ('is_practice', 'session')
    search_fields = ('session__participant__id',)
