from django import forms
from django.core.exceptions import ValidationError
from .models import Participant

class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['age', 'is_right_handed', 'has_music_background', 'email', 'agreed_to_terms']
        widgets = {
            'age': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg', 
                'placeholder': 'Enter your age',
                'min': 18,  # Assuming age range 18-35
                'max': 35,
            }),
            'is_right_handed': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
            'has_music_background': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg', 
                'placeholder': 'Enter your email'
            }),
            'agreed_to_terms': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}),
        }
        help_texts = {
            'agreed_to_terms': 'You must agree to the terms to participate.',
        }

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age < 18 or age > 35:
            raise ValidationError("Age must be between 18 and 35.")
        return age

    def clean_agreed_to_terms(self):
        agreed = self.cleaned_data.get('agreed_to_terms')
        if not agreed:
            raise ValidationError("You must agree to the terms to participate.")
        return agreed


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
        # Additional validation could be added here, such as checking for specific data format if required
        return response
