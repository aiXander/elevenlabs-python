import os
import time
import threading
import json
import pprint
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from eden_utils import *

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Global hyperparameters
MESSAGE_HISTORY_LIMIT = 20  # Maximum number of messages to include in history for next agent
DEBUG = True

class ConversationTracker:
    """Track the conversation history."""
    def __init__(self, message_limit=MESSAGE_HISTORY_LIMIT):
        self.history = []
        self.message_limit = message_limit
        self.current_agent = None
        self.current_agent_message_count = 0
        self.agent_turn_limit = 2
        self.last_speaker = None
        self.lock = threading.Lock()
        
    def set_current_agent(self, agent_name, turn_limit=2):
        """Set the current active agent."""
        with self.lock:
            self.current_agent = agent_name
            self.current_agent_message_count = 0
            self.agent_turn_limit = turn_limit
        
    def add_agent_message(self, message):
        """Add an agent message to the history."""
        with self.lock:
            self.current_agent_message_count += 1
            formatted_message = f"{self.current_agent} ({self.current_agent_message_count}/{self.agent_turn_limit}): {message}"
            self.history.append(formatted_message)
            print(formatted_message)
            self.last_speaker = "agent"
        
    def add_user_message(self, message):
        """Add a user message to the history."""
        with self.lock:
            formatted_message = f"User: {message}"
            self.history.append(formatted_message)
            print(formatted_message)
            self.last_speaker = "user"
        
    def get_formatted_history(self):
        """Get the formatted conversation history."""
        with self.lock:
            limited_history = self.history[-self.message_limit:] if len(self.history) > self.message_limit else self.history
            return "\n".join(limited_history)
        
    def should_switch_agent(self):
        """Check if we should switch to the next agent."""
        with self.lock:
            # Switch if we have enough agent messages and the last speaker was the agent:
            return self.current_agent_message_count >= self.agent_turn_limit and self.last_speaker == "agent"
            
    def print_full_history(self):
        """Print the complete conversation history."""
        with self.lock:
            print("\n----- FULL CONVERSATION HISTORY -----")
            print("\n".join(self.history))
            print("----- END OF HISTORY -----\n")

def start_conversation_with_agent(agent_name, client, all_agent_data, tracker, requires_auth=False, n_turns=2):
    """Start a conversation with the specified agent."""
    print(f"\n--- Starting conversation with agent: {agent_name} ---\n")
    
    tracker.set_current_agent(agent_name, turn_limit=n_turns)
    agent_data = all_agent_data[agent_name]
    
    config = _build_conversation_override(agent_data["config"], tracker, n_turns, verbose=1)

    if DEBUG:
        exit()

    conversation = Conversation(
        client,
        agent_data["agent_id"],
        requires_auth=requires_auth,
        audio_interface=DefaultAudioInterface(),
        config=config,
        callback_agent_response=lambda response: tracker.add_agent_message(response),
        callback_agent_response_correction=lambda original, corrected: print(f"Correction: '{original}' -> '{corrected}'"),
        callback_user_transcript=lambda transcript: tracker.add_user_message(transcript)
    )
    conversation.start_session()
    
    try:
        while not tracker.should_switch_agent():
            time.sleep(0.25)
            
        print(f"\n--- Ending conversation with agent: {agent_name} ---\n")
        
        # Wait for agent to completely finish speaking
        audio_interface = conversation._audio_interface if hasattr(conversation, '_audio_interface') else conversation.audio_interface
        while getattr(audio_interface, 'is_agent_speaking', False):
            print("Agent is still speaking... Sleeping for 0.5 seconds...")
            time.sleep(0.5)
            
    finally:
        conversation.end_session()
        print(f"\n --- Conversation TERMINATED --- \n")
        try:
            wait_thread = threading.Thread(target=conversation.wait_for_session_end)
            wait_thread.daemon = True
            wait_thread.start()
            wait_thread.join(timeout=2.0)
        except Exception as e:
            print(f"Warning during session cleanup: {e}")

def _build_conversation_override(agent_config, tracker, n_turns, verbose = 0):
    """Build the conversation override configuration with agent prompt, calendar info and conversation history."""
    conversation_override = {}
    conversation_override["agent"] = {"prompt": {"prompt": ""}, "first_message": ""}
    if "first_message" in agent_config:
        conversation_override["agent"]["first_message"] = agent_config["first_message"]

    # Get agent prompt:
    agent_prompt = agent_config["prompt"]
    agent_cue_turns = n_turns - 1
    turn_indicator_cue = f"IMPORTANT: You will get a total of {agent_cue_turns} turns to speak after which this conversation will be closed. Make sure to end your final turn with a closed, finalizing statement / answer (not a question)!"
    agent_prompt += f"\n\n{turn_indicator_cue}"

    # Get calendar context:
    calendar_context = get_calendar_context_today()

    if tracker.history:
        conversation_history = tracker.get_formatted_history()
        history_context = f"\n\nConversation history with previous agent(s):\n{conversation_history}\n\nContinue the conversation based on this history and remember you only get {agent_cue_turns} turns to speak!"
    else:
        history_context = "New conversation starting now."
    
    # Construct final agent prompt:
    conversation_override["agent"]["prompt"]["prompt"] = f"{agent_prompt}\n{calendar_context}\n{history_context}"

    if verbose > 0:
        print("conversation_override:")
        print(json.dumps(conversation_override, indent=4))
        
        with open("conversation_override.json", "w") as f:
            json.dump(conversation_override, f, indent=4)

    return ConversationInitiationData(conversation_config_override=conversation_override)

def main():
    all_agent_data = load_agents()
    client = ElevenLabs(api_key=os.environ.get('ELEVENLABS_API_KEY'))
    tracker = ConversationTracker(message_limit=MESSAGE_HISTORY_LIMIT)

    #play_sound("tests/assets/audio/ambient/02.flac", async_play=True, loop=True)
    start_conversation_with_agent("Shakti", client, all_agent_data, tracker, n_turns=4)
    start_conversation_with_agent("JeroWiku", client, all_agent_data, tracker, n_turns=3)
    #play_random_sound("tests/assets/audio/gongs", async_play=True)

if __name__ == '__main__':
    main() 