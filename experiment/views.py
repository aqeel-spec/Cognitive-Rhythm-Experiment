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
    template_name = 'experiment/complete.html'

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
class TrialView(View):
    
    template_name = 'experiment/trials.html'

    def get(self, request, trial_number):
        participant_id = request.session.get('participant_id')
        if not participant_id:
            return redirect('welcome_home')

        participant = get_object_or_404(Participant, id=participant_id)
        experiment_session = ExperimentSession.objects.get(participant=participant)
        rhythm_sequence = RhythmSequence.objects.get(id=request.session['rhythm_sequence_id'])

        audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
        audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
        audio_path = os.path.join(audio_dir, audio_filename)

        # Generate the audio file if it doesn't exist
        if not os.path.exists(audio_path):
            logger.debug(f"Generating audio file for {audio_filename}")
            generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)

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
            logger.info(f"Received POST request for trial number: {trial_number}")

            # Extract and parse JSON data from request
            tap_times_raw = request.POST.get('tap_times', '[]')
            stim_onsets_raw = request.POST.get('stim_onsets', '[]')
            background_audio = request.FILES.get('background_audio')

            # Parse tap_times and stim_onsets
            try:
                tap_times = json.loads(tap_times_raw)
                stim_onsets = json.loads(stim_onsets_raw)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decoding error: {e}")
                return JsonResponse({'error': 'Invalid JSON format for tap_times or stim_onsets.'}, status=400)

            # Validate parsed data
            if not tap_times or not stim_onsets:
                logger.error("Invalid data received: missing tap_times or stim_onsets.")
                return JsonResponse({'error': 'Invalid data: missing tap_times or stim_onsets.'}, status=400)

            # Get participant information from the session
            participant_id = request.session.get('participant_id')
            if not participant_id:
                logger.error("Participant not found in session.")
                return JsonResponse({'error': 'Participant not found in session.'}, status=400)

            participant = get_object_or_404(Participant, id=participant_id)
            experiment_session = get_object_or_404(ExperimentSession, participant=participant)
            rhythm_sequence = get_object_or_404(RhythmSequence, id=request.session.get('rhythm_sequence_id'))

            # Save trial data
            trial, created = Trial.objects.get_or_create(
                session=experiment_session,
                participant=participant,
                trial_number=trial_number,
                defaults={'rhythm_sequence': rhythm_sequence}
            )
            TapRecord.objects.create(trial=trial, participant=participant, tap_times=tap_times)

            # Set up local audio file path and directory structure
            local_audio_dir = os.path.join(settings.MEDIA_ROOT, f"participant_{participant_id}", f"trial_{trial_number}")
            os.makedirs(local_audio_dir, exist_ok=True)
            local_audio_path = os.path.join(local_audio_dir, "background_audio.wav")

            # Save audio file locally
            if background_audio:
                with open(local_audio_path, 'wb') as f:
                    f.write(background_audio.read())
                logger.info(f"Saved background audio locally to {local_audio_path}")
            else:
                logger.error("No background audio received in the request.")
                return JsonResponse({'error': 'No background audio received.'}, status=400)

            # Upload audio file to S3
            s3_audio_path = f"participant_{participant_id}/trial_{trial_number}/background_audio.wav"
            upload_to_s3(local_audio_path, s3_audio_path)
            logger.info(f"Uploaded background audio to S3 path: {s3_audio_path}")

            # Structure for REPP Analysis, add nesting if needed
            stim_info = {
                'onsets': stim_onsets,
                'stim_shifted_onsets': stim_onsets,  # duplicate for any shifting logic in analysis
                'markers_onsets': [0.0, 1.0, 2.0],
                'onset_is_played': [True] * len(stim_onsets)
            }
            
            resp_info = {
                'onsets': tap_times
            }

            # Detailed logs to verify structure and types before analysis
            logger.info(f"REPP analysis parameters:\n - stim_info: {stim_info} (Type: {type(stim_info)})")
            logger.info(f" - resp_info: {resp_info} (Type: {type(resp_info)})")

            # Ensure paths are valid for REPP analysis
            output_plot_path = os.path.join(local_audio_dir, "output_plot.png")
            
            # Perform REPP Analysis with dictionaries as expected inputs
            config = sms_tapping  # Assuming sms_tapping is your config for REPP
            analysis = REPPAnalysis(config=config)

            # Run the analysis
            analysis_result = analysis.do_analysis(local_audio_path, output_plot_path, stim_info, resp_info)

            # Log and return analysis results
            if analysis_result:
                logger.info(f"Analysis result: {analysis_result}")
                return JsonResponse({'success': True, 'analysis_result': analysis_result})

            return JsonResponse({'error': 'REPP analysis did not return any result'}, status=500)

        except json.JSONDecodeError:
            logger.error("JSON decoding error for tap_times or stim_onsets.")
            return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
        except AssertionError as e:
            logger.error(f"Path type error: {e}")
            return JsonResponse({'error': f'Path type error: {str(e)}'}, status=500)
        except TypeError as e:
            logger.error(f"Type error in TrialView POST: {e}")
            return JsonResponse({'error': f'Type error: {str(e)}'}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error in TrialView POST: {e}")
            return JsonResponse({'error': str(e)}, status=500)








    def save_analysis_to_csv(self, csv_path, output, analysis_result, is_failed, trial_number, experiment_session):
        try:
            metrics = {
                'trial_number': trial_number,
                'complexity_level': experiment_session.complexity_level,
                'ear_order': experiment_session.ear_order,
                'trial_failed': is_failed.get('failed', False),
                'failure_reason': is_failed.get('reason', 'N/A'),
                'mean_asynchrony': analysis_result.get('mean_async_all', np.nan),
                'sd_asynchrony': analysis_result.get('sd_async_all', np.nan),
                'percent_responses_aligned': analysis_result.get('percent_resp_aligned_all', np.nan),
                'mean_stimulus_ioi': np.nanmean(output.get('stim_ioi', [])),
                'mean_response_ioi': np.nanmean(output.get('resp_ioi', [])),
            }
            df = pd.DataFrame([metrics])

            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                df_combined = pd.concat([df_existing, df], ignore_index=True)
            else:
                df_combined = df
            df_combined.to_csv(csv_path, index=False)

        except Exception as e:
            logger.error(f"Error saving CSV: {e}")
    
    def plot_trial_data(self, output, trial_number, output_dir):
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 6))
            plt.plot(output.get('stim_onsets_input', []), label="Stimulus Onsets")
            plt.plot(output.get('resp_onsets_detected', []), label="Response Onsets", linestyle='--')
            plt.legend()
            plt.title(f"Trial {trial_number} Stimulus vs Response Onsets")
            plt.xlabel("Time (ms)")
            plt.ylabel("Amplitude")
            plot_path = os.path.join(output_dir, f"trial_{trial_number}_plot.png")
            plt.savefig(plot_path)
            plt.close()

            s3_path = f"participant_plots/trial_{trial_number}_plot.png"
            upload_to_s3(plot_path, s3_path)
            logger.info(f"Uploaded plot to {s3_path}")

        except Exception as e:
            logger.error(f"Error plotting trial data: {e}")

