import os
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ClientTools
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from dotenv import load_dotenv
load_dotenv('.env')

def main():
    AGENT_ID=os.environ.get('AGENT_ID_HAIDAI')
    API_KEY=os.environ.get('ELEVENLABS_API_KEY')
    
    client = ElevenLabs(api_key=API_KEY)
    conversation = Conversation(
        client,
        AGENT_ID,
        requires_auth=False,
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=lambda response: print(f"Agent: {response}"),
        callback_agent_response_correction=lambda original, corrected: print(f"Agent: {original} -> {corrected}"),
        callback_user_transcript=lambda transcript: print(f"User: {transcript}")
    )
    conversation.start_session()

if __name__ == '__main__':
    main()