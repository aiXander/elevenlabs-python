import threading
import time
import os
import random
import pygame
import atexit
from datetime import datetime
import yaml
from typing import Optional, Literal, Dict

# Get the directory of the current file
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"Current directory: {CURRENT_DIR}")

from openai import AsyncOpenAI
async def async_llm_call(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini", temperature: float = 0.2, max_tokens: int = 100, response_format: Optional[Dict] = {"type": "json_object"}):
    """Generic async function to call an LLM with system and user prompts.
    
    Args:
        system_prompt: The system prompt to provide context for the model
        user_prompt: The user prompt/question
        model: The model to use for completion
        temperature: Controls randomness (0-1)
        max_tokens: Maximum number of tokens to generate
        response_format: Format for the response, defaults to JSON
        
    Returns:
        The model's response content
    """
    client = AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    try:
        # Check if we're using json_object format and if 'json' is not in either prompt
        if response_format and response_format.get("type") == "json_object":
            if "json" not in (system_prompt + user_prompt).lower():
                user_prompt += "\nPlease provide the response in JSON format."
        
        response = await client.chat.completions.create(
            model=model,
            response_format=response_format,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in async LLM call: {e}")
        return None

# Global variables for sound management
pygame_initialized = False
pygame_sounds = {}
pygame_channels = {}

def setup_pygame():
    """Initialize pygame mixer with optimal settings"""
    global pygame_initialized
    if not pygame_initialized:
        pygame.init()
        pygame.mixer.quit()  # Ensure clean state
        pygame.mixer.pre_init(44100, -16, 2, 1024)  # 44.1kHz, 16-bit, stereo
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)  # Allow multiple sounds
        atexit.register(pygame_cleanup)
        pygame_initialized = True

def pygame_cleanup():
    """Clean up pygame resources"""
    global pygame_initialized, pygame_sounds, pygame_channels
    if pygame_initialized:
        pygame.mixer.stop()
        pygame_sounds = {}
        pygame_channels = {}
        pygame.mixer.quit()
        pygame_initialized = False

def play_sound(filepath, async_play=True, max_time=99999, loop=False):
    """Play an audio file from disk with specified parameters.
    
    Args:
        filepath (str): Path to the audio file to play.
        async_play (bool, optional): Whether to play asynchronously. Defaults to True.
        max_time (int, optional): Maximum time in seconds to play. Defaults to 99999.
        loop (bool, optional): Whether to loop the audio. Defaults to False.
        
    Returns:
        object: Reference to the playback channel or None
    """
    try:
        # Ensure pygame is properly initialized
        setup_pygame()
        
        # Load the sound if not already loaded
        if filepath not in pygame_sounds:
            pygame_sounds[filepath] = pygame.mixer.Sound(filepath)
        
        # Find an available channel
        channel = None
        for i in range(pygame.mixer.get_num_channels()):
            test_channel = pygame.mixer.Channel(i)
            if not test_channel.get_busy():
                channel = test_channel
                pygame_channels[i] = channel
                break
        
        if channel is None:
            # If no free channel, use channel 0
            channel = pygame.mixer.Channel(0)
            pygame_channels[0] = channel
        
        def play_audio():
            start_time = time.time()
            
            # Play the sound
            channel.play(pygame_sounds[filepath], loops=-1 if loop else 0)
            
            # Wait for max_time if specified
            while time.time() - start_time < max_time:
                time.sleep(0.1)
                if not loop or time.time() - start_time >= max_time:
                    channel.stop()
                    break
        
        # Play audio in a separate thread if async
        if async_play:
            audio_thread = threading.Thread(target=play_audio)
            audio_thread.daemon = True
            audio_thread.start()
            return channel
        else:
            play_audio()
            return channel
            
    except ImportError:
        print("Error: pygame could not be installed. Try manually with 'pip install pygame'")
        return None
    except Exception as e:
        print(f"Error playing sound: {e}")
        return None

def play_random_sound(folder_path, async_play=True, max_time=99999, loop=False):
    """Play a random audio file from a directory with specified parameters.
    
    Args:
        folder_path (str): Path to the directory containing audio files.
        async_play (bool, optional): Whether to play asynchronously. Defaults to True.
        max_time (int, optional): Maximum time in seconds to play. Defaults to 99999.
        loop (bool, optional): Whether to loop the audio. Defaults to False.
        
    Returns:
        object: Reference to the playback process or None
    """
    
    try:
        # Check if filepath is a directory
        if not os.path.isdir(folder_path):
            print(f"Error: {folder_path} is not a directory")
            return None
            
        # Common audio file extensions
        audio_extensions = ['.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a']
        
        # Get all audio files in the directory
        audio_files = []
        for file in os.listdir(folder_path):
            if any(file.lower().endswith(ext) for ext in audio_extensions):
                audio_files.append(os.path.join(folder_path, file))
        
        # Check if any audio files were found
        if not audio_files:
            print(f"Error: No audio files found in {folder_path}")
            return None
            
        # Select a random audio file
        random_file = random.choice(audio_files)
        
        # Play the selected file
        return play_sound(random_file, async_play, max_time, loop)
        
    except Exception as e:
        print(f"Error playing random sound: {e}")
        return None

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
            
            config_path = os.path.join(CURRENT_DIR, 'agents', f'{agent_name}.yaml')
            print(f"Config path: {config_path}")
            if os.path.exists(config_path):
                with open(config_path, 'r') as file:
                    agents[agent_name]["config"] = yaml.safe_load(file)
            else:
                raise(f"Warning: No config file found for agent {agent_name}")
                
    print(f"Found {len(agents)} agents: {', '.join(agents.keys())}")
    return agents

def get_calendar_context_today(fallback: bool = True):
    """Get the calendar context for today's date."""
    today = datetime.now().strftime("%Y-%m-%d")
    calendar_path = os.path.join(CURRENT_DIR, 'calendar', f'{today}.txt')
    if os.path.exists(calendar_path):
        with open(calendar_path, 'r') as file:
            calendar_context = file.read()
        return "Energy calendar context for today:\n" + calendar_context
    else:
        if fallback:
            calendar_path = os.path.join(CURRENT_DIR, 'calendar', f'2025-03-29.txt')
            with open(calendar_path, 'r') as file:
                calendar_context = file.read()
            return "Energy calendar context for today:\n" + calendar_context
        else:
            raise Exception(f"Calendar file not found for today: {calendar_path}")
