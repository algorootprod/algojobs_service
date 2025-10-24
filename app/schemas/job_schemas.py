from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

class AgeRange(BaseModel):
    min: Optional[int] = None
    max: Optional[int] = None

class CandidateFilters(BaseModel):
    preferredGender: Optional[str] = None
    maritalStatus: Optional[str] = None
    ageRange: Optional[AgeRange] = None
    locationPreference: Optional[str] = None
    # any other custom filters can go into extra
    extra: Dict[str, Any] = Field(default_factory=dict)

class JobDescription(BaseModel):
    # This matches the nested "jobDescription" object in your document
    country: Optional[str] = None
    state: Optional[str] = None
    employmentType: Optional[str] = None
    experienceLevel: Optional[str] = None
    currency: Optional[str] = None
    minSalary: Optional[int] = None
    maxSalary: Optional[int] = None

    applicationDeadline: Optional[datetime] = None
    startDate: Optional[datetime] = None

    preferredNoticePeriod: Optional[str] = None
    remoteWorkAllowed: Optional[bool] = False

    templateTitle: Optional[str] = None
    templateDescription: Optional[str] = None
    jobTitle: Optional[str] = None
    jobSummary: Optional[str] = None

    skills: List[str] = Field(default_factory=list)
    keyResponsibilities: List[str] = Field(default_factory=list)
    requiredQualifications: List[str] = Field(default_factory=list)
    goodToHaveSkills: List[str] = Field(default_factory=list)
    customSections: List[Any] = Field(default_factory=list)

    isPredefined: Optional[bool] = False
    candidateFilters: Optional[CandidateFilters] = None

class Job(BaseModel):
    # top-level job document
    id: Optional[str] = Field(None, alias="_id")
    jobId: Optional[str] = None

    company: Optional[str] = None    # originally ObjectId — map to str
    department: Optional[str] = None # originally ObjectId — map to str
    departmentName: Optional[str] = None

    createdBy: Optional[str] = None  # ObjectId -> str

    panel: List[str] = Field(default_factory=list)  # list of ObjectId -> list[str]

    # References (stored as ObjectId in your doc) — keep them as optional str
    questionTemplate: Optional[str] = None
    jobDescriptionTemplate: Optional[str] = None

    status: Optional[str] = None
    isActive: Optional[bool] = True
    archived: Optional[bool] = False

    candidatesRequired: Optional[str] = None
    hiringManager: Optional[str] = None

    jobDescription: Optional[JobDescription] = None

    candidateFilters: Optional[Dict[str,Any]] = None
    candidateCap: Optional[int] = None
    
    # timestamps
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
