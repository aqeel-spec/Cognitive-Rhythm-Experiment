import os
import sounddevice as sd
import matplotlib as mpl
import matplotlib.pyplot as plt
import json
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import numpy as np
import scipy.signal
import random
import pandas as pd
import glob

from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from repp.analysis import REPPAnalysis

def create_participant_analysis_csv(output, analysis_result, is_failed, trial_num, output_dir, stimulus_num, allocation):
    """
    Create or update a CSV file with analysis metrics for all trials of a participant.
    
    Parameters:
    output: dict - The output data from REPP analysis
    analysis_result: dict - The analysis results from REPP analysis
    is_failed: dict - Information about whether the trial failed
    trial_num: int - Trial number
    output_dir: str - Directory path for participant output
    stimulus_num: int - Current stimulus number (1 or 2)
    allocation: str - Participant's experimental allocation
    """
    # Calculate metrics from the output data
    metrics = {
        'trial_number': trial_num,
        'stimulus_number': stimulus_num,
        'allocation': allocation,
        'trial_failed': is_failed['failed'],
        'failure_reason': is_failed['reason'],
        
        # Stimulus metrics
        'total_stimuli': len(output['stim_onsets_input']),
        'detected_stimuli': len([x for x in output['stim_onsets_aligned'] if not np.isnan(x)]),
        
        # Response metrics
        'total_responses': len(output['resp_onsets_detected']),
        'aligned_responses': len([x for x in output['resp_onsets_aligned'] if not np.isnan(x)]),
        
        # Timing metrics
        'mean_asynchrony': analysis_result['mean_async_all'],
        'sd_asynchrony': analysis_result['sd_async_all'],
        'percent_responses': analysis_result['ratio_resp_to_stim'],
        'percent_responses_aligned': analysis_result['percent_resp_aligned_all'],
        
        # IOI metrics
        'mean_stimulus_ioi': np.nanmean([x for x in output['stim_ioi'] if not np.isnan(x)]),
        'mean_response_ioi': np.nanmean([x for x in output['resp_ioi'] if not np.isnan(x)]),
        
        # Marker metrics
        'num_markers': analysis_result['num_markers_onsets'],
        'detected_markers': analysis_result['num_markers_detected'],
        'marker_detection_rate': analysis_result['markers_status'],
        'max_marker_error': analysis_result['markers_max_difference'],
        
        # Performance metrics
        'percent_bad_taps': analysis_result['percent_of_bad_taps_all'],
        
        # Additional metrics for played vs not played onsets
        'mean_async_played': analysis_result['mean_async_played'],
        'sd_async_played': analysis_result['sd_async_played'],
        'percent_resp_played': analysis_result['percent_response_aligned_played'],
        'mean_async_notplayed': analysis_result['mean_async_notplayed'],
        'sd_async_notplayed': analysis_result['sd_async_notplayed'],
        'percent_resp_notplayed': analysis_result['percent_response_aligned_notplayed']
    }
    
    csv_path = os.path.join(output_dir, 'participant_analysis.csv')
    
    # If file exists, read it and append new data
    if os.path.exists(csv_path):
        df_existing = pd.read_csv(csv_path)
        df_new = pd.DataFrame([metrics])
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = pd.DataFrame([metrics])
    
    # Sort by stimulus number and trial number
    df_combined = df_combined.sort_values(['stimulus_number', 'trial_number'])
    
    # Save to CSV
    df_combined.to_csv(csv_path, index=False)
    
    return metrics

