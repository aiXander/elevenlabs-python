import os
import time
import threading
import pygame
import pyaudio
import math
import struct
import wave
import sys
import atexit
import multiprocessing
from multiprocessing import Process, Queue, Event

# Global variables to track state and resources
pygame_initialized = False
pygame_sounds = {}
pygame_channels = {}

# ---------- Initial Pygame Setup ----------
def setup_pygame():
    global pygame_initialized
    if not pygame_initialized:
        # Initialize pygame - this is done once before any PyAudio work
        pygame.init()
        
        # Configure mixer specifically for this application
        # 44.1kHz, 16-bit signed, stereo with 1024 buffer size
        pygame.mixer.quit()  # Ensure it's shut down before re-initializing
        pygame.mixer.pre_init(44100, -16, 2, 1024)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)  # Allow 16 sounds at once
        
        # Register cleanup function
        atexit.register(pygame_cleanup)
        pygame_initialized = True

def pygame_cleanup():
    global pygame_initialized, pygame_sounds, pygame_channels
    if pygame_initialized:
        # Stop all sounds
        pygame.mixer.stop()
        # Release resources
        pygame_sounds = {}
        pygame_channels = {}
        pygame.mixer.quit()
        pygame_initialized = False

# ---------- Pygame Sound Functions ----------
def play_sound(filepath, loop=False, channel_num=None, duration=None):
    """Play a sound using pygame mixer with channel control"""
    global pygame_sounds, pygame_channels
    
    # Ensure pygame is set up
    setup_pygame()
    
    # Load the sound if not already loaded
    if filepath not in pygame_sounds:
        pygame_sounds[filepath] = pygame.mixer.Sound(filepath)
    
    # Get the appropriate channel
    if channel_num is not None:
        if channel_num not in pygame_channels:
            pygame_channels[channel_num] = pygame.mixer.Channel(channel_num)
        channel = pygame_channels[channel_num]
    else:
        # Find first available channel
        for i in range(pygame.mixer.get_num_channels()):
            test_channel = pygame.mixer.Channel(i)
            if not test_channel.get_busy():
                channel = test_channel
                pygame_channels[i] = channel
                break
        else:
            # All channels busy, use channel 0
            channel = pygame.mixer.Channel(0)
            pygame_channels[0] = channel
    
    # Play the sound
    channel.play(pygame_sounds[filepath], loops=-1 if loop else 0)
    
    # If duration is specified, set up a timer to stop the sound
    if duration is not None:
        def stop_after_duration():
            time.sleep(duration)
            if channel.get_busy():
                channel.stop()
        
        timer_thread = threading.Thread(target=stop_after_duration)
        timer_thread.daemon = True
        timer_thread.start()
    
    return channel

def stop_sound(channel_num=None):
    """Stop a sound on a specific channel or all channels"""
    global pygame_channels
    
    if channel_num is not None and channel_num in pygame_channels:
        pygame_channels[channel_num].stop()
    else:
        pygame.mixer.stop()  # Stop all channels

# ---------- PyAudio Process Functions ----------
def pyaudio_process(input_queue, output_queue, stop_event):
    """Process function for handling PyAudio in a separate process"""
    # Prevent pygame initialization in this process
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    
    p = pyaudio.PyAudio()
    
    def in_callback(in_data, frame_count, time_info, status):
        input_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    # Open streams
    in_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4000,
        stream_callback=in_callback,
        start=True,
    )
    
    out_stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        output=True,
        frames_per_buffer=1000,
        start=True,
    )
    
    # Main process loop
    while not stop_event.is_set():
        try:
            # Check for output data
            if not output_queue.empty():
                audio_data = output_queue.get_nowait()
                out_stream.write(audio_data)
            time.sleep(0.01)  # Small sleep to prevent CPU overuse
        except Exception as e:
            print(f"PyAudio process error: {e}")
            break
    
    # Cleanup
    in_stream.stop_stream()
    in_stream.close()
    out_stream.stop_stream()
    out_stream.close()
    p.terminate()

# ---------- Mock DefaultAudioInterface ----------
class MinimalAudioInterface:
    """A minimal version of DefaultAudioInterface for testing"""
    def __init__(self):
        self.is_agent_speaking = False
        self.speaking_lock = threading.Lock()
        self.last_output_time = 0
        self.output_queue = Queue()
        self.input_queue = Queue()
        self.stop_event = Event()
        self.process = None

    def start(self, input_callback=None):
        # Audio input callback
        self.input_callback = input_callback
        
        # Start PyAudio process
        self.process = Process(
            target=pyaudio_process,
            args=(self.input_queue, self.output_queue, self.stop_event)
        )
        self.process.start()
        
        # Start input processing thread
        self.input_thread = threading.Thread(target=self._process_input)
        self.input_thread.daemon = True
        self.input_thread.start()

    def stop(self):
        if self.stop_event is not None:
            self.stop_event.set()
        if self.process is not None:
            self.process.join(timeout=1.0)
        if self.input_thread is not None and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)

    def output(self, audio):
        with self.speaking_lock:
            self.is_agent_speaking = True
            print("Interface is speaking: Locking")
        self.output_queue.put(audio)

    def interrupt(self):
        # Clear the output queue to stop any audio that is currently playing
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except:
                pass
        with self.speaking_lock:
            print("Interface done speaking: unlocking")
            self.is_agent_speaking = False

    def _process_input(self):
        """Process input data from the PyAudio process"""
        while not self.stop_event.is_set():
            try:
                if not self.input_queue.empty():
                    audio_data = self.input_queue.get_nowait()
                    if self.input_callback and not self.is_agent_speaking:
                        self.input_callback(audio_data)
                time.sleep(0.01)
            except Exception as e:
                print(f"Input processing error: {e}")
                break

