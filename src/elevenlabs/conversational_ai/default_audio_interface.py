from typing import Callable
import queue
import threading

from .conversation import AudioInterface


class DefaultAudioInterface(AudioInterface):
    INPUT_FRAMES_PER_BUFFER = 4000  # 250ms @ 16kHz
    OUTPUT_FRAMES_PER_BUFFER = 1000  # 62.5ms @ 16kHz

    def __init__(self):
        try:
            import pyaudio
        except ImportError:
            raise ImportError("To use DefaultAudioInterface you must install pyaudio.")
        self.pyaudio = pyaudio
        self.is_agent_speaking = False
        self.speaking_lock = threading.Lock()
        self.last_output_time = 0

    def start(self, input_callback: Callable[[bytes], None]):
        # Audio input is using callbacks from pyaudio which we simply pass through.
        self.input_callback = input_callback

        # Audio output is buffered so we can handle interruptions.
        # Start a separate thread to handle writing to the output stream.
        self.output_queue: queue.Queue[bytes] = queue.Queue()
        self.should_stop = threading.Event()
        self.output_thread = threading.Thread(target=self._output_thread)

        self.p = self.pyaudio.PyAudio()
        self.in_stream = self.p.open(
            format=self.pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            stream_callback=self._in_callback,
            frames_per_buffer=self.INPUT_FRAMES_PER_BUFFER,
            start=True,
        )
        self.out_stream = self.p.open(
            format=self.pyaudio.paInt16,
            channels=1,
            rate=16000,
            output=True,
            frames_per_buffer=self.OUTPUT_FRAMES_PER_BUFFER,
            start=True,
        )

        self.output_thread.start()

    def stop(self):
        self.should_stop.set()
        self.output_thread.join()
        self.in_stream.stop_stream()
        self.in_stream.close()
        self.out_stream.close()
        self.p.terminate()

    def output(self, audio: bytes):
        with self.speaking_lock:
            self.is_agent_speaking = True
            print("Agent is speaking: Locking")
        self.output_queue.put(audio)

    def interrupt(self):
        # Clear the output queue to stop any audio that is currently playing.
        # Note: We can't atomically clear the whole queue, but we are doing
        # it from the message handling thread so no new audio will be added
        # while we are clearing.
        try:
            while True:
                _ = self.output_queue.get(block=False)
        except queue.Empty:
            pass
        with self.speaking_lock:
            print("Agent is done speaking: unlocking")
            self.is_agent_speaking = False

    def _output_thread(self):
        import time
        
        while not self.should_stop.is_set():
            try:
                audio = self.output_queue.get(timeout=0.25)
                self.out_stream.write(audio)
                self.last_output_time = time.time()
            except queue.Empty:
                # If the queue is empty for more than a short period,
                # the agent has likely stopped speaking
                if self.is_agent_speaking and time.time() - self.last_output_time > 0.75:
                    with self.speaking_lock:
                        print("Agent is done speaking: unlocking")
                        self.is_agent_speaking = False

    def _in_callback(self, in_data, frame_count, time_info, status):
        with self.speaking_lock:
            speaking = self.is_agent_speaking
        
        if self.input_callback and not speaking:
            self.input_callback(in_data)
        return (None, self.pyaudio.paContinue)