class RhythmExperimentGUI:
    def __init__(self, master):
        self.master = master
        master.title("Rhythm Experiment")
        master.geometry("500x400")

        # Initialize variables
        self.participant_id = tk.StringVar()
        self.current_step = 0
        self.first_ear = None
        self.current_stimulus = 1
        self.playback_count = 0
        self.current_trial = 0

        # Setup experiment configuration first
        self.setup_experiment()
        # Then setup GUI
        self.setup_gui()

    def setup_experiment(self):
        self.config = sms_tapping

        # Define rhythms
        self.simple_rhythms = [
            [0, 520, 520, 520, 260, 260, 520, 520],
            [0, 520, 260, 260, 520, 260, 260, 520, 520]
        ]
        self.complex_rhythms = [
            [0, 130, 260, 390, 260, 130, 260, 390, 260],
            [0, 390, 130, 260, 520, 260, 130, 390]
        ]

        # Random assignments
        self.complexity = random.choice(['simple', 'complex'])
        self.first_ear = random.choice(['right', 'left'])
        self.sequence_order = random.choice([0, 1])

        # Set rhythms based on complexity
        self.rhythms = self.simple_rhythms if self.complexity == 'simple' else self.complex_rhythms

    def setup_gui(self):
        self.frame = ttk.Frame(self.master, padding="10")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        welcome_text = """
        This experiment investigates rhythm perception and synchronization abilities.
        
        Your participation will take approximately 15 minutes. You will hear rhythmic patterns through headphones and tap along with them.

        Your data will be saved anonymously using a participant ID. You may stop participating at any time by closing this window.

        By clicking 'Start', you agree to participate in this experiment.
        
        Thank you for your time
        
        Adi and Natalie"""

        self.label = ttk.Label(self.frame, text=welcome_text, wraplength=400)
        self.label.grid(row=0, column=0, pady=10)

        self.entry = ttk.Entry(self.frame, textvariable=self.participant_id)
        self.entry.grid(row=1, column=0, pady=5)
        self.entry.grid_remove()

        self.next_button = ttk.Button(self.frame, text="Start", command=self.start_experiment)
        self.next_button.grid(row=2, column=0, pady=10)


    def start_experiment(self):
        """Initial step to start the experiment"""
        self.label.config(text="Please enter your participant ID (9 digits):")
        self.entry.grid()  # Show the entry box
        self.next_button.config(text="Submit", command=self.validate_participant_id)


    def validate_participant_id(self):
        pid = self.participant_id.get()
        if not (pid.isdigit() and len(pid) == 9):
            messagebox.showerror("Error", "Please enter a valid 9-digit ID")
            return

        # Create output directory
        self.output_dir = os.path.join('output', self.participant_id.get())
        os.makedirs(self.output_dir, exist_ok=True)

        # Save allocation
        allocation = f"{self.complexity}-stimulus{self.sequence_order + 1}-{self.first_ear}ear"
        with open(os.path.join(self.output_dir, 'allocation.txt'), 'w') as f:
            f.write(allocation)

        self.entry.grid_remove()  # Remove the entry box
        self.show_initial_instructions()

    def setup_output_directories(self):
        self.output_dir = os.path.join('output', self.participant_id.get())
        os.makedirs(self.output_dir, exist_ok=True)

    def show_initial_instructions(self):
        instructions = """In this experiment, you will hear and tap along with 2 different rhythms.

    1. First, each rhythm will be played twice for practice - just listen, no tapping needed.
    2. Then, you will tap along with each rhythm for multiple trials.
    3. Use your right hand index finger to tap in sync with the beats.
    4. The rhythms will be played through one ear at a time.
    5. Each rhythm starts and ends with 3 marker beats - you don't need to tap these."""

        self.label.config(text=instructions)
        self.next_button.config(text="Next", command=self.show_tapping_instructions)

    def show_tapping_instructions(self):
        instructions = """Important tapping instructions:

    1. Use ONLY your right hand's index finger
    2. Tap on the laptop surface next to the touchpad
    3. Tap gently but firmly with your fingertip
    4. DO NOT tap on:
    - Keys
    - Mouse buttons
    - Touchpad"""

        self.label.config(text=instructions)
        self.next_button.config(command=self.start_headphone_check)

    def start_headphone_check(self):
        self.label.config(text="""Right Earbud Check:

    At first, please make sure to insert your earbuds properly.
    1. You will hear a single beat
    2. Tap once when you hear it
    3. The sound should come from your RIGHT ear
    4. If you hear it in your LEFT ear, please switch your earbuds""")
        self.next_button.config(text="Start Check", command=self.check_right_ear)

    def update_progress(self):
        """Update the progress bar based on current trial block (6 trials)"""
        trials_per_block = 6
        
        # Calculate progress for current block of 6 trials
        progress = (self.current_trial % 12) / 12 * 100
        self.progress['value'] = progress

    def check_right_ear(self):
        self.next_button.grid_remove()
        self.perform_ear_check('right')

    def check_left_ear(self):
        self.label.config(text="Left Earbud Check\n"
                               "You will hear a beat. Please tap when you hear it.\n")
        self.next_button.config(text="Start Check", command=self.perform_left_check)
        self.next_button.grid()

    def perform_left_check(self):
        self.next_button.grid_remove()
        self.perform_ear_check('left')

    def perform_ear_check(self, ear):
        """
        Perform ear check with longer sound duration
        """
        duration = 1.5  # Increased from 1
        fs = 44100
        t = np.linspace(0, duration, int(fs * duration))
        test_sound = np.sin(2 * np.pi * 440 * t)  # 440 Hz tone

        # Extended silence before and after
        silence = np.zeros(int(0.75 * fs))  # Increased from 0.5
        full_audio = np.concatenate((silence, test_sound, silence))

        if ear == 'left':
            stereo_audio = np.vstack((full_audio, np.zeros_like(full_audio)))
        else:  # right ear
            stereo_audio = np.vstack((np.zeros_like(full_audio), full_audio))

        recording = sd.playrec(stereo_audio.T, fs, channels=1)
        sd.wait()

        tap_detected = self.detect_tap(recording.flatten(), fs)

        if tap_detected:
            if ear == 'right':
                self.check_left_ear()
            else:
                self.start_rhythm_practice()
        else:
            self.label.config(text=f"No tap detected for {ear} ear. Please try again with a firmer tap.")
            if ear == 'right':
                self.next_button.config(text="Retry Right Check", command=self.check_right_ear)
            else:
                self.next_button.config(text="Retry Left Check", command=self.perform_left_check)
            self.next_button.grid()

    def detect_tap(self, audio, fs):
        """
        Detect tap with much more lenient parameters
        """
        # High-pass filter to remove low frequency noise
        nyq = 0.5 * fs
        high = 30 / nyq  # Lowered from 50 to be more lenient
        b, a = scipy.signal.butter(4, high, btype='high')
        filtered_audio = scipy.signal.filtfilt(b, a, audio)

        # Get envelope
        analytic_signal = scipy.signal.hilbert(filtered_audio)
        envelope = np.abs(analytic_signal)

        # Smooth envelope with wider window
        window_size = int(0.05 * fs)  # Increased from 0.03 for more smoothing
        envelope_smooth = np.convolve(envelope, np.ones(window_size) / window_size, mode='same')

        # Find peaks with much lower threshold and wider distance
        peaks, _ = scipy.signal.find_peaks(envelope_smooth, 
                                        height=0.01,  # Lowered from 0.03
                                        distance=int(0.05 * fs))  # Decreased from 0.1

        # Wider time window for valid peaks
        beat_time = 0.5
        valid_peaks = peaks[(peaks > int((beat_time - 0.5) * fs)) &  # Increased from 0.4
                        (peaks < int((beat_time + 0.5) * fs))]  # Increased from 0.4

        return len(valid_peaks) > 0

    def start_rhythm_practice(self):
        ear = self.first_ear if self.current_stimulus == 1 else ('left' if self.first_ear == 'right' else 'right')
        rhythm = self.rhythms[self.sequence_order if self.current_stimulus == 1 else 1 - self.sequence_order]

        practice_text = f"""You will now hear Rhythm {self.current_stimulus} of 2.

    1. The rhythm will play twice for practice
    2. Just LISTEN during practice - do not tap yet
    3. Notice the 3 marker beats at the start and end
    4. After practice is finished, you'll tap along this rhythm for 12 trials

    Press 'Start Practice' when ready."""

        self.label.config(text=practice_text)
        self.current_repp_stimulus = REPPStimulus(f"rhythm_{self.current_stimulus}", config=self.config)
        stim_onsets = self.current_repp_stimulus.make_onsets_from_ioi(rhythm)
        self.stim_prepared, self.stim_info, _ = self.current_repp_stimulus.prepare_stim_from_onsets(stim_onsets)

        self.next_button.config(text="Start Practice", command=self.play_practice)
        self.next_button.grid()

    def play_practice(self):
        self.next_button.grid_remove()

        def play_twice():
            for i in range(2):
                self.label.config(text=f"""Playing practice for the  {i + 1}/2 time.
                    Just LISTEN during practice - do not tap yet
                    Notice the 3 marker beats at the start and end""")
                sd.play(self.stim_prepared, self.config.FS)
                sd.wait()
                if i == 0:
                    self.master.after(1000)

            self.master.after(1000, self.start_trials)

        threading.Thread(target=play_twice).start()

    def start_trials(self):
        self.current_trial = 0
        ear = self.first_ear if self.current_stimulus == 1 else ('left' if self.first_ear == 'right' else 'right')

        self.label.config(text=f"""Ready to start Rhythm {self.current_stimulus} trials.

    1. Tap along as accurately as possible with EACH beat
    2. The rhythm will be played only in your {ear.upper()} ear
    3. Remember to ignore the 3 marker beats at start/end
    4. Please remember to tap with your right index finger
    5. This is trial 1 of 12

    Press 'Start Recording' when ready.""")
        
        self.next_button.config(text="Start Recording", command=self.run_trial)
        self.next_button.grid()


    def run_trial(self):
            self.next_button.grid_remove()

            if self.current_trial < 12: #12
                self.label.config(text=f"""Recording trial {self.current_trial + 2}/12
                
                1. Tap along as accurately as possible with EACH beat
                2. Remember to ignore the 3 marker beats at start/end
                3. remember to tap with your right index finger
                
                you will have a 15 sec break after the 6th trial""")

                # Create ear-specific stereo audio
                ear = self.first_ear if self.current_stimulus == 1 else ('left' if self.first_ear == 'right' else 'right')
                stereo_stim = np.zeros((len(self.stim_prepared), 2))
                
                # Put the stimulus in the correct ear
                if ear == 'right':
                    stereo_stim[:, 1] = self.stim_prepared.flatten()  # Right channel
                else:  # left ear
                    stereo_stim[:, 0] = self.stim_prepared.flatten()  # Left channel

                # Record taps while playing stimulus
                tapping_recording = sd.playrec(stereo_stim, 
                                            samplerate=self.config.FS,
                                            channels=1)  # Record in mono
                sd.wait()

                # Normalize the tapping recording
                tapping_recording = tapping_recording / np.max(np.abs(tapping_recording)) * 0.9

                # Get the mono stimulus for combining
                mono_stimulus = self.stim_prepared.flatten()
                mono_stimulus = mono_stimulus / np.max(np.abs(mono_stimulus)) * 0.9

                # Combine the recordings
                # Add the stimulus and tapping recordings together
                combined_recording = tapping_recording + mono_stimulus.reshape(-1, 1)
                
                # Normalize the combined recording to prevent clipping
                combined_recording = combined_recording / np.max(np.abs(combined_recording)) * 0.9

                # Create directory for this trial
                trial_dir = os.path.join(self.output_dir, f'stimulus_{self.current_stimulus}',
                                        f'trial_{self.current_trial + 1}')
                os.makedirs(trial_dir, exist_ok=True)

                # Save both the original tapping and the combined recording
                tapping_path = os.path.join(trial_dir, f'tapping_only_trial_{self.current_trial + 1}.wav')
                combined_path = os.path.join(trial_dir, f'recording_trial_{self.current_trial + 1}.wav')
                
                REPPStimulus.to_wav(tapping_recording, tapping_path, self.config.FS)
                REPPStimulus.to_wav(combined_recording, combined_path, self.config.FS)

                # Debug plots
                plt.figure(figsize=(10, 12))
                
                plt.subplot(3, 1, 1)
                plt.plot(tapping_recording)
                plt.title("Tapping Recording")
                
                plt.subplot(3, 1, 2)
                plt.plot(mono_stimulus)
                plt.title("Stimulus")
                
                plt.subplot(3, 1, 3)
                plt.plot(combined_recording)
                plt.title("Combined Recording")
                
                plt.tight_layout()
                plt.savefig(os.path.join(trial_dir, f'waveform_trial_{self.current_trial + 1}.png'))
                plt.close()

                try:
                    # Analyze using REPP with the combined recording
                    analysis = REPPAnalysis(config=self.config)
                    output, analysis_result, is_failed = analysis.do_analysis(
                        self.stim_info,
                        combined_path,  # Use the combined recording for analysis
                        f"trial_{self.current_trial + 1}",
                        os.path.join(trial_dir, f'plot_trial_{self.current_trial + 1}.png')
                    )

                # Save numerical data
                    with open(os.path.join(trial_dir, f'numerical_data_trial_{self.current_trial + 1}.json'), 'w') as f:
                        json.dump(output, f)


                    # Get allocation from file
                    with open(os.path.join(self.output_dir, 'allocation.txt'), 'r') as f:
                        allocation = f.read().strip()

                # Create and save participant analysis CSV
                    create_participant_analysis_csv(
                        output=output,
                        analysis_result=analysis_result,
                        is_failed=is_failed,
                        trial_num=self.current_trial + 1,
                        output_dir=self.output_dir,
                        stimulus_num=self.current_stimulus,
                        allocation=allocation
                    )

                    self.current_trial += 1

                    # Handle breaks
                    if self.current_trial == 6:  # Break after 2nd trial
                        self.take_break(15)
                    elif self.current_trial == 12:  # After 4th trial
                        if self.current_stimulus == 1:
                            self.take_break(120)
                        else:
                            self.experiment_complete()
                    else:
                        self.master.after(1000, self.run_trial)

                except Exception as e:
                    error_msg = f"Analysis error in trial {self.current_trial + 1}: {str(e)}"
                    with open(os.path.join(trial_dir, 'error_log.txt'), 'w') as f:
                        f.write(error_msg)
                    
                    messagebox.showerror("Analysis Error", 
                                    "There was an error analyzing the trial. Please check the microphone levels and try again.")
                    
                    self.next_button.config(text="Retry Trial", command=self.run_trial)
                    self.next_button.grid()
    

    def take_break(self, duration):
        self.remaining_time = duration
        self.update_break_timer()

    def update_break_timer(self):
        if self.remaining_time > 0:
            self.label.config(text=f"Break time remaining: {self.remaining_time} seconds\n"
                                   f"Press 'Continue' to skip timer")
            self.remaining_time -= 1
            self.timer_id = self.master.after(1000, self.update_break_timer)
        else:
            self.continue_after_break()

        self.next_button.config(text="Continue", command=self.continue_after_break)
        self.next_button.grid()

    def continue_after_break(self):
        if hasattr(self, 'timer_id'):
            self.master.after_cancel(self.timer_id)

        if self.current_trial == 6: # needs to be changed
            self.label.config(text=f"""Recording trial 7/12
                
                    1. Tap along as accurately as possible with EACH beat
                    2. Remember to ignore the 3 marker beats at start/end
                    3. remember to tap with your right index finger""")
            self.run_trial()
        else:  # After stimulus 1
            self.current_stimulus = 2
            self.start_rhythm_practice()    


    def experiment_complete(self):
        """Handle experiment completion"""
        completion_text = """Experiment Complete!

        Thank you for your participation.
        
        You may now close this window.
        
        Your data has been saved successfully."""

        self.label.config(text=completion_text)
        self.next_button.config(text="Close", command=self.master.destroy)
        self.next_button.grid()

def main():
    root = tk.Tk()
    app = RhythmExperimentGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
