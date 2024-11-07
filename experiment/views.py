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
import matplotlib.pyplot as plt
from .aws import upload_to_s3  # Assuming upload_to_s3 is implemented in aws.py
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Helper function to generate rhythm audio
def generate_rhythm_audio(sequence, filename):
    repp_stimulus = REPPStimulus("generated_rhythm", config=sms_tapping)
    stim_onsets = repp_stimulus.make_onsets_from_ioi(sequence)
    audio, _stim_info, _stim_alignment = repp_stimulus.prepare_stim_from_onsets(stim_onsets)
    
    # Adding markers to the start and end
    marker_duration = 0.25
    fs = sms_tapping.FS
    marker = np.sin(2 * np.pi * 440 * np.linspace(0, marker_duration, int(fs * marker_duration)))
    silence = np.zeros(int(0.2 * fs))
    markers = np.concatenate([marker, silence, marker, silence, marker])

    full_audio = np.concatenate([markers, audio, markers])
    local_path = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios', filename)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    REPPStimulus.to_wav(full_audio, local_path, fs)

    # Upload audio to AWS S3 and get URL
    s3_path = f"rhythm_audios/{filename}"
    audio_url = upload_to_s3(local_path, s3_path)
    return audio_url

class CompletionView(TemplateView):
    template_name = 'experiment/completion.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    

