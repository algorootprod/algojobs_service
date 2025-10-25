from datetime import datetime, date
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, EmailStr, ValidationError
from app.schemas.resume_schema import Resume

class RecommendedJob(BaseModel):
    job_id: str 
    score: float 
    rank: int 


class RankedResumeOut(BaseModel):
    candidate_id: Optional[str] 
    owner: Optional[str] 
    name: Optional[str] 
    recommended_jobs: List[RecommendedJob] 
    

class RankRequest(BaseModel):
    job_description: str = Field(..., min_length=3)
    resumes: List[Resume] = Field(..., min_items=1)
    top_k: Optional[int] = Field(None, ge=1, description="Return top K resumes")


class RankResponse(BaseModel):
    total_resumes: int
    returned: int
    
# --- Scheduler API Schemas ---

class ScheduleRequest(BaseModel):
    candidate_key: str

class ScheduleResponse(BaseModel):
    message: str
    agent_name:str
    room_name: str
    scheduled_time: datetime
    token: str
    # In a real app, this would also include a meeting_id to track the interview state
