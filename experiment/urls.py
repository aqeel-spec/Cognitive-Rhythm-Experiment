from django.urls import path
from .views import WelcomeHomeView, PracticeView, TrialView, CompletionView, TapRecordAPIView

urlpatterns = [
    path('', WelcomeHomeView.as_view(), name='welcome_home'),
    path('practice/', PracticeView.as_view(), name='practice'),
    path('trial/<int:trial_number>/', TrialView.as_view(), name='trial'),
    path('trial/<int:trial_number>/tap-record/', TapRecordAPIView.as_view(), name='tap_record'),
    path('complete/', CompletionView.as_view(), name='complete'),
]
