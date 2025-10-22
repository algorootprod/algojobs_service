from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class Education(BaseModel):
    degree: str = Field(..., description="Degree name, e.g. B.Tech, M.Sc")
    institution: str = Field(..., description="University or institute")
    year: Optional[int] = Field(None, description="Year of graduation")

class Experience(BaseModel):
    title: str = Field(..., description="Job title, e.g. Data Scientist")
    company: str = Field(..., description="Employer name")
    years: float = Field(..., description="Number of years in this role")
    description: Optional[str] = Field(None, description="Summary of responsibilities")

class Skill(BaseModel):
    name: str = Field(..., description="Skill name, e.g. Python")
    level: Optional[str] = Field(None, description="Optional level: Beginner/Intermediate/Expert")

class Projects(BaseModel):
    title: str = Field(..., description="Project title")
    description: Optional[str] = Field(None, description="Brief description of the project")
    link: Optional[str] = Field(None, description="Link to the project if available")

class Resume(BaseModel):
    candidate_id: str = Field(..., description="Unique ID of the candidate")
    name: str = Field(..., description="Full name of the candidate")
    email: Optional[str] = Field(None, description="Email ID")
    phone: Optional[str] = Field(None, description="Phone number")

    summary: Optional[str] = Field(None, description="Short professional summary")

    education: List[Education] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)

    projects: Optional[List[Projects]] = Field(default_factory=list)
    certifications: Optional[List[str]] = Field(default_factory=list)

class RankRequest(BaseModel):
    job_description: str = Field(..., min_length=3)
    resumes: List[Resume] = Field(..., min_items=1)
    top_k: Optional[int] = Field(None, ge=1, description="Return top K resumes")

class RankedResume(BaseModel):
    candidate_id: str
    name: str
    score: float
    resume: Resume

class RankResponse(BaseModel):
    total_resumes: int
    returned: int
    results: List[RankedResume]
    
# --- Scheduler API Schemas ---

class ScheduleRequest(BaseModel):
    candidate_resume: str = Field(..., description="The full text of the candidate's resume.")
    job_description: str = Field(..., description="The job description for the role.")
    interview_template: str = Field(..., description="The template/prompt for the AI interviewer.")
    evaluation_template: str = Field(..., description="The template for post-interview evaluation.")
    interview_time: datetime = Field(..., description="The proposed date and time for the interview (UTC).")
    candidate_id: str = Field(..., description="A unique identifier for the candidate.")
    candidate_name: str = Field(..., description="Full name of the candidate.")

class ScheduleResponse(BaseModel):
    message: str
    agent_name:str
    room_name: str
    candidate_id: str
    scheduled_time: datetime
    token: str
    # In a real app, this would also include a meeting_id to track the interview state
