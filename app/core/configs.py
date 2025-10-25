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
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "32"))
    MAX_RESUMES: int = int(os.getenv("MAX_RESUMES", "1000"))

    # --- Meeting Scheduler & LiveKit Agent Settings ---
    LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
    LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")
    LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
    MEET_HOST: str = os.getenv("MEET_HOST", "https://meet.livekit.io")
    TINYURL_API_KEY: str = os.getenv("TINYURL_API_KEY", "")
    MONGO_DB_URL: str = os.getenv("MONGO_DB_URL", "mongodb://localhost:27017")
    SHARED_SECRET: str = os.getenv("SHARED_SECRET", "default_shared_secret")
    
    class Config:
        case_sensitive = True

    if not all([LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_URL, MONGO_DB_URL, SHARED_SECRET]):
        raise Exception("Environment variables not set properly. Please check your .env file.")

# Instantiate settings
config = Settings()
