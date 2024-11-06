# experiment/forms.py

from django import forms
from .models import Participant
from django.core.exceptions import ValidationError

class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['age', 'is_right_handed', 'has_music_background', 'email', 'agreed_to_terms']
        widgets = {
            'age': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'placeholder': 'Enter your age'}),
            'is_right_handed': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
            'has_music_background': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'placeholder': 'Enter your email'}),
            'agreed_to_terms': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
        }
        help_texts = {
            'agreed_to_terms': 'You must agree to the terms to participate.',
        }


# class ParticipantForm(forms.ModelForm):
#     class Meta:
#         model = Participant
#         fields = ['age', 'is_right_handed', 'has_music_background', 'email', 'agreed_to_terms']
#         widgets = {
#             'age': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'placeholder': 'Enter your age'}),
#             'is_right_handed': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
#             'has_music_background': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
#             'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'placeholder': 'Enter your email'}),
#             'agreed_to_terms': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
#         }


class TrialResponseForm(forms.Form):
    response = forms.CharField(
        label='Your Response',
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
            'placeholder': 'Enter your response here...',
            'rows': 4,
        }),
        required=True,
    )

    def clean_response(self):
        response = self.cleaned_data.get('response')
        if not response.strip():
            raise ValidationError("Response cannot be empty.")
        return response
