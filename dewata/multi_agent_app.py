import os
import time
import threading
import json
import pprint
import asyncio
from typing import Optional, Literal, Dict

from pydantic import BaseModel
from elevenlabs import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
from eden_utils import *
from agent_config import build_conversation_override

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Global hyperparameters
MESSAGE_HISTORY_LIMIT = 20  # Maximum number of messages to include in history for next agent
DEBUG = False

class AgentSwitchResponse(BaseModel):
    """Response format for agent switching decisions."""
    should_switch: Literal["yes", "no"]

class ConversationTracker:
    """Track the conversation history."""
    def __init__(self, message_limit=MESSAGE_HISTORY_LIMIT):
        self.history = []
        self.message_limit = message_limit
        self.current_agent = None
        self.current_agent_message_count = 0
        self.min_turns = 2
        self.max_turns = 8
        self.last_speaker = None
        self.lock = threading.Lock()
        self.llm_client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.llm_decision = None
        
    def set_current_agent(self, agent_name, min_turns=2, max_turns=8):
        """Set the current active agent."""
        with self.lock:
            self.current_agent = agent_name
            self.current_agent_message_count = 0
            self.min_turns = min_turns
            self.max_turns = max_turns
            self.llm_decision = None
        
    async def query_llm_for_agent_switch(self, conversation_history: str) -> str:
        """Ask the LLM if it's a good time to switch agents based on conversation."""

        system_prompt = """You are an AI assistant that helps decide when to switch between different characters / agents in an interactive AI installation.
        Analyze the following conversation history and decide if the most recent agent message is a good point to switch to the next agent.
        Consider:
        1. If the agent completed its thought or message
        2. If there are no hanging questions requiring a direct follow-up from the same agent
        3. If this is a natural transition point in the conversation
        
        Respond with either "yes" or "no" only as a JSON object in the format: {"should_switch": "yes"} or {"should_switch": "no"}."""
        
        user_prompt = f"""Based on the following conversation history, should we switch to the next agent now?
        
        {conversation_history}
        
        Respond with only "yes" or "no" as a JSON object with the key "should_switch"."""
        
        try:
            print("Querying LLM for agent switch decision...")
            response_content = await async_llm_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=10
            )
            
            if response_content:
                response_json = json.loads(response_content)
                decision = AgentSwitchResponse(**response_json)
                return decision.should_switch
            else:
                # Default behavior if we didn't get a valid response
                return "no" if self.current_agent_message_count < self.max_turns else "yes"
        except Exception as e:
            print(f"Error querying LLM for agent switch decision: {e}")
            # Default to the original behavior if there's an error
            return "no" if self.current_agent_message_count < self.max_turns else "yes"
    
    async def add_agent_message(self, message):
        """Add an agent message to the history and query LLM for switching decision."""
        with self.lock:
            self.current_agent_message_count += 1
            formatted_message = f"{self.current_agent} ({self.current_agent_message_count}/{self.max_turns}): {message}"
            self.history.append(formatted_message)
            print(formatted_message)
            self.last_speaker = "agent"
        
        # Only query the LLM for a decision if we've reached the minimum number of turns
        if self.current_agent_message_count >= self.min_turns:
            conversation_history = self.get_formatted_history()
            self.llm_decision = await self.query_llm_for_agent_switch(conversation_history)
            print(f"LLM decision for agent switch: {self.llm_decision}")
        else:
            print(f"Not querying LLM yet - minimum {self.min_turns} turns not reached ({self.current_agent_message_count}/{self.min_turns})")
        
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
        """Check if we should switch to the next agent based on LLM decision or max turns."""
        with self.lock:
            if self.current_agent_message_count < self.min_turns:
                return False
                
            if self.current_agent_message_count >= self.max_turns and self.last_speaker == "agent":
                return True
                
            if self.llm_decision is not None:
                return self.llm_decision == "yes" and self.last_speaker == "agent"
            
            return False
            
    def print_full_history(self):
        """Print the complete conversation history."""
        with self.lock:
            print("\n----- FULL CONVERSATION HISTORY -----")
            print("\n".join(self.history))
            print("----- END OF HISTORY -----\n")

def start_conversation_with_agent(agent_name, client, all_agent_data, tracker, requires_auth=True, min_turns=1, max_turns=3):
    """Start a conversation with the specified agent."""
    print(f"\n--- Starting conversation with agent: {agent_name} ---\n")
    
    tracker.set_current_agent(agent_name, min_turns=min_turns, max_turns=max_turns)
    agent_data = all_agent_data[agent_name]
    
    try:
        config = build_conversation_override(agent_data["config"], tracker, max_turns, verbose=1)
        
        if DEBUG:
            exit()

        conversation = Conversation(
            client,
            agent_data["agent_id"],
            requires_auth=requires_auth,
            audio_interface=DefaultAudioInterface(),
            config=config,
            callback_agent_response=lambda response: asyncio.run(tracker.add_agent_message(response)),
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
    except Exception as e:
        print(f"Error starting conversation with agent {agent_name}: {e}")
        import traceback
        traceback.print_exc()

def main():
    all_agent_data = load_agents()
    client = ElevenLabs(api_key=os.environ.get('ELEVENLABS_API_KEY'))
    tracker = ConversationTracker(message_limit=MESSAGE_HISTORY_LIMIT)

    #play_sound("tests/assets/audio/ambient/02.flac", async_play=True, loop=True)
    start_conversation_with_agent("Shakti", client, all_agent_data, tracker, min_turns=2, max_turns=4)
    start_conversation_with_agent("Shiva", client, all_agent_data, tracker, min_turns=2, max_turns=3)
    #play_random_sound("tests/assets/audio/gongs", async_play=True)

if __name__ == '__main__':
    main() 