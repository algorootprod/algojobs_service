from typing import Optional,Any
from datetime import datetime

from pydantic import BaseModel, Field

class LLM(BaseModel):
    provider: str
    model: str
    api_key: str
    temperature: Optional[float] = None

class STT(BaseModel):
    provider: str
    model: str
    api_key: str

class TTS(BaseModel):
    provider: str
    model: str
    api_key: str

class AgentConfig(BaseModel):
    prompt: str
    llm: Optional[LLM] = None
    stt: Optional[STT] = None
    tts: Optional[TTS] = None

class Agent(BaseModel):
    """
    Schema for agent configuration.
    """
    id: Optional[str] = Field(None, alias="_id")
    name: Optional[str] = None
    agentConfig: Optional[AgentConfig] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None