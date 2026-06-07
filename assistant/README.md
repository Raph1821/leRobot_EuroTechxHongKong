# assistant/

LLM-powered conversational assistant, speech I/O, and memory interface.

## What belongs here

- LLM client (`llm_client.py`)
- Intent classification (`intents.py`)
- Action dispatch (`assistant_actions.py`)
- System prompts (`prompts.py`)
- Care context builder (`care_context_builder.py`)
- Capability declarations (`careai_capabilities.py`)
- Speech input (`speech/speech_listener.py`)
- Speech output / TTS (`speech/tts_engine.py`)
- Emergency phrase detection (`speech/emergency_phrases.py`)
- Persistent care memory (`memory/care_memory.py`)
- Memory recall helpers (`memory/memory_recall.py`)
