from __future__ import annotations
from datetime import datetime, date
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, EmailStr, ValidationError


# --- Nested models ---


class CareerPreferences(BaseModel):
    desired_locations: Optional[List[str]] = Field(default_factory=list)
    desired_roles: Optional[List[str]] = Field(default_factory=list)
    min_ctc: Optional[float] = None
    max_ctc: Optional[float] = None
    notice_period_days: Optional[int] = None


class KeySkill(BaseModel):
    name: str
    level: Optional[str] = None
    years: Optional[float] = None


class Skill(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None


class Education(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    grade: Optional[str] = None
    details: Optional[str] = None
    id: Optional[str] = None


class AcademicAchievement(BaseModel):
    title: str
    description: Optional[str] = None
    year: Optional[int] = None


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    currently_working: Optional[bool] = False
    description: Optional[str] = None
    location: Optional[str] = None
    roleTitle: Optional[str] = None  # preserve original key if present
    employerName: Optional[str] = None
    id: Optional[str] = None


class Internship(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None


class LanguageProficiency(BaseModel):
    language: str
    speaking: Optional[str] = None
    reading: Optional[str] = None
    writing: Optional[str] = None
    proficiency: Optional[str] = None
    id: Optional[str] = None


class Project(BaseModel):
    title: str
    role: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    techStack: Optional[List[str]] = None
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    projectUrl: Optional[str] = None
    githubUrl: Optional[str] = None
    liveUrl: Optional[str] = None
    isPersonalProject: Optional[bool] = None
    teamSize: Optional[int] = None
    responsibilities: Optional[List[str]] = None
    achievements: Optional[List[str]] = None


class Accomplishment(BaseModel):
    title: str
    description: Optional[str] = None
    year: Optional[int] = None


class CompetitiveExam(BaseModel):
    name: str
    score: Optional[str] = None
    year: Optional[int] = None


# --- Main Resume model ---


class Resume(BaseModel):
    # If Mongo _id present it will be stored in id field (alias applied on read)
    id: Optional[str] = Field(None, alias="_id")
    owner: Optional[str] = None

    # Basic identity (DB uses fullName, preferredName, firstName may be missing)
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    fullName: Optional[str] = None
    preferredName: Optional[str] = None
    preferredContactMethod: Optional[str] = None

    # Contact info
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # profile / metadata
    bio: Optional[str] = None
    summary: Optional[str] = None
    dob: Optional[date] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    careerPreferences: Optional[CareerPreferences] = Field(default_factory=CareerPreferences)

    # Experience & skills
    totalExperience: Optional[float] = 0.0
    totalExperienceYears: Optional[float] = None

    # main lists (normalized)
    skills: Union[List[Skill],Any] = Field(default_factory=list)
    keySkills:Union[List[KeySkill],Any]  = Field(default_factory=list)
    education: Union[List[Education],Any] = Field(default_factory=list)
    academicAchievements: Union[List[AcademicAchievement],Any] = Field(default_factory=list)
    experiences: List[Experience] = Field(default_factory=list)
    internships: List[Internship] = Field(default_factory=list)
    languages: List[LanguageProficiency] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    accomplishments: List[Accomplishment] = Field(default_factory=list)
    competitiveExams: List[CompetitiveExam] = Field(default_factory=list)

    # raw/legacy containers (kept as extras if present)
    skillSet: Optional[Dict[str, Any]] = None
    experienceEntries: Optional[List[Dict[str, Any]]] = None
    educationEntries: Optional[List[Dict[str, Any]]] = None
    languageProficiencies: Optional[List[Dict[str, Any]]] = None

    # metadata
    isActive: Optional[bool] = True
    isDeleted: Optional[bool] = False
    tags: List[str] = Field(default_factory=list)
    extras: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # class Config:
    #     allow_population_by_field_name = True
    #     arbitrary_types_allowed = True

    # optional convenience property
    # @property
    # def display_name(self) -> Optional[str]:
    #     if self.fullName:
    #         return self.fullName
    #     if self.firstName or self.lastName:
    #         return f"{self.firstName or ''} {self.lastName or ''}".strip()
    #     return self.preferredName or None