def calculate_reaction_time(resp_onsets, stim_onsets):
    reaction_times = []
    for resp_time in resp_onsets:
        closest_stim_time = min(stim_onsets, key=lambda x: abs(x - resp_time))
        rt = resp_time - closest_stim_time
        reaction_times.append(rt)
    return reaction_times


# from django.views.generic import TemplateView, View
# from django.shortcuts import render, redirect, get_object_or_404
# from django.http import JsonResponse
# from django.utils import timezone
# from django.conf import settings
# from django.urls import reverse
# from .models import Trial, ExperimentSession, Participant, Analysis, RhythmSequence, TapRecord
# from .forms import ParticipantForm
# import json
# import random
# import os
# import numpy as np
# import pandas as pd
# from repp.analysis import REPPAnalysis
# from repp.config import sms_tapping
# from repp.stimulus import REPPStimulus
# from rest_framework import viewsets
# from .serializers import RhythmSequenceSerializer
# from urllib.parse import urljoin
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from rest_framework import status
# from django.utils.decorators import method_decorator
# from django.views.decorators.csrf import csrf_exempt
# import logging
# import matplotlib.pyplot as plt

# logger = logging.getLogger(__name__)

# from django.views.generic import TemplateView
# from .aws import upload_to_s3


# # Helper function to generate rhythm audio
# def generate_rhythm_audio(sequence, output_dir, filename):
#     repp_stimulus = REPPStimulus("generated_rhythm", config=sms_tapping)
#     stim_onsets = repp_stimulus.make_onsets_from_ioi(sequence)
#     audio, _stim_info, _stim_alignment = repp_stimulus.prepare_stim_from_onsets(stim_onsets)
    
#     marker_duration = 0.25
#     fs = sms_tapping.FS
#     marker = np.sin(2 * np.pi * 440 * np.linspace(0, marker_duration, int(fs * marker_duration)))
#     silence = np.zeros(int(0.2 * fs))
#     markers = np.concatenate([marker, silence, marker, silence, marker])

