import openai
import os

from dotenv import load_dotenv
load_dotenv('.env')

os.environ.get('OPENAI_API_KEY')

# Define a function to get transcription with timestamps
def transcribe_audio_with_timestamps(audio_file_path):

    txt_filepath = os.path.join(os.path.dirname(audio_file_path), os.path.basename(audio_file_path) + '_transcript.txt')
    
    with open(audio_file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    segments = transcript.get('segments', [])
    
    # Write transcription to file
    with open(txt_filepath, 'w') as f:
        for segment in segments:
            start = segment['start']
            end = segment['end']
            text = segment['text']
            f.write(f"[{start:.2f}s - {end:.2f}s]: {text}\n")
            print(f"[{start:.2f}s - {end:.2f}s]: {text}")
    
    print(f"Transcription saved to {txt_filepath}")


# Example usage
audio_path = "/data/xander/Projects/cog/GitHub_repos/audio/data/Terence McKenna - Lost in Language.mp3"
transcribe_audio_with_timestamps(audio_path)
