import json, os
import asyncio
from typing import Dict, Optional, Any

from elevenlabs.conversational_ai.conversation import ConversationInitiationData
from eden_utils import get_calendar_context_today, async_llm_call, save_conversation_override
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_installation_context(person_name: str = None) -> str:
    installation_context_path = os.path.join(CURRENT_DIR, 'installation', f'dewata.txt')
    with open(installation_context_path, "r") as f:
        installation_context = f.read()

    if person_name:
        person_context_file = os.path.join(CURRENT_DIR, f"people/{person_name}.txt") 
        with open(person_context_file, "r") as f:
            person_context = f.read()
        person_cue = f"\n\nYou will be speaking to a human visitor called {person_name}. Here is some additional information about them:\n{person_context}"
        installation_context += person_cue

    return installation_context

async def generate_first_message(agent_prompt: str, conversation_history: Optional[str] = None) -> str:
    """Generate a first message for an agent using LLM if not provided."""
    system_prompt = """You come up with creative opening lines for an interactive AI agent that has a conversation with a visitor."""
    
    user_prompt = f"""
    --- Agent description: ---
    {agent_prompt}
    --- End of agent description ---
    --- Conversation history: ---
    {conversation_history}
    --- End of conversation history ---
    Based on the above Agent description and optional conversation history, generate the first message for the agent that is at most 20 words. Respond with a json object with the key "message" and the value being the first message.
    """
    
    response = await async_llm_call(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model="gpt-4o-mini",
        temperature=1.0,
        max_tokens=100
    )
    
    message = json.loads(response)["message"]
    return message or "Greetings, pilgrim. Who am I speaking with?"

async def build_conversation_config(
    agent_config: Dict[str, Any],
    conversation_history: Optional[str] = None,
    max_turns: int = 3,
    is_final_turn: bool = False,
    person_name: str = None,
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

    installation_context = load_installation_context(person_name=person_name)

    # Get or generate first message
    first_message = agent_config.get("first_message", "")
    if not first_message:
        first_message = await generate_first_message(agent_config["prompt"], conversation_history)
    
    # Create turn indicator
    agent_cue_turns = max_turns - 1
    if is_final_turn:
        turn_indicator = f"IMPORTANT: This is your final turn to respond in this conversation. Make sure to end with a a closed, finalizing statement / answer (not a question)!"
    else:
        turn_indicator = f"IMPORTANT: You will get a total of {agent_cue_turns} turns to speak after which this conversation will be closed. Make sure to end your final turn with a closed, finalizing statement / answer (not a question)!"
    
    # Format history context
    if not conversation_history:
        formatted_history = "New conversation starting now."
    else:
        formatted_history = f"\n\nConversation history with previous agent(s):\n{conversation_history}\n\nContinue the conversation based on this history and remember you only get {agent_cue_turns} turns to speak!"
    
    # Build the prompt template and format final prompt
    prompt_template = (
        "### Installation context ###\n\n"
        "{installation_context}\n\n"
        "### Today's Energy Calendar Context ###\n\n"
        "{calendar_context}\n\n"
        "### Agent Description ###\n\n"
        "{base_prompt}\n\n"
        "### Turn Indicator ###\n\n"
        "{turn_indicator}\n\n"
        "### Conversation History ###\n\n"
        "{history_context}"
    )
    
    final_prompt = prompt_template.format(
        installation_context=installation_context,
        base_prompt=agent_config["prompt"],
        turn_indicator=turn_indicator,
        calendar_context=get_calendar_context_today() or "",
        history_context=formatted_history
    )
    
    # Build the conversation override structure
    conversation_override = {
        "agent": {
            "prompt": {
                "prompt": final_prompt
            },
            "first_message": first_message
        }
    }
    
    # Add any additional context if provided in agent_config
    additional_context = agent_config.get("additional_context", {})
    if additional_context:
        for key, value in additional_context.items():
            conversation_override["agent"][key] = value

    save_conversation_override(conversation_override, "conversation_override.txt")
    
    return ConversationInitiationData(conversation_config_override=conversation_override)

def build_conversation_override(
    agent_config: Dict[str, Any],
    tracker,
    max_turns: int = 3,
    is_final_turn: bool = False,
    person_name: str = None,
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
        is_final_turn=is_final_turn,
        person_name=person_name,
        verbose=verbose
    ))
