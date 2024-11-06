from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from .models import Trial, ExperimentSession, Participant, Analysis, RhythmSequence, TapRecord
from .forms import ParticipantForm
import json
import random
import os
import numpy as np
import pandas as pd
from repp.analysis import REPPAnalysis
from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from rest_framework import viewsets
from .serializers import RhythmSequenceSerializer
from urllib.parse import urljoin
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class TapRecordAPIView(APIView):
    def post(self, request, trial_number):
        """
        Endpoint to record a participant's tap times during a trial.

        Parameters:
            trial_number (int): The current trial number

        Request Data:
            tap_times (list): A list of tap timestamps

        Returns:
            Response with 'success' key set to True if successful, or an error message and a 400 status code if the request data is invalid
        """
        try:
            print('recieved data format ', request.data)
            # Get participant ID from session
            participant_id = request.session.get('participant_id')
            if not participant_id:
                return Response({'error': 'Participant not found in session'}, status=status.HTTP_400_BAD_REQUEST)

            # Retrieve participant and trial
            participant = get_object_or_404(Participant, id=participant_id)
            trial = get_object_or_404(Trial, trial_number=trial_number, session__participant=participant)

            # Retrieve tap_times from the request data
            tap_times = request.data.get('tap_times')
            print("✔️ tap times", tap_times)
            if not isinstance(tap_times, list) or not all(isinstance(t, (int, float)) for t in tap_times):
                logger.error("Invalid tap_times data format")
                return Response({'error': 'Invalid tap_times data format'}, status=status.HTTP_400_BAD_REQUEST)

            # Create a new TapRecord
            TapRecord.objects.create(
                trial=trial,
                participant=participant,
                tap_times=tap_times
            )

            return Response({'success': True}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error in TapRecordAPIView: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Utility function to generate rhythm audio
def generate_rhythm_audio(sequence, output_dir, filename):
    repp_stimulus = REPPStimulus("generated_rhythm", config=sms_tapping)
    stim_onsets = repp_stimulus.make_onsets_from_ioi(sequence)
    audio, _stim_info, _stim_alignment = repp_stimulus.prepare_stim_from_onsets(stim_onsets)
    audio_path = os.path.join(output_dir, filename)
    REPPStimulus.to_wav(audio, audio_path, sms_tapping.FS)
    return audio_path

class RhythmSequenceViewSet(viewsets.ModelViewSet):
    queryset = RhythmSequence.objects.all()
    serializer_class = RhythmSequenceSerializer

class WelcomeHomeView(View):
    template_name = 'experiment/welcome.html'

    def get(self, request):
        form = ParticipantForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save()
            request.session['participant_id'] = participant.id
            return redirect('practice')
        else:
            return render(request, self.template_name, {'form': form})

class PracticeView(View):
    template_name = 'experiment/practice.html'

    def get(self, request):
        participant_id = request.session.get('participant_id')
        if not participant_id:
            return redirect('welcome_home')

        participant = Participant.objects.get(id=participant_id)
        experiment_session, created = ExperimentSession.objects.get_or_create(
            participant=participant,
            defaults={
                'complexity_level': random.choice(['simple', 'complex']),
                'ear_order': random.choice(['left_first', 'right_first']),
                'start_time': timezone.now(),
            }
        )

        rhythm_sequences = RhythmSequence.objects.filter(rhythm_type=experiment_session.complexity_level)
        rhythm_sequence = rhythm_sequences.first()
        if not rhythm_sequence:
            print("No rhythm sequence available for the selected complexity.")
            return redirect('welcome_home')

        request.session['rhythm_sequence_id'] = rhythm_sequence.id

        context = {
            'participant_id': participant_id,
            'complexity_level': experiment_session.complexity_level,
            'ear_order': experiment_session.ear_order,
            'rhythm_sequence': rhythm_sequence,
            'rhythm_sequence_data': {
                'name': rhythm_sequence.name,
                'sequence_data': rhythm_sequence.sequence_data,
            },
            'trial_number': 1  # Starting trial number
        }
        return render(request, self.template_name, context)

class TrialView(View):
    template_name = 'experiment/trials.html'

    def get(self, request, trial_number):
        try:
            participant_id = request.session.get('participant_id')
            if not participant_id:
                print("No participant ID in session.")
                return redirect('welcome_home')

            participant = get_object_or_404(Participant, id=participant_id)
            experiment_session, created = ExperimentSession.objects.get_or_create(
                participant=participant,
                defaults={
                    'complexity_level': random.choice(['simple', 'complex']),
                    'ear_order': random.choice(['left_first', 'right_first']),
                    'start_time': timezone.now(),
                }
            )

            rhythm_sequences = RhythmSequence.objects.filter(rhythm_type=experiment_session.complexity_level)
            rhythm_sequence = rhythm_sequences.first()
            if not rhythm_sequence:
                print("No rhythm sequence available for the selected complexity.")
                return redirect('welcome_home')

            request.session['rhythm_sequence_id'] = rhythm_sequence.id

            # Generate or locate the rhythm audio file
            audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
            os.makedirs(audio_dir, exist_ok=True)
            audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
            audio_path = os.path.join(audio_dir, audio_filename)

            if not os.path.exists(audio_path):
                generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)
                print(f"Audio generated for rhythm sequence {rhythm_sequence.id} at {audio_path}")

            audio_url = urljoin(settings.MEDIA_URL, f"rhythm_audios/{audio_filename}")

            context = {
                'participant_id': participant_id,
                'complexity_level': experiment_session.complexity_level,
                'ear_order': experiment_session.ear_order,
                'rhythm_sequence': rhythm_sequence,
                'audio_url': audio_url,
                'trial_number': trial_number,
            }
            return render(request, self.template_name, context)

        except Exception as e:
            print(f"An error occurred in TrialView GET: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def post(self, request, trial_number):
        try:
            data = json.loads(request.body)
            tap_times = data.get('tap_times')
            stim_onsets = data.get('stim_onsets')

            if not tap_times or not stim_onsets:
                print("Invalid data received.")
                return JsonResponse({'error': 'Invalid data received'}, status=400)

            participant_id = request.session.get('participant_id')
            participant = get_object_or_404(Participant, id=participant_id)
            experiment_session = get_object_or_404(ExperimentSession, participant=participant)
            rhythm_sequence = RhythmSequence.objects.get(id=request.session['rhythm_sequence_id'])

            trial, created = Trial.objects.get_or_create(
                session=experiment_session,
                trial_number=trial_number,
                defaults={'rhythm_sequence': rhythm_sequence}
            )

            # Create a new TapRecord entry
            TapRecord.objects.create(
                trial=trial,
                participant=participant,
                tap_times=tap_times
            )

            # Perform analysis as before
            stim_info = {'onsets': stim_onsets}
            resp_info = {'onsets': tap_times}
            analysis = REPPAnalysis(config=sms_tapping)
            output, analysis_result, is_failed = analysis.do_analysis(
                stim_info,
                resp_info,
                f"trial_{trial_number}",
                None
            )

            reaction_times = calculate_reaction_time(tap_times, stim_onsets)
            Analysis.objects.create(
                trial=trial,
                reaction_time=json.dumps(reaction_times),
                response=json.dumps(tap_times),
            )

            # Save analysis data to CSV as before
            output_dir = os.path.join('output', f"participant_{participant_id}")
            os.makedirs(output_dir, exist_ok=True)
            csv_path = os.path.join(output_dir, 'participant_analysis.csv')
            self.save_analysis_to_csv(csv_path, output, analysis_result, is_failed, trial_number, experiment_session)

            return JsonResponse({'success': True})

        except json.JSONDecodeError:
            print("Error decoding JSON from request body.")
            return JsonResponse({'error': 'Invalid JSON format.'}, status=400)

        except Exception as e:
            print(f"An error occurred in TrialView POST: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


    def save_analysis_to_csv(self, csv_path, output, analysis_result, is_failed, trial_number, experiment_session):
        try:
            metrics = {
                'trial_number': trial_number,
                'complexity_level': experiment_session.complexity_level,
                'ear_order': experiment_session.ear_order,
                'trial_failed': is_failed['failed'],
                'failure_reason': is_failed.get('reason', 'N/A'),
                'mean_asynchrony': analysis_result['mean_async_all'],
                'sd_asynchrony': analysis_result['sd_async_all'],
                'percent_responses_aligned': analysis_result['percent_resp_aligned_all'],
                'mean_stimulus_ioi': np.nanmean([x for x in output['stim_ioi'] if not np.isnan(x)]),
                'mean_response_ioi': np.nanmean([x for x in output['resp_ioi'] if not np.isnan(x)]),
            }
            df = pd.DataFrame([metrics])
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                df_combined = pd.concat([df_existing, df], ignore_index=True)
            else:
                df_combined = df
            df_combined.to_csv(csv_path, index=False)
        except Exception as e:
            print(f"Error saving analysis to CSV: {e}")


class CompletionView(TemplateView):
    template_name = 'experiment/complete.html'

    def get(self, request, *args, **kwargs):
        participant_id = request.session.get('participant_id')
        if participant_id:
            participant = Participant.objects.get(id=participant_id)
            session = ExperimentSession.objects.filter(participant=participant).first()
            if session and not session.end_time:
                session.end_time = timezone.now()
                session.save()
            del request.session['participant_id']
        return super().get(request, *args, **kwargs)


def calculate_reaction_time(resp_onsets, stim_onsets):
    reaction_times = []
    for resp_time in resp_onsets:
        closest_stim_time = min(stim_onsets, key=lambda x: abs(x - resp_time))
        rt = resp_time - closest_stim_time
        reaction_times.append(rt)
    return reaction_times


# from django.views.generic import TemplateView, View
# from django.shortcuts import render, redirect
# from django.urls import reverse
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.http import JsonResponse
# from django.utils import timezone
# from .models import Trial, ExperimentSession, Participant, Analysis, RhythmSequence
# from .forms import ParticipantForm
# from rest_framework import viewsets, status
# from rest_framework.response import Response
# from rest_framework.views import APIView
# import json
# import random
# from repp.analysis import REPPAnalysis
# from repp.config import sms_tapping
# from .serializers import TrialSerializer, ExperimentSessionSerializer, ParticipantSerializer, AnalysisSerializer, RhythmSequenceSerializer


# class RhythmSequenceViewSet(viewsets.ModelViewSet):
#     queryset = RhythmSequence.objects.all()
#     serializer_class = RhythmSequenceSerializer


# class WelcomeHomeView(View):
#     template_name = 'experiment/welcome.html'

#     def get(self, request):
#         form = ParticipantForm()
#         return render(request, self.template_name, {'form': form})

#     def post(self, request):
#         form = ParticipantForm(request.POST)
#         if form.is_valid():
#             participant = form.save()
#             request.session['participant_id'] = participant.id
#             return redirect('practice')
#         else:
#             return render(request, self.template_name, {'form': form})


# class PracticeView(View):
#     template_name = 'experiment/practice.html'

#     def get(self, request):
#         participant_id = request.session.get('participant_id')
#         if not participant_id:
#             return redirect('welcome_home')

#         participant = Participant.objects.get(id=participant_id)
#         experiment_session, created = ExperimentSession.objects.get_or_create(
#             participant=participant,
#             defaults={
#                 'complexity_level': random.choice(['simple', 'complex']),
#                 'ear_order': random.choice(['left_first', 'right_first']),
#                 'start_time': timezone.now(),
#             }
#         )

#         rhythm_sequences = RhythmSequence.objects.filter(rhythm_type=experiment_session.complexity_level)
#         rhythm_sequence = rhythm_sequences.first()
#         if not rhythm_sequence:
#             print("No rhythm sequence available for the selected complexity.")
#             return redirect('welcome_home')

#         request.session['rhythm_sequence_id'] = rhythm_sequence.id

#         # Pass the starting trial number (e.g., 1)
#         context = {
#             'participant_id': participant_id,
#             'complexity_level': experiment_session.complexity_level,
#             'ear_order': experiment_session.ear_order,
#             'rhythm_sequence': rhythm_sequence,
#             'rhythm_sequence_data': {
#                 'name': rhythm_sequence.name,
#                 'sequence_data': rhythm_sequence.sequence_data,
#             },
#             'trial_number': 1  # Starting trial number
#         }
#         return render(request, self.template_name, context)



# from django.shortcuts import get_object_or_404
# import os
# import numpy as np
# import pandas as pd
# from repp.stimulus import REPPStimulus
# from django.conf import settings

# def generate_rhythm_audio(sequence, output_dir, filename):
#     """Generate an audio file from a rhythm sequence using REPP."""
#     repp_stimulus = REPPStimulus("generated_rhythm", config=sms_tapping)
#     stim_onsets = repp_stimulus.make_onsets_from_ioi(sequence)
#     audio, _stim_info, _stim_alignment = repp_stimulus.prepare_stim_from_onsets(stim_onsets)
#     audio_path = os.path.join(output_dir, filename)
#     REPPStimulus.to_wav(audio, audio_path, sms_tapping.FS)
#     return audio_path

# class TrialView(View):
#     template_name = 'experiment/trials.html'

#     def get(self, request, trial_number):
#         # Existing setup code
#         participant_id = request.session.get('participant_id')
#         if not participant_id:
#             return redirect('welcome_home')

#         participant = get_object_or_404(Participant, id=participant_id)
#         experiment_session, created = ExperimentSession.objects.get_or_create(
#             participant=participant,
#             defaults={
#                 'complexity_level': random.choice(['simple', 'complex']),
#                 'ear_order': random.choice(['left_first', 'right_first']),
#                 'start_time': timezone.now(),
#             }
#         )

#         # Fetch or create the rhythm sequence
#         rhythm_sequences = RhythmSequence.objects.filter(rhythm_type=experiment_session.complexity_level)
#         rhythm_sequence = rhythm_sequences.first()
#         if not rhythm_sequence:
#             print("No rhythm sequence available for the selected complexity.")
#             return redirect('welcome_home')

#         request.session['rhythm_sequence_id'] = rhythm_sequence.id

#         # Generate the rhythm audio file if not already generated
#         audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
#         os.makedirs(audio_dir, exist_ok=True)
#         audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
#         audio_path = os.path.join(audio_dir, audio_filename)
        
#         # Generate audio only if it doesn't exist
#         if not os.path.exists(audio_path):
#             generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)
        
#         audio_url = os.path.join(settings.MEDIA_URL, 'rhythm_audios', audio_filename)

#         context = {
#             'participant_id': participant_id,
#             'complexity_level': experiment_session.complexity_level,
#             'ear_order': experiment_session.ear_order,
#             'rhythm_sequence': rhythm_sequence,
#             'audio_url': audio_url,
#             'trial_number': trial_number,
#         }
#         return render(request, self.template_name, context)



# class CompletionView(TemplateView):
#     template_name = 'experiment/complete.html'

#     def get(self, request, *args, **kwargs):
#         participant_id = request.session.get('participant_id')
#         if participant_id:
#             participant = Participant.objects.get(id=participant_id)
#             session = ExperimentSession.objects.filter(participant=participant).first()
#             if session and not session.end_time:
#                 session.end_time = timezone.now()
#                 session.save()
#             del request.session['participant_id']
#         return super().get(request, *args, **kwargs)


# def get_stimulus_onsets(rhythm_sequence):
#     iois_in_seconds = [ioi / 1000.0 for ioi in rhythm_sequence]
#     onset_times = [0.0]
#     for ioi in iois_in_seconds:
#         onset_times.append(onset_times[-1] + ioi)
#     return onset_times[1:]


# def calculate_reaction_time(resp_onsets, stim_onsets):
#     reaction_times = []
#     for resp_time in resp_onsets:
#         closest_stim_time = min(stim_onsets, key=lambda x: abs(x - resp_time))
#         rt = resp_time - closest_stim_time
#         reaction_times.append(rt)
#     return reaction_times


# def assign_rhythm_sequence(session):
#     # Randomly select a rhythm sequence based on complexity
#     rhythm_type = 'simple' if session.complexity_level == 'simple' else 'complex'
#     rhythm_sequences = RhythmSequence.objects.filter(rhythm_type=rhythm_type)
#     sequence = random.choice(rhythm_sequences)
#     return sequence