import os
import time
import threading
import yaml
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from dotenv import load_dotenv
load_dotenv('.env')

# Global hyperparameters
MESSAGES_PER_AGENT = 2  # Number of messages the agent should speak before switching
MESSAGE_HISTORY_LIMIT = 10  # Maximum number of messages to include in history for next agent

def load_agents():
    """Load agent IDs from environment variables and their configurations from YAML files.
    
    Returns:
        dict: A dictionary where keys are agent names and values are dictionaries containing
              agent_id and config keys.
    """
    agents = {}
    for key, value in os.environ.items():
        if key.startswith('AGENT_ID_'):
            agent_name = key.replace('AGENT_ID_', '')
            agents[agent_name] = {"agent_id": value}
            
            config_path = os.path.join('tests', 'agents', f'{agent_name}.yaml')
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    agents[agent_name]["config"] = yaml.safe_load(file)
            else:
                raise(f"Warning: No config file found for agent {agent_name}")
                
    return agents

class ConversationTracker:
    """Track the conversation history."""
    def __init__(self, message_limit=MESSAGE_HISTORY_LIMIT):
        self.history = []
        self.message_limit = message_limit
        self.agent_message_count = 0
        self.last_speaker = None
        self.lock = threading.Lock()
        
    def add_agent_message(self, message):
        """Add an agent message to the history."""
        with self.lock:
            self.history.append(f"Agent: {message}")
            print(f"Agent: {message}")
            self.agent_message_count += 1
            self.last_speaker = "agent"
        
    def add_user_message(self, message):
        """Add a user message to the history."""
        with self.lock:
            self.history.append(f"User: {message}")
            print(f"User: {message}")
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
            return self.agent_message_count >= MESSAGES_PER_AGENT and self.last_speaker == "agent"

def start_conversation_with_agent(client, agent_data, agent_name, tracker, requires_auth=False):
    """Start a conversation with the specified agent."""
    print(f"\n--- Starting conversation with agent: {agent_name} ---\n")
    
    agent_id = agent_data["agent_id"]
    agent_config = agent_data["config"]
    
    # Create conversation config with history if available
    conversation_override = {}
    
    # Add agent configuration if available
    if agent_config:
        conversation_override["agent"] = {
            "prompt": {
                "prompt": agent_config.get("prompt", "")
            }
        }
        
        # Add first message if available
        if "first_message" in agent_config:
            conversation_override["agent"]["first_message"] = agent_config["first_message"]
    
    # Add conversation history if available
    if tracker.history:
        conversation_history = tracker.get_formatted_history()
        if "agent" not in conversation_override:
            conversation_override["agent"] = {}
        if "prompt" not in conversation_override["agent"]:
            conversation_override["agent"]["prompt"] = {}
        
        # Append history to the prompt if a prompt already exists
        if agent_config and "prompt" in agent_config:
            conversation_override["agent"]["prompt"]["prompt"] += f"\n\nPrevious conversation history:\n{conversation_history}\n\nContinue the conversation based on this history."
        else:
            conversation_override["agent"]["prompt"]["prompt"] = f"Previous conversation history:\n{conversation_history}\n\nContinue the conversation based on this history."
    
    config = ConversationInitiationData(
        conversation_config_override=conversation_override
    ) if conversation_override else None
    
    # Reset tracker's agent message count
    tracker.agent_message_count = 0
    tracker.last_speaker = None
    
    # Create and start the conversation
    conversation = Conversation(
        client,
        agent_id,
        requires_auth=requires_auth,
        audio_interface=DefaultAudioInterface(),
        config=config,
        callback_agent_response=lambda response: tracker.add_agent_message(response),
        callback_agent_response_correction=lambda original, corrected: print(f"Correction: '{original}' -> '{corrected}'"),
        callback_user_transcript=lambda transcript: tracker.add_user_message(transcript)
    )
    
    conversation.start_session()
    
    try:
        # Keep checking if we should switch agents
        while not tracker.should_switch_agent():
            time.sleep(0.25)
            
        print(f"\n--- Ending conversation with agent: {agent_name} ---\n")
        
        # Wait for agent to completely finish speaking
        audio_interface = conversation._audio_interface if hasattr(conversation, '_audio_interface') else conversation.audio_interface
        while getattr(audio_interface, 'is_agent_speaking', False):
            time.sleep(0.5)
            
    finally:
        conversation.end_session()
        conversation.wait_for_session_end()

def main():
    API_KEY = os.environ.get('ELEVENLABS_API_KEY')
    agents = load_agents()
    print(f"Found {len(agents)} agents: {', '.join(agents.keys())}")
    
    client = ElevenLabs(api_key=API_KEY)
    tracker = ConversationTracker(message_limit=MESSAGE_HISTORY_LIMIT)
    
    # Start conversations with each agent in sequence
    for agent_name, agent_data in agents.items():
        try:
            start_conversation_with_agent(client, agent_data, agent_name, tracker)
        except Exception as e:
            print(f"Error in conversation with agent {agent_name}: {e}")

if __name__ == '__main__':
    main() 