from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

class JobDescriptionTemplate(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    templateTitle: Optional[str] = None
    templateDescription: Optional[str] = None
    department: Optional[str] = None
    departmentName: Optional[str] = None
    jobTitle: Optional[str] = None
    jobSummary: Optional[str] = None

    skills: List[str] = []
    keyResponsibilities: List[str] = []
    requiredQualifications: List[str] = []
    goodToHaveSkills: List[str] = []
    customSections: List[Any] = Field(default_factory=list)

    isPredefined: Optional[bool] = False
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

class Job(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    jobId: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    createdBy: Optional[str] = None

    panel: List[str] = []

    jobDescriptionTemplate: Optional[str] = None
    questionTemplate: Optional[str] = None

    country: Optional[str] = None
    state: Optional[str] = None
    employmentType: Optional[str] = None
    experienceLevel: Optional[str] = None
    currency: Optional[str] = None

    minSalary: Optional[int] = None
    maxSalary: Optional[int] = None

    applicationDeadline: Optional[datetime] = None
    startDate: Optional[datetime] = None

    hiringManager: Optional[str] = None
    candidatesRequired: Optional[str] = None
    preferredNoticePeriod: Optional[str] = None

    remoteWorkAllowed: Optional[bool] = False
    archived: Optional[bool] = False

    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
