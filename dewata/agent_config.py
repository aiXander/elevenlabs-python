import json
import asyncio
from typing import Dict, Optional, Union, Any
from dataclasses import dataclass

from elevenlabs.conversational_ai.conversation import ConversationInitiationData
from eden_utils import get_calendar_context_today, async_llm_call

@dataclass
class AgentContextComponents:
    """Container for all components that make up an agent's context."""
    base_prompt: str
    first_message: Optional[str] = None
    calendar_context: Optional[str] = None
    conversation_history: Optional[str] = None
    turn_indicator: Optional[str] = None
    additional_context: Optional[Dict[str, str]] = None

class AgentConfigBuilder:
    """Builder class for creating agent configurations."""
    
    @staticmethod
    async def generate_first_message(agent_prompt: str, conversation_history: Optional[str] = None) -> str:
        """Generate a first message for an agent using LLM if not provided."""
        system_prompt = """You come up with creative opening lines for an interactive AI agent that starts a conversation with a visitor.
        """
        user_prompt = f"""
        --- Agent description: ---
        {agent_prompt}
        --- End of agent description ---
        --- Conversation history: ---
        {conversation_history}
        --- End of conversation history ---
        Based on the above Agent description, generate a first message for the agent that is at most 20 words.
        """
        
        response = await async_llm_call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="gpt-4o-mini",
            temperature=0.8,
            max_tokens=100
        )
        print(f"Generated first message: {response}")

        return response or "Greetings, pilgrim. Who am I speaking with?"
    
    @staticmethod
    def create_turn_indicator(max_turns: int) -> str:
        """Create a turn indicator message for the agent."""
        agent_cue_turns = max_turns - 1
        return f"IMPORTANT: You will get a total of {agent_cue_turns} turns to speak after which this conversation will be closed. Make sure to end your final turn with a closed, finalizing statement / answer (not a question)!"
    
    @staticmethod
    def format_history_context(history: Optional[str], max_turns: int) -> str:
        """Format the conversation history context."""
        if not history:
            return "New conversation starting now."
            
        agent_cue_turns = max_turns - 1
        return f"\n\nConversation history with previous agent(s):\n{history}\n\nContinue the conversation based on this history and remember you only get {agent_cue_turns} turns to speak!"
    
    @staticmethod
    def build_prompt_template() -> str:
        """Build the template for the final prompt."""
        return (
            "######### Agent Description #################\n\n"
            "{base_prompt}\n\n"
            "######### Calendar Context #################\n\n"
            "{calendar_context}\n\n"
            "######### Turn Indicator #################\n\n"
            "{turn_indicator}\n\n"
            "######### Conversation History #################\n\n"
            "{history_context}"
        )
    
    @staticmethod
    def create_conversation_override(components: AgentContextComponents) -> Dict[str, Any]:
        """Create the conversation override configuration from components."""
        prompt_template = AgentConfigBuilder.build_prompt_template()
        
        # Format the final prompt
        final_prompt = prompt_template.format(
            base_prompt=components.base_prompt,
            turn_indicator=components.turn_indicator or "",
            calendar_context=components.calendar_context or "",
            history_context=components.conversation_history or "New conversation starting now."
        )
        
        # Build the conversation override structure
        conversation_override = {
            "agent": {
                "prompt": {
                    "prompt": final_prompt
                },
                "first_message": components.first_message or ""
            }
        }
        
        # Add any additional context if provided
        if components.additional_context:
            for key, value in components.additional_context.items():
                conversation_override["agent"][key] = value
                
        return conversation_override

async def build_conversation_config(
    agent_config: Dict[str, Any],
    conversation_history: Optional[str] = None,
    max_turns: int = 3,
    verbose: int = 0
) -> ConversationInitiationData:
    """
    Build the conversation configuration with agent prompt, calendar info, and conversation history.
    
    Args:
        agent_config: The agent configuration from the YAML file
        conversation_history: Optional conversation history 
        max_turns: Maximum number of turns the agent can speak
        verbose: Verbosity level for debugging
        
    Returns:
        ConversationInitiationData object with the complete configuration
    """
    # Get or generate first message
    first_message = agent_config.get("first_message", "")
    if not first_message:
        first_message = await AgentConfigBuilder.generate_first_message(agent_config["prompt"], conversation_history)
    
    # Build the components
    components = AgentContextComponents(
        base_prompt=agent_config["prompt"],
        first_message=first_message,
        calendar_context=get_calendar_context_today(),
        conversation_history=AgentConfigBuilder.format_history_context(conversation_history, max_turns),
        turn_indicator=AgentConfigBuilder.create_turn_indicator(max_turns)
    )
    
    # Create the conversation override
    conversation_override = AgentConfigBuilder.create_conversation_override(components)
    
    # Debugging output
    if verbose > 0:
        print("conversation_override:")
        print(json.dumps(conversation_override, indent=4))
        
        with open("conversation_override.json", "w") as f:
            json.dump(conversation_override, f, indent=4)
    
    return ConversationInitiationData(conversation_config_override=conversation_override)

# Synchronous wrapper for the async function
def build_conversation_override(
    agent_config: Dict[str, Any],
    tracker,
    max_turns: int = 3,
    verbose: int = 0
) -> ConversationInitiationData:
    """
    Synchronous wrapper for build_conversation_config.
    
    Args:
        agent_config: The agent configuration from the YAML file
        tracker: The conversation tracker object
        max_turns: Maximum number of turns the agent can speak
        verbose: Verbosity level for debugging
        
    Returns:
        ConversationInitiationData object with the complete configuration
    """
    conversation_history = tracker.get_formatted_history() if tracker.history else None
    return asyncio.run(build_conversation_config(
        agent_config=agent_config,
        conversation_history=conversation_history,
        max_turns=max_turns,
        verbose=verbose
    ))