#     full_audio = np.concatenate([markers, audio, markers])
#     audio_path = os.path.join(output_dir, filename)
#     os.makedirs(output_dir, exist_ok=True)
#     REPPStimulus.to_wav(full_audio, audio_path, fs)
#     logger.info(f"Audio generated at: {audio_path}")
#     return audio_path

# class CompletionView(TemplateView):
#     template_name = 'experiment/complete.html'

# @method_decorator(csrf_exempt, name='dispatch')
# class TapRecordAPIView(APIView):
#     def post(self, request, trial_number):
#         try:
#             logger.info(f"Received data for trial {trial_number}: {request.data}")
#             participant_id = request.session.get('participant_id')
#             if not participant_id:
#                 logger.error("Participant ID not found in session.")
#                 return Response({'error': 'Participant not found in session'}, status=status.HTTP_400_BAD_REQUEST)

#             participant = get_object_or_404(Participant, id=participant_id)
#             experiment_session = ExperimentSession.objects.filter(participant=participant).first()
#             if not experiment_session:
#                 logger.error(f"No ExperimentSession found for Participant {participant_id}")
#                 return Response({'error': 'No ExperimentSession for participant'}, status=status.HTTP_404_NOT_FOUND)

#             trial = Trial.objects.filter(session=experiment_session, trial_number=trial_number).first()
#             if not trial:
#                 logger.error(f"No Trial with trial_number {trial_number} for session {experiment_session.id}")
#                 return Response({'error': 'Trial not found'}, status=status.HTTP_404_NOT_FOUND)

#             tap_times = request.data.get('tap_times', [])
#             if not isinstance(tap_times, list):
#                 logger.error("Invalid format for tap_times; expected a list.")
#                 return Response({'error': 'tap_times must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

#             TapRecord.objects.update_or_create(
#                 trial=trial,
#                 participant=participant,
#                 defaults={'tap_times': tap_times}
#             )

#             logger.info(f"Tap data saved successfully for trial {trial_number}")
#             return Response({'success': True}, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             logger.error(f"Error in TapRecordAPIView: {e}")
#             return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
#         return render(request, self.template_name, {'form': form})

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

#         context = {
#             'participant_id': participant_id,
#             'complexity_level': experiment_session.complexity_level,
#             'ear_order': experiment_session.ear_order,
#             'rhythm_sequence': rhythm_sequence,
#             'rhythm_sequence_data': {
#                 'name': rhythm_sequence.name,
#                 'sequence_data': rhythm_sequence.sequence_data,
#             },
#             'trial_number': 1
#         }
#         return render(request, self.template_name, context)




# class TrialView(View):
    # template_name = 'experiment/trials.html'

    # def get(self, request, trial_number):
    #     participant_id = request.session.get('participant_id')
    #     if not participant_id:
    #         return redirect('welcome_home')

    #     participant = get_object_or_404(Participant, id=participant_id)
    #     experiment_session = ExperimentSession.objects.get(participant=participant)
    #     rhythm_sequence = RhythmSequence.objects.get(id=request.session['rhythm_sequence_id'])

    #     audio_dir = os.path.join(settings.MEDIA_ROOT, 'rhythm_audios')
    #     audio_filename = f"rhythm_sequence_{rhythm_sequence.id}.wav"
    #     audio_path = os.path.join(audio_dir, audio_filename)

    #     # Generate the audio file if it doesn't exist
    #     if not os.path.exists(audio_path):
    #         logger.debug(f"Generating audio file for {audio_filename}")
    #         generate_rhythm_audio(rhythm_sequence.sequence_data, audio_dir, audio_filename)

    #     audio_url = os.path.join(settings.MEDIA_URL, f"rhythm_audios/{audio_filename}")
    #     context = {
    #         'participant_id': participant_id,
    #         'complexity_level': experiment_session.complexity_level,
    #         'ear_order': experiment_session.ear_order,
    #         'rhythm_sequence': rhythm_sequence,
    #         'audio_url': audio_url,
    #         'trial_number': trial_number,
    #     }
    #     return render(request, self.template_name, context)

#     def post(self, request, trial_number):
#         try:
#             data = json.loads(request.body)
#             tap_times = data.get('tap_times')
#             stim_onsets = data.get('stim_onsets')
#             if not tap_times or not stim_onsets:
#                 return JsonResponse({'error': 'Invalid data received'}, status=400)