@method_decorator(csrf_exempt, name='dispatch')
class TapRecordAPIView(APIView):
    def post(self, request, trial_number):
        try:
            
            participant_id = request.session.get('participant_id')
            if not participant_id:
                return Response({'error': 'Participant not found in session'}, status=status.HTTP_400_BAD_REQUEST)

            participant = get_object_or_404(Participant, id=participant_id)
            experiment_session = ExperimentSession.objects.filter(participant=participant).first()
            trial = Trial.objects.filter(session=experiment_session, trial_number=trial_number).first()

            if not trial:
                return Response({'error': 'Trial not found'}, status=status.HTTP_404_NOT_FOUND)

            tap_times = request.data.get('tap_times', [])
            if not isinstance(tap_times, list):
                return Response({'error': 'tap_times must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

            TapRecord.objects.update_or_create(
                trial=trial,
                participant=participant,
                defaults={'tap_times': tap_times}
            )

            return Response({'success': True}, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error in TapRecordAPIView: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
            'trial_number': 1
        }
        return render(request, self.template_name, context)
    
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend for Matplotlib

class TrialView(View):
    template_name = 'experiment/trials.html'

    def get(self, request, trial_number):
        participant_id = request.session.get('participant_id')
        if not participant_id:
            return redirect('welcome_home')

        participant = get_object_or_404(Participant, id=participant_id)
        experiment_session = get_object_or_404(ExperimentSession, participant=participant)
        rhythm_sequence = get_object_or_404(RhythmSequence, id=request.session.get('rhythm_sequence_id'))

        audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
        audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
        audio_path = os.path.join(audio_dir, audio_filename)

        # Generate the audio file if it doesn't exist
        if not os.path.exists(audio_path):
            logger.debug(f"Generating audio file for {audio_filename}")
            # generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)
            generate_rhythm_audio(rhythm_sequence.sequence_data, audio_filename)

        audio_url = os.path.join(settings.MEDIA_URL, f"rhythm_audios/{audio_filename}")
        context = {
            'participant_id': participant_id,
            'complexity_level': experiment_session.complexity_level,
            'ear_order': experiment_session.ear_order,
            'rhythm_sequence': rhythm_sequence,
            'audio_url': audio_url,
            'trial_number': trial_number,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, trial_number):
        try:
            participant_id = request.session.get('participant_id')
            if not participant_id:
                return JsonResponse({'error': 'Participant not found in session.'}, status=400)

            # Retrieve experiment session for the participant
            participant = get_object_or_404(Participant, id=participant_id)
            experiment_session = get_object_or_404(ExperimentSession, participant=participant)

            # Define local directories based on the participant and trial structure
            participant_dir = os.path.join(settings.MEDIA_ROOT, f"participant_{participant_id}")
            stimulus_dir = os.path.join(participant_dir, f"stimulus_1")  # Adjust stimulus number dynamically if needed
            trial_dir = os.path.join(stimulus_dir, f"trial_{trial_number}")
            os.makedirs(trial_dir, exist_ok=True)

            # Save and upload the background audio file
            background_audio = request.FILES.get('background_audio')
            if background_audio:
                local_audio_path = os.path.join(trial_dir, f"recording_trial_{trial_number}.wav")
                with open(local_audio_path, 'wb') as f:
                    f.write(background_audio.read())
                s3_audio_path = f"participant_{participant_id}/stimulus_1/trial_{trial_number}/recording_trial_{trial_number}.wav"
                upload_to_s3(local_audio_path, s3_audio_path)
                logger.info(f"Uploaded audio to S3: {s3_audio_path}")
            else:
                logger.warning("No background audio file provided in request.")

            # Placeholder for the analysis result
            analysis_result = {
                'mean_async_all': 0.5,
                'sd_async_all': 0.1,
                'percent_resp_aligned_all': 95.0
            }
            output = {'stim_ioi': [500, 510, 520], 'resp_ioi': [495, 505, 515]}  # Replace with actual data

            # Generate CSV and upload to S3
            csv_path = os.path.join(stimulus_dir, 'participant_analysis.csv')
            self.save_analysis_to_csv(csv_path, output, analysis_result, is_failed={}, trial_number=trial_number, experiment_session=experiment_session)
            s3_csv_path = f"participant_{participant_id}/stimulus_1/participant_analysis.csv"
            upload_to_s3(csv_path, s3_csv_path)

            # Plot and save plot image
            plot_output_dir = trial_dir
            self.plot_trial_data(output, trial_number, plot_output_dir)
            plot_path = os.path.join(plot_output_dir, f"plot_trial_{trial_number}.png")
            s3_plot_path = f"participant_{participant_id}/stimulus_1/trial_{trial_number}/plot_trial_{trial_number}.png"
            upload_to_s3(plot_path, s3_plot_path)

            return JsonResponse({'success': True})

        except Exception as e:
            logger.error(f"Unexpected error in TrialView POST: {e}")
            return JsonResponse({'error': str(e)}, status=500)

    def save_analysis_to_csv(self, csv_path, output, analysis_result, is_failed, trial_number, experiment_session):
        try:
            metrics = {
                'trial_number': trial_number,
                'complexity_level': experiment_session.complexity_level if experiment_session else 'N/A',
                'ear_order': experiment_session.ear_order if experiment_session else 'N/A',
                'trial_failed': is_failed.get('failed', False),
                'failure_reason': is_failed.get('reason', 'N/A'),
                'mean_asynchrony': analysis_result.get('mean_async_all', float('nan')),
                'sd_asynchrony': analysis_result.get('sd_async_all', float('nan')),
                'percent_responses_aligned': analysis_result.get('percent_resp_aligned_all', float('nan')),
                'mean_stimulus_ioi': pd.Series(output.get('stim_ioi', [])).mean(),
                'mean_response_ioi': pd.Series(output.get('resp_ioi', [])).mean(),
            }
            df = pd.DataFrame([metrics])

            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                df_combined = pd.concat([df_existing, df], ignore_index=True)
            else:
                df_combined = df
            df_combined.to_csv(csv_path, index=False)
            logger.info(f"CSV saved at {csv_path}")

        except Exception as e:
            logger.error(f"Error saving CSV: {e}")

    def plot_trial_data(self, output, trial_number, output_dir):
        try:
            stim_ioi = output.get('stim_ioi', [])
            resp_ioi = output.get('resp_ioi', [])

            # Check if data exists
            if not stim_ioi or not resp_ioi:
                logger.warning(f"No data to plot for trial {trial_number}. stim_ioi: {stim_ioi}, resp_ioi: {resp_ioi}")
                return
            
            # Convert IOIs to cumulative onsets if necessary
            stim_onsets = [sum(stim_ioi[:i+1]) for i in range(len(stim_ioi))]
            resp_onsets = [sum(resp_ioi[:i+1]) for i in range(len(resp_ioi))]

            plt.figure(figsize=(10, 6))
            plt.plot(stim_onsets, label="Stimulus Onsets", color='blue')
            plt.plot(resp_onsets, label="Response Onsets", linestyle='--', color='orange')
            plt.legend()
            plt.title(f"Trial {trial_number} Stimulus vs Response Onsets")
            plt.xlabel("Time (ms)")
            plt.ylabel("Amplitude")
            plot_path = os.path.join(output_dir, f"plot_trial_{trial_number}.png")
            plt.savefig(plot_path)
            plt.close()
            logger.info(f"Plot saved at {plot_path}")

        except Exception as e:
            logger.error(f"Error plotting trial data: {e}")

def calculate_reaction_time(resp_onsets, stim_onsets):
    reaction_times = []
    for resp_time in resp_onsets:
        closest_stim_time = min(stim_onsets, key=lambda x: abs(x - resp_time))
        rt = resp_time - closest_stim_time
        reaction_times.append(rt)
    return reaction_times



# class TrialView(View):
    
#     template_name = 'experiment/trials.html'

#     def get(self, request, trial_number):
#         participant_id = request.session.get('participant_id')
#         if not participant_id:
#             return redirect('welcome_home')

#         participant = get_object_or_404(Participant, id=participant_id)
#         experiment_session = ExperimentSession.objects.get(participant=participant)
#         rhythm_sequence = RhythmSequence.objects.get(id=request.session['rhythm_sequence_id'])

#         audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
#         audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
#         audio_path = os.path.join(audio_dir, audio_filename)

#         # Generate the audio file if it doesn't exist
#         if not os.path.exists(audio_path):
#             logger.debug(f"Generating audio file for {audio_filename}")
#             generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)

#         audio_url = os.path.join(settings.MEDIA_URL, f"rhythm_audios/{audio_filename}")
#         context = {
#             'participant_id': participant_id,
#             'complexity_level': experiment_session.complexity_level,
#             'ear_order': experiment_session.ear_order,
#             'rhythm_sequence': rhythm_sequence,
#             'audio_url': audio_url,
#             'trial_number': trial_number,
#         }
#         return render(request, self.template_name, context)
    
    
#     def post(self, request, trial_number):
#         try:
#             participant_id = request.session.get('participant_id')
#             if not participant_id:
#                 return JsonResponse({'error': 'Participant not found in session.'}, status=400)

#             # Define local directories based on the participant and trial structure
#             participant_dir = os.path.join(settings.MEDIA_ROOT, f"participant_{participant_id}")
#             stimulus_dir = os.path.join(participant_dir, f"stimulus_1")  # Adjust stimulus number dynamically if needed
#             trial_dir = os.path.join(stimulus_dir, f"trial_{trial_number}")
#             os.makedirs(trial_dir, exist_ok=True)

#             # Save and upload the background audio file
#             background_audio = request.FILES.get('background_audio')
#             if background_audio:
#                 local_audio_path = os.path.join(trial_dir, f"recording_trial_{trial_number}.wav")
#                 with open(local_audio_path, 'wb') as f:
#                     f.write(background_audio.read())
#                 s3_audio_path = f"participant_{participant_id}/stimulus_1/trial_{trial_number}/recording_trial_{trial_number}.wav"
#                 upload_to_s3(local_audio_path, s3_audio_path)

#             # Placeholder for the analysis result (mocked)
#             analysis_result = {
#                 'mean_async_all': 0.5,
#                 'sd_async_all': 0.1,
#                 'percent_resp_aligned_all': 95.0
#             }
#             output = {'stim_ioi': [500, 510, 520], 'resp_ioi': [495, 505, 515]}  # Replace with actual data

#             # Generate CSV and upload to S3
#             csv_path = os.path.join(stimulus_dir, 'participant_analysis.csv')
#             self.save_analysis_to_csv(csv_path, output, analysis_result, is_failed={}, trial_number=trial_number, experiment_session=None)
#             s3_csv_path = f"participant_{participant_id}/stimulus_1/participant_analysis.csv"
#             upload_to_s3(csv_path, s3_csv_path)

#             # Plot and save plot image
#             plot_output_dir = trial_dir
#             self.plot_trial_data(output, trial_number, plot_output_dir)
#             plot_path = os.path.join(plot_output_dir, f"plot_trial_{trial_number}.png")
#             s3_plot_path = f"participant_{participant_id}/stimulus_1/trial_{trial_number}/plot_trial_{trial_number}.png"
#             upload_to_s3(plot_path, s3_plot_path)

#             # Additional files can be generated, saved, and uploaded similarly...
#             return JsonResponse({'success': True})

#         except Exception as e:
#             return JsonResponse({'error': str(e)}, status=500)

#     def save_analysis_to_csv(self, csv_path, output, analysis_result, is_failed, trial_number, experiment_session):
#         try:
#             metrics = {
#                 'trial_number': trial_number,
#                 'complexity_level': experiment_session.complexity_level if experiment_session else 'N/A',
#                 'ear_order': experiment_session.ear_order if experiment_session else 'N/A',
#                 'trial_failed': is_failed.get('failed', False),
#                 'failure_reason': is_failed.get('reason', 'N/A'),
#                 'mean_asynchrony': analysis_result.get('mean_async_all', float('nan')),
#                 'sd_asynchrony': analysis_result.get('sd_async_all', float('nan')),
#                 'percent_responses_aligned': analysis_result.get('percent_resp_aligned_all', float('nan')),
#                 'mean_stimulus_ioi': pd.Series(output.get('stim_ioi', [])).mean(),
#                 'mean_response_ioi': pd.Series(output.get('resp_ioi', [])).mean(),
#             }
#             df = pd.DataFrame([metrics])

#             if os.path.exists(csv_path):
#                 df_existing = pd.read_csv(csv_path)
#                 df_combined = pd.concat([df_existing, df], ignore_index=True)
#             else:
#                 df_combined = df
#             df_combined.to_csv(csv_path, index=False)

#         except Exception as e:
#             logger.error(f"Error saving CSV: {e}")

#     def plot_trial_data(self, output, trial_number, output_dir):
#         try:
#             stim_ioi = output.get('stim_ioi', [])
#             resp_ioi = output.get('resp_ioi', [])

#             # Verify the data presence and length
#             if not stim_ioi or not resp_ioi:
#                 logger.warning(f"No data to plot for trial {trial_number}. stim_ioi: {stim_ioi}, resp_ioi: {resp_ioi}")
#                 return
            
#             # Convert IOIs to cumulative onsets if necessary (assuming IOIs are durations between taps)
#             stim_onsets = [sum(stim_ioi[:i+1]) for i in range(len(stim_ioi))]
#             resp_onsets = [sum(resp_ioi[:i+1]) for i in range(len(resp_ioi))]

#             # Check if the cumulative onsets have been correctly created
#             logger.debug(f"stim_onsets: {stim_onsets}")
#             logger.debug(f"resp_onsets: {resp_onsets}")

#             # Plot stimulus and response onsets
#             plt.figure(figsize=(10, 6))
#             plt.plot(stim_onsets, label="Stimulus Onsets", color='blue')
#             plt.plot(resp_onsets, label="Response Onsets", linestyle='--', color='orange')
#             plt.legend()
#             plt.title(f"Trial {trial_number} Stimulus vs Response Onsets")
#             plt.xlabel("Time (ms)")
#             plt.ylabel("Amplitude")
#             plot_path = os.path.join(output_dir, f"plot_trial_{trial_number}.png")
#             plt.savefig(plot_path)
#             plt.close()

#             logger.info(f"Plot saved at {plot_path}")

#         except Exception as e:
#             logger.error(f"Error plotting trial data: {e}")
    