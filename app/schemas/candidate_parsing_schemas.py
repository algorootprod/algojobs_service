from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

# ---
# Simplified Sub-models for Parsing
# ---

class Education(BaseModel):
    qualification: Optional[str] = None
    institution: Optional[str] = None
    passingYear: Optional[int] = None
    degree: Optional[str] = None
    specialization: Optional[str] = None
    grade: Optional[str] = None

class Experience(BaseModel):
    employerName: Optional[str] = None
    roleTitle: Optional[str] = None
    employmentType: Optional[str] = None
    # Simplified from a complex object to a simple string
    fromMonthYear: Optional[str] = None
    toMonthYear: Optional[str] = None
    isPresent: Optional[bool] = Field(default=False)
    responsibilities: Optional[str] = None
    achievements: Optional[str] = None
    isVoiceProcess: Optional[bool] = Field(default=False)
    processType: Optional[str] = None
    shiftType: Optional[str] = None
    techStack: Optional[List[str]] = Field(default_factory=list)
    projectsWorkedOn: Optional[List[str]] = Field(default_factory=list)
    teamSize: Optional[int] = None
    location: Optional[str] = None

class LanguageProficiency(BaseModel):
    language: Optional[str] = None
    speaking: Optional[str] = None
    reading: Optional[str] = None
    writing: Optional[str] = None

class SkillExperience(BaseModel):
    skillName: str
    years: float

class SkillSet(BaseModel):
    skills: Optional[List[str]] = Field(default_factory=list)
    typingSpeedWPM: Optional[int] = None
    toolsMultiSelect: Optional[List[str]] = Field(default_factory=list)
    qualityAssuranceExposure: Optional[bool] = Field(default=False)
    technicalSkills: Optional[List[str]] = Field(default_factory=list)
    softSkills: Optional[List[str]] = Field(default_factory=list)
    databases: Optional[List[str]] = Field(default_factory=list)
    cloudPlatforms: Optional[List[str]] = Field(default_factory=list)
    devTools: Optional[List[str]] = Field(default_factory=list)
    yearsOfExperience: Optional[List[SkillExperience]] = Field(default_factory=list)

class Preferences(BaseModel):
    desiredRoles: Optional[List[str]] = Field(default_factory=list)
    desiredLocations: Optional[List[str]] = Field(default_factory=list)
    expectedSalaryMin: Optional[float] = None
    expectedSalaryMax: Optional[float] = None
    workModePreference: Optional[str] = None
    preferredShiftPreference: Optional[List[str]] = Field(default_factory=list)
    preferredJoiningTimeline: Optional[str] = None

class Internship(BaseModel):
    companyName: Optional[str] = None
    title: Optional[str] = None
    # Simplified from datetime to string
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    description: Optional[str] = None

class Project(BaseModel):
    title: Optional[str] = None
    role: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    techStack: Optional[List[str]] = Field(default_factory=list)
    # Simplified from datetime to string
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    projectUrl: Optional[str] = None
    githubUrl: Optional[str] = None
    liveUrl: Optional[str] = None
    isPersonalProject: Optional[bool] = Field(default=False)
    teamSize: Optional[int] = None
    responsibilities: Optional[List[str]] = Field(default_factory=list)
    achievements: Optional[List[str]] = Field(default_factory=list)

class Accomplishment(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    issuer: Optional[str] = None
    # Simplified from datetime to string
    date: Optional[str] = None
    details: Optional[str] = None

class CompetitiveExam(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    scoreOrRank: Optional[str] = None
    details: Optional[str] = None

class Skill(BaseModel):
    name: str
    level: Optional[str] = Field(default='Intermediate')
    years: Optional[float] = Field(default=0.0)

class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None

# ---
# Main Simplified Candidate Schema for Parsing
# ---

class Candidate(BaseModel):
    """
    A simplified, lean version of the Candidate schema, designed
    specifically for AI parsing. It removes all complex formats (like
    datetime), metadata, and legacy/duplicate fields.
    """
    
    # Personal Details
    phone: Optional[str] = None
    fullName: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    preferredName: Optional[str] = None
    # Simplified from EmailStr to str
    email: Optional[str] = None
    # Simplified from date to str
    dob: Optional[str] = None
    gender: Optional[str] = None
    martialStatus: Optional[str] = None
    nationality: Optional[str] = None

    # Location
    currentLocation: Optional[Location] = None
    preferredLanguages: Optional[List[str]] = Field(default_factory=list)

    # Employment Summary
    totalExperienceYears: Optional[float] = Field(default=0.0)
    currentOrLastEmployer: Optional[str] = None
    currentOrLastDesignation: Optional[str] = None
    employmentType: Optional[str] = None
    willingToRelocate: Optional[bool] = Field(default=False)
    willingForNightShift: Optional[bool] = Field(default=False)
    headsetAvailable: Optional[bool] = Field(default=False)
    primaryWorkMode: Optional[str] = None
    preferredContactMethod: Optional[str] = None

    # --- Main Data Lists (Modern Fields Only) ---
    experienceEntries: Optional[List[Experience]] = Field(default_factory=list)
    skillSet: Optional[SkillSet] = None
    languageProficiencies: Optional[List[LanguageProficiency]] = Field(default_factory=list)
    educationEntries: Optional[List[Education]] = Field(default_factory=list)
    preferences: Optional[Preferences] = None

    # Profile Summary
    summary: Optional[str] = None

    # --- Legacy/Other Lists (Still useful) ---
    internships: Optional[List[Internship]] = Field(default_factory=list)
    projects: Optional[List[Project]] = Field(default_factory=list)
    accomplishments: Optional[List[Accomplishment]] = Field(default_factory=list)
    competitiveExams: Optional[List[CompetitiveExam]] = Field(default_factory=list)

    # Online presence
    linkedin: Optional[str] = None
    portfolioUrl: Optional[str] = None
    github: Optional[str] = None
    leetcode: Optional[str] = None
    hackerrank: Optional[str] = None
    website: Optional[str] = None

    # Misc
    bio: Optional[str] = None
    jobType: Optional[str] = None

    # Shift & Availability (Simplified)
    preferredShifts: Optional[List[str]] = Field(default_factory=list)
    immediateJoiner: Optional[bool] = Field(default=False)
    noticePeriodDays: Optional[int] = None
    # Simplified from a complex object to a simple string
    weeklyAvailability: Optional[str] = None
    availableForOvertime: Optional[bool] = Field(default=False)
    preferredWorkingHoursWindow: Optional[str] = None