# ---------- Test Audio Generation ----------
def generate_sine_wave(frequency, duration, sample_rate=16000):
    """Generate a simple sine wave for testing audio output"""
    samples = []
    for i in range(int(sample_rate * duration)):
        sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(struct.pack('<h', sample))
    
    return b''.join(samples)

# ---------- Main Test Function ----------
def main():
    # 1. Set up and play background sound with pygame
    print("Setting up pygame...")
    setup_pygame()
    
    print("Starting background sound with pygame...")
    background_audio = "/Users/xandersteenbrugge/Documents/GitHub/Dewata_Nawa_Sanga/elevenlabs-python/tests/assets/audio/ambient/01.flac"
    bg_channel = play_sound(background_audio, loop=True, channel_num=0)
    print("Background sound started on channel 0")
    time.sleep(2)  # Let it play for a moment
    
    # 2. Initialize audio interface AFTER pygame is already playing
    print("\nInitializing audio interface...")
    def input_callback(audio_bytes):
        print("Audio input received:", len(audio_bytes), "bytes")
    
    audio_interface = MinimalAudioInterface()
    audio_interface.start(input_callback)
    time.sleep(1)
    
    # Check if background is still playing
    print("Checking if background sound is still playing...")
    if pygame_channels[0].get_busy():
        print("✅ Background sound is still playing")
    else:
        print("❌ Background sound stopped")
        # Try to restart it
        bg_channel = play_sound(background_audio, loop=True, channel_num=0)
    
    # 3. Play test sound through audio interface
    print("\nPlaying test audio through interface...")
    test_audio = generate_sine_wave(880, 2)  # 880Hz for 2 seconds
    audio_interface.output(test_audio)
    time.sleep(3)
    
    # 4. Play another pygame sound alongside
    print("\nPlaying additional pygame sound while interface is active...")
    
    # Create the test file path for writing
    test_audio2_path = "test_additional.wav"
    sample_rate = 44100
    nframes = sample_rate * 2
    with wave.open(test_audio2_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        # Write a higher pitched sine wave
        for i in range(nframes):
            value = int(32767 * math.sin(2 * math.pi * 660 * i / sample_rate))
            wf.writeframes(struct.pack('<h', value))
    
    # Play on channel 1 with duration
    additional_channel = play_sound(test_audio2_path, channel_num=1, duration=3)
    print("Additional sound started on channel 1")
    time.sleep(3)
    
    # 5. Test interruption
    print("\nPlaying longer audio through interface...")
    long_audio = generate_sine_wave(440, 5)  # 440Hz for 5 seconds
    audio_interface.output(long_audio)
    
    time.sleep(1)  # Let it play briefly
    print("Interrupting interface playback...")
    audio_interface.interrupt()
    
    # 6. Play one more sound to verify multiple sounds work
    print("\nPlaying third pygame sound to verify multiple async sounds...")
    test_audio3_path = "test_third.wav"
    with wave.open(test_audio3_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        
        # Write a different pitched sine wave
        for i in range(nframes):
            value = int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wf.writeframes(struct.pack('<h', value))
    
    # Play on channel 2 with duration
    third_channel = play_sound(test_audio3_path, channel_num=2, duration=3)
    print("Third sound started on channel 2")
    time.sleep(3)
    
    # 7. Check all sounds
    print("\nChecking all sounds:")
    for channel_num, channel in pygame_channels.items():
        if channel.get_busy():
            print(f"Channel {channel_num} is playing")
        else:
            print(f"Channel {channel_num} is silent")
    
    # 8. Clean up
    time.sleep(2)
    print("\nStopping audio interface...")
    audio_interface.stop()
    
    # Fade out pygame sounds gradually
    print("Fading out pygame sounds...")
    for channel_num in pygame_channels:
        if pygame_channels[channel_num].get_busy():
            pygame_channels[channel_num].fadeout(1000)  # 1 second fadeout
    
    # Let things clean up
    time.sleep(2)
    
    # Clean up test files
    for file_path in ["test_additional.wav", "test_third.wav"]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Removed {file_path}")
            except Exception as e:
                print(f"Could not remove {file_path}: {e}")
    
    print("Test completed successfully!")

if __name__ == "__main__":
    main() 