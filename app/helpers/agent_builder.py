from livekit.plugins import openai, google, deepgram, groq, sarvam, speechify
from typing import Optional
from app.helpers.decripter import decrypt_api_key

def build_llm_instance(provider: str, model: str, encrypted_api_key: str, temperature: Optional[float]=None):
    api_key=decrypt_api_key(encrypted_api_key)
    if provider == "google":
        return google.LLM(model=model, api_key=api_key,temperature=temperature)
    elif provider == "groq":
        return groq.LLM(model=model, api_key=api_key,temperature=temperature)
    if "gpt-5" in model:
        return openai.LLM(model=model, api_key=api_key)
    return openai.LLM(model=model, api_key=api_key,temperature=temperature)

def build_stt_instance(provider: str, model: str, language: str, encrypted_api_key: str):
    api_key=decrypt_api_key(encrypted_api_key)
    if provider == "openai":
        return openai.STT(model=model, language=language, api_key=api_key)
    elif provider == "deepgram":
        return deepgram.STT(model=model, language=language, api_key=api_key)
    elif provider == "sarvam":
        return sarvam.STT(model=model, language=language, api_key=api_key)
    return deepgram.STT(model="nova-3", language="en", api_key=api_key)

def build_tts_instance(
        provider: str, 
        model: str, 
        sample_rate: Optional[int]=8000,
        language: Optional[str]=None,
        voice: Optional[str]=None,
        instructions :Optional[str] =None,
        credentials_info: dict | str = None
        ):
    api_key=decrypt_api_key(credentials_info)
    if provider == "google":
        tts_kwargs = {
            "voice_name": model,
            "language": language,
            "sample_rate": sample_rate,
            "credentials_info": api_key
        }

        if "Wavenet" in model:
            tts_kwargs["use_streaming"] = False

        return google.TTS(**tts_kwargs)

    elif provider == "deepgram":
        return deepgram.TTS(
            model=model,
            api_key=api_key,
            sample_rate=sample_rate,
            )
    elif provider == "openai":
        return openai.TTS(
            model=model,
            api_key=api_key,
            sample_rate=sample_rate,
            voice=voice, 
            instructions=instructions
            )
    elif provider == "sarvam":
        return sarvam.TTS(
            target_language_code=language,
            model=model,
            speaker=voice,
            api_key=api_key,
            speech_sample_rate=sample_rate
            )
    
    elif provider == "speechify":
        return speechify.TTS(
            model=model,
            api_key=api_key,
            voice_id=voice, 
            language=language
            )
    
    return google.TTS(
            voice_name="en-IN-Chirp3-HD-Charon",
            language="en-IN",
            credentials_info=api_key,
            sample_rate=sample_rate
            )