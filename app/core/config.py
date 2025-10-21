import os
from dotenv import load_dotenv

load_dotenv()

class Settings():
    """
    Application configuration settings loaded from environment variables.
    """
    # --- General App Settings ---
    API_V1_STR: str = "/api/v1"
    
    # --- Resume Ranker Settings ---
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "32"))
    MAX_RESUMES: int = int(os.getenv("MAX_RESUMES", "1000"))

    # --- Meeting Scheduler & LiveKit Agent Settings ---
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
    MEET_HOST: str = os.getenv("MEET_HOST", "https://meet.livekit.io")
    TINYURL_API_KEY: str = os.getenv("TINYURL_API_KEY", "")
    
    class Config:
        case_sensitive = True

    if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL]):
        raise Exception("Environment variables not set properly. Please check your .env file.")

# Instantiate settings
settings = Settings()
