# Dewata Nawa Sanga Multi-Agent Conversation System

This is a multi-agent conversation system built with ElevenLabs API that enables seamless transitions between multiple conversational AI agents in a single installation.

## Features

- Modular architecture for managing multiple conversational agents
- Automatic tracking and sharing of conversation context between agents
- Dynamic switching between agents with conversation continuity
- Configurable instructions for each agent's behavior
- Built-in conversation history tracking
- Trigger-based agent switching (keyword, regex, or intent patterns)

## Setup

1. Create a `.env` file in the `tests` directory with your API credentials:

```
ELEVENLABS_API_KEY=your_api_key_here
AGENT_ID=your_primary_agent_id
AGENT_ID_2=your_secondary_agent_id

# For the advanced example (optional)
NARRATOR_AGENT_ID=your_narrator_agent_id
PHILOSOPHER_AGENT_ID=your_philosopher_agent_id
ARTIST_AGENT_ID=your_artist_agent_id
FUTURIST_AGENT_ID=your_futurist_agent_id
```

2. Install required dependencies:

```bash
pip install elevenlabs python-dotenv pytest
```

## Usage

### Basic Demo

To run the basic demonstration with two agents:

```bash
python dewata_app.py
```

This will start a conversation with your primary agent. The system will automatically switch agents when trigger phrases are detected in either the agent's response or the user's input.

### Advanced Installation Example

For a more complex example with four different agent roles:

```bash
python dewata_installation_example.py
```

This advanced example creates an installation with four distinct characters:
- A **Narrator** who guides the overall conversation
- A **Philosopher** who explores philosophical implications
- An **Artist** who provides artistic perspectives
- A **Futurist** who discusses future possibilities

The agents respond to specific phrases to transition the conversation between different characters, creating a dynamic multi-perspective experience.

### Built-in Trigger Phrases

The system comes with some default triggers:

- When the primary agent says "hand over to my colleague" or "switch to my colleague", it will switch to the secondary agent
- When a user says "back to the first" or "return to first", it will switch back to the primary agent

The advanced example includes additional triggers like:
- "Let's consider the philosophical implications" (switches to philosopher)
- "Through an artistic lens" (switches to artist)
- "What about the future" (switches to futurist)
- "Back to you, narrator" (switches back to narrator)

## Architecture

The system is composed of several key components:

- `ConfigManager`: Handles loading and managing API keys and credentials
- `ConversationTracker`: Keeps track of conversation history between agents
- `AgentTrigger`: Defines pattern-based triggers for switching between agents
- `MultiAgentManager`: Manages multiple conversational agents and transitions
- `DewataInstallation`: Main class that coordinates the multi-agent conversation

## Extending the System

### Adding More Agents

1. Add your additional agent IDs to the `.env` file:

```
AGENT_ID_3=your_third_agent_id
AGENT_ID_4=your_fourth_agent_id
```

2. Modify the `DewataInstallation` class to include these additional agents and create a more complex conversation flow with additional triggers.

### Custom Trigger Creation

You can create custom triggers for agent switching:

```python
# Create a trigger that switches to agent3 when the word "philosophy" is mentioned
manager.add_trigger(
    AgentTrigger(
        target_agent_id="agent3_id",
        pattern="philosophy",
        pattern_type="keyword",  # Can be "keyword", "regex", or "intent"
        dynamic_variables={
            "instructions": "You are a philosophy expert. Continue the conversation."
        }
    )
)
```

The system supports three types of triggers:
- **Keyword** triggers: Simple substring matching
- **Regex** triggers: Regular expression pattern matching
- **Intent** triggers: Basic intent detection (currently implemented as keyword matching)

### Programmatic Agent Switching

In addition to pattern triggers, you can use the `switch_agent` client tool to switch agents from within client tools:

```python
def custom_tool(parameters):
    # Do something...
    
    # Programmatically switch to another agent
    switch_agent({
        "agent_id": "another_agent_id",
        "dynamic_variables": {
            "key": "value"
        }
    })
    
    return "Tool executed"
```

## Acknowledgements

This system is built on top of the ElevenLabs Conversation API. 