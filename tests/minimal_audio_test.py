import os
import time
import threading
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from eden_utils import play_sound, play_random_sound

from dotenv import load_dotenv
load_dotenv('.env')

def input_callback(audio_bytes):
    """Callback function for audio input"""
    print("Audio input received:", len(audio_bytes), "bytes")

def main():
    # 1. First start playing background ambient sound with pygame (async)
    print("Starting background ambient sound...")
    ambient_thread = play_sound("tests/assets/audio/ambient/02.flac", async_play=True, loop=True)
    time.sleep(2)  # Let ambient sound play for a moment
    
    # 2. Initialize DefaultAudioInterface
    print("Initializing DefaultAudioInterface...")
    audio_interface = DefaultAudioInterface()
    audio_interface.start(input_callback)
    
    # 3. Play a test sound through DefaultAudioInterface
    print("Playing test audio through DefaultAudioInterface...")
    # Create a simple sine wave as test audio (1 second)
    import math
    import struct
    
    sample_rate = 16000
    duration = 1  # seconds
    frequency = 440  # A4 note
    
    samples = []
    for i in range(int(sample_rate * duration)):
        sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(struct.pack('<h', sample))
    
    test_audio = b''.join(samples)
    audio_interface.output(test_audio)
    time.sleep(2)  # Wait for test audio to complete
    
    # 4. Play another pygame sound while DefaultAudioInterface is active
    print("Playing gong sound with pygame while DefaultAudioInterface is active...")
    gong_thread = play_random_sound("tests/assets/audio/gongs", async_play=True)
    time.sleep(3)  # Let gong sound play
    
    # 5. Test interruption
    print("Playing another audio through DefaultAudioInterface...")
    # Lower frequency for second test sound
    frequency = 220  # A3 note
    
    samples = []
    for i in range(int(sample_rate * duration * 4)):  # 4 seconds this time
        sample = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(struct.pack('<h', sample))
    
    test_audio2 = b''.join(samples)
    audio_interface.output(test_audio2)
    
    time.sleep(1)  # Let it play briefly
    print("Interrupting DefaultAudioInterface playback...")
    audio_interface.interrupt()
    
    # 6. Clean up
    time.sleep(2)
    print("Stopping DefaultAudioInterface...")
    audio_interface.stop()
    
    # Let background sounds continue for a moment after interface is stopped
    time.sleep(3)
    print("Test completed, exiting.")

if __name__ == "__main__":
    main() 