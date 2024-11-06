from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Participant, ExperimentSession, Trial

class ExperimentViewsTest(TestCase):
    def setUp(self):
        # Create a user and participant
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.participant = Participant.objects.get(user=self.user)
        # Create an ExperimentSession
        self.session = ExperimentSession.objects.create(
            participant=self.participant,
            complexity_level='simple',
            ear_order='left_first'
        )
        # Create a Trial
        self.trial = Trial.objects.create(
            session=self.session,
            trial_number=1,
            rhythm_sequence=None,  # Assign as needed
            ear_first_order='left_first',
            is_practice=False
        )

    def test_welcome_view(self):
        response = self.client.get(reverse('welcome'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'experiment/welcome.html')

    def test_practice_view_requires_login(self):
        response = self.client.get(reverse('practice'))
        self.assertRedirects(response, '/admin/login/?next=/practice/')

    def test_practice_view_authenticated(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('practice'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'experiment/practice.html')

    def test_trial_view(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('trial', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'experiment/trial.html')

    def test_completion_view(self):
        self.client.login(username='testuser', password='testpass')
        response = self.client.get(reverse('complete'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'experiment/complete.html')
