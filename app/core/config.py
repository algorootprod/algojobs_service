import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    """
    Application configuration settings loaded from environment variables.
    """
    # --- General App Settings ---
    API_V1_STR: str = "/api/v1"
    
    # --- Resume Ranker Settings ---
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBED_BATCH_SIZE: int = int(os.environ.get("EMBED_BATCH_SIZE", "32"))
    MAX_RESUMES: int = int(os.environ.get("MAX_RESUMES", "1000"))

    # --- Meeting Scheduler & LiveKit Agent Settings ---
    LIVEKIT_API_KEY: str = os.environ.get("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.environ.get("LIVEKIT_API_SECRET", "")
    LIVEKIT_WS_URL: str = os.environ.get("LIVEKIT_WS_URL", "wss://your-livekit-url.livekit.cloud")
    MEET_HOST: str = os.environ.get("MEET_HOST", "https://meet.livekit.io")
    TINYURL_API_KEY: str = os.environ.get("TINYURL_API_KEY", "")
    
    class Config:
        case_sensitive = True

# Instantiate settings
settings = Settings()