#             participant_id = request.session.get('participant_id')
#             participant = get_object_or_404(Participant, id=participant_id)
#             experiment_session = get_object_or_404(ExperimentSession, participant=participant)
#             rhythm_sequence = RhythmSequence.objects.get(id=request.session['rhythm_sequence_id'])

#             trial, created = Trial.objects.get_or_create(
#                 session=experiment_session,
#                 participant=participant,
#                 trial_number=trial_number,
#                 defaults={'rhythm_sequence': rhythm_sequence}
#             )

#             TapRecord.objects.create(trial=trial, participant=participant, tap_times=tap_times)

#             stim_info = {
#                 'onsets': stim_onsets,
#                 'stim_shifted_onsets': stim_onsets,
#                 'markers_onsets': [0.0, 1.0, 2.0],
#                 'onset_is_played': [True] * len(stim_onsets)
#             }
#             resp_info = {'onsets': tap_times}

#             analysis = REPPAnalysis(config=sms_tapping)
#             output_dir = os.path.join(settings.BASE_DIR, 'output', f"participant_{participant_id}")
#             os.makedirs(output_dir, exist_ok=True)
#             output_plot_path = os.path.join(output_dir, f"trial_{trial_number}_output.png")

#             output, analysis_result, is_failed = analysis.do_analysis(stim_info, resp_info, f"trial_{trial_number}", output_plot_path)

#             reaction_times = calculate_reaction_time(tap_times, stim_onsets)
#             Analysis.objects.create(trial=trial, reaction_time=json.dumps(reaction_times), response_data=json.dumps(tap_times))

#             csv_path = os.path.join(output_dir, 'participant_analysis.csv')
#             self.save_analysis_to_csv(csv_path, output, analysis_result, is_failed, trial_number, experiment_session)
#             self.plot_trial_data(output, trial_number, output_dir)

#             return JsonResponse({'success': True})

#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
#         except Exception as e:
#             logger.error(f"Error in TrialView POST: {e}")
#             return JsonResponse({'success': False, 'error': str(e)}, status=500)

#     def save_analysis_to_csv(self, csv_path, output, analysis_result, is_failed, trial_number, experiment_session):
#         try:
#             metrics = {
#                 'trial_number': trial_number,
#                 'complexity_level': experiment_session.complexity_level,
#                 'ear_order': experiment_session.ear_order,
#                 'trial_failed': is_failed.get('failed', False),
#                 'failure_reason': is_failed.get('reason', 'N/A'),
#                 'mean_asynchrony': analysis_result.get('mean_async_all', np.nan),
#                 'sd_asynchrony': analysis_result.get('sd_async_all', np.nan),
#                 'percent_responses_aligned': analysis_result.get('percent_resp_aligned_all', np.nan),
#                 'mean_stimulus_ioi': np.nanmean(output.get('stim_ioi', [])),
#                 'mean_response_ioi': np.nanmean(output.get('resp_ioi', [])),
#             }
#             df = pd.DataFrame([metrics])

#             if os.path.exists(csv_path):
#                 df_existing = pd.read_csv(csv_path)
#                 df_combined = pd.concat([df_existing, df], ignore_index=True)
#             else:
#                 df_combined = df
#             df_combined.to_csv(csv_path, index=False)

#             s3_path = f"participant_data/{os.path.basename(csv_path)}"
#             upload_to_s3(csv_path, s3_path)

#         except Exception as e:
#             logger.error(f"Error saving CSV: {e}")

#     def plot_trial_data(self, output, trial_number, output_dir):
#         try:
#             plt.figure(figsize=(10, 6))
#             plt.plot(output.get('stim_onsets_input', []), label="Stimulus Onsets")
#             plt.plot(output.get('resp_onsets_detected', []), label="Response Onsets", linestyle='--')
#             plt.legend()
#             plt.title(f"Trial {trial_number} Stimulus vs Response Onsets")
#             plt.xlabel("Time (ms)")
#             plt.ylabel("Amplitude")
#             plot_path = os.path.join(output_dir, f"trial_{trial_number}_plot.png")
#             plt.savefig(plot_path)
#             plt.close()

#             s3_path = f"participant_plots/trial_{trial_number}_plot.png"
#             upload_to_s3(plot_path, s3_path)

#         except Exception as e:
#             logger.error(f"Error plotting trial data: {e}")
        

# def calculate_reaction_time(resp_onsets, stim_onsets):
#     reaction_times = []
#     for resp_time in resp_onsets:
#         closest_stim_time = min(stim_onsets, key=lambda x: abs(x - resp_time))
#         rt = resp_time - closest_stim_time
#         reaction_times.append(rt)
#     return reaction_times
