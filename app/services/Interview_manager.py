from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
import uuid
import logging
from typing import Optional, Dict, Any
from app.schemas import Job, JobDescription ,Resume
from app.services.mongoDB_service import MongoService
from app.services.dispatch_service import create_token_with_agent_dispatch
from app.helpers import prompt_builder
from app.services.agent_registry import agent_registry
from app.core.entrypoint_function import entrypoint
from app.schemas import ScheduleResponse

router = APIRouter()
logger = logging.getLogger(__name__)

class InterviewManager:
    """
    Combined flow:
      1) lookup interview_keys by candidateKey
      2) ensure interviewTime <= now (or missing -> proceed)
      3) fetch resume and job using MongoService helpers and normalize to strings
      4) pick predefined interview + evaluation templates (simple heuristic)
      5) build prompt via prompt_builder.create_interview_prompt
      6) create token passing agent_id from interview_keys, and start agent via registry
    """

    def __init__(self, mongo_service: MongoService):
        self.mongo = mongo_service

    def _find_interview_by_candidate_key(self, candidate_key: str) -> Optional[Dict[str, Any]]:
        coll = self.mongo._get_collection("interview_keys")
        try:
            doc = coll.find_one({"candidateKey": candidate_key})
            return doc
        except Exception as e:
            logger.exception("Error querying interview_keys for candidateKey=%s : %s", candidate_key, e)
            raise HTTPException(status_code=500, detail="Database error when searching interview_keys")

    def _parse_interview_time(self, interview_time_raw: Any) -> Optional[datetime]:
        """
        Normalize interviewTime to an aware UTC datetime or return None if not present.
        Accepts datetime or ISO string. Treat naive datetimes as UTC.
        """
        if interview_time_raw is None:
            return None
        from datetime import datetime as _dt
        try:
            if isinstance(interview_time_raw, _dt):
                dt = interview_time_raw
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
            if isinstance(interview_time_raw, str):
                # try ISO parsing; use fromisoformat as fallback
                try:
                    # Python 3.11+ has fromisoformat improved; we use it as fallback if dateutil not present
                    from dateutil import parser as _parser  # optional
                    dt = _parser.isoparse(interview_time_raw)
                except Exception:
                    dt = _dt.fromisoformat(interview_time_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt
        except Exception:
            logger.exception("Failed to parse interviewTime: %s", interview_time_raw)
            return None

        logger.warning("Unknown interviewTime type: %s", type(interview_time_raw))
        return None

    def _normalize_doc_to_str(self, doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Ensure ObjectId fields are converted to str recursively (best-effort).
        MongoService.get_* methods already serialize top-level ObjectId -> str, but interview_keys
        lookup returns raw BSON; this helper converts common nested ObjectId values to strings for prompt builder.
        """
        if doc is None:
            return None

        def convert(value):
            # ObjectId -> str
            try:
                from bson import ObjectId
            except Exception:
                ObjectId = None
            # primitives
            if value is None or isinstance(value, (str, int, float, bool)):
                return value
            # ObjectId
            if ObjectId and isinstance(value, ObjectId):
                return str(value)
            # datetime keep as is
            from datetime import datetime as _dt
            if isinstance(value, _dt):
                return value
            # dict -> recurse
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            # list -> recurse
            if isinstance(value, list):
                return [convert(x) for x in value]
            # fallback to str for unknown types
            try:
                return str(value)
            except Exception:
                return value

        return convert(doc)

    def _pick_templates(self, resume: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, str]:
        """
        Return chosen interview_template and evaluation_template.
        Simple predefined logic: default 'general'/'standard_evaluation_v1', or 'senior' variants if experience >=5.
        """
        interview_template = "general"
        evaluation_template = "standard_evaluation_v1"
        try:
            resume_exp = None
            if isinstance(resume, dict):
                resume_exp = resume.get("totalExperienceYears") or resume.get("totalExperience")
            jd = job.get("jobDescription") if job else None
            jd_level = None
            if jd and isinstance(jd, dict):
                jd_level = jd.get("experienceLevel") or jd.get("employmentType")

            if resume_exp:
                try:
                    if float(resume_exp) >= 5:
                        interview_template = "senior"
                        evaluation_template = "senior_evaluation_v1"
                except Exception:
                    pass

            if jd_level and isinstance(jd_level, str) and "senior" in jd_level.lower():
                interview_template = "senior"
                evaluation_template = "senior_evaluation_v1"
        except Exception:
            logger.exception("Error choosing templates; falling back to defaults")

        return {"interview_template": interview_template, "evaluation_template": evaluation_template}

    async def start_by_candidate_key(self, candidate_key: str) -> ScheduleResponse:
        """
        Accepts candidate_key (query param), validates schedule time, fetches resume/job,
        constructs prompt + token, and starts the agent.
        """
        # 1) fetch interview_keys entry
        interview_doc = self._find_interview_by_candidate_key(candidate_key)
        if not interview_doc:
            raise HTTPException(status_code=404, detail=f"No scheduled interview found for candidateKey={candidate_key}")

        # 1.5) time check: only start if interviewTime <= now (or missing)
        interview_time_raw = interview_doc.get("interviewTime")
        parsed_time = self._parse_interview_time(interview_time_raw)
        now_utc = datetime.now(timezone.utc)
        if parsed_time is not None:
            if parsed_time > now_utc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Interview scheduled for {parsed_time.isoformat()} (UTC). It is not yet time to start."
                )

        # 2) get candidate resume using MongoService helper
        # the interview_keys doc stores candidate as ObjectId; convert -> str then use get_resume_by_id
        candidate_field = interview_doc.get("candidate") or interview_doc.get("candidate_id") or interview_doc.get("candidateId")
        if not candidate_field:
            raise HTTPException(status_code=400, detail="interview_keys entry missing candidate reference")
        candidate_id_str = str(candidate_field)
        try:
            raw_resume = self.mongo.get_resume_by_id(candidate_id_str)
        except Exception:
            logger.exception("Database error fetching resume for id %s", candidate_id_str)
            raise HTTPException(status_code=500, detail="Database error fetching candidate resume")

        if not raw_resume:
            resume_doc = None
        else:
            try:
                resume_doc = Resume.model_validate(raw_resume).model_dump()
            except Exception:
                logger.exception("Resume validation failed for id %s", candidate_id_str)
                raise HTTPException(status_code=500, detail="Invalid resume format")
        if not resume_doc:
            raise HTTPException(status_code=404, detail=f"Candidate resume not found for id {candidate_id_str}")

        # convert resume doc nested ObjectIds to strings (best-effort)
        resume_doc = self._normalize_doc_to_str(resume_doc)

        # 3) get job description using job id
        job_field = interview_doc.get("job") or interview_doc.get("job_id") or interview_doc.get("jobId")
        job_doc = None
        job_id_str = None
        if job_field:
            job_id_str = str(job_field)
            try:
                job_doc = self.mongo.get_job_by_id(job_id_str)
                if not job_doc:
                    job_description = None
                else:
                    # validate job and extract/normalize jobDescription (if present)
                    job = Job.model_validate(job_doc)
                    jd = getattr(job, "jobDescription", None)
                    job_description = None if jd is None else JobDescription.model_validate(jd).model_dump()
            except Exception:
                logger.exception("Error fetching or validating job for id %s", job_id_str)
                job_description = None
            if job_description:
                job_doc = self._normalize_doc_to_str(job_description)
            else:
                logger.warning("Job document not found for id %s; proceeding without job", job_id_str)

        # 4) pick predefined templates and merge with resume & JD to pass to prompt builder
        templates = self._pick_templates(resume_doc or {}, job_doc or {})
        interview_template = templates["interview_template"]
        evaluation_template = templates["evaluation_template"]

        # The create_interview_prompt expects resume, job_description, interview_template
        try:
            agent_instructions = prompt_builder.create_interview_prompt(
                resume=resume_doc,
                job_description=job_doc,
                interview_template=interview_template,
                # if your prompt_builder needs evaluation_template pass as additional arg:
                # evaluation_template=evaluation_template
            )
        except Exception as e:
            logger.exception("Failed to build prompt via prompt_builder: %s", e)
            raise HTTPException(status_code=500, detail="Failed to construct agent prompt")

        # 5) create token, pass agent_id from interview_keys into metadata
        # interview_keys agent id may exist as ObjectId; convert to str
        agent_id_field = interview_doc.get("agentId")
        agent_id_to_pass = str(agent_id_field) if agent_id_field is not None else None

        room_name = f"interview-{uuid.uuid4()}"
        agent_name = f"agent-{uuid.uuid4()}"

        token = create_token_with_agent_dispatch(
            agent_name=agent_name,
            room_name=room_name,
            metadata={"prompt": agent_instructions, "agent_id": agent_id_to_pass},
            identity=candidate_id_str,
        )

        if not token:
            logger.error("Failed to create LiveKit token for agent dispatch for candidate_key=%s", candidate_key)
            raise HTTPException(status_code=500, detail="Failed to create access token for interview.")

        # 6) start the agent via registry (following your instruction — call start_now as shown)
        try:
            mgr, started = await agent_registry.start_now(
                agent_name=agent_name,
                entrypoint=entrypoint,
                room_name=room_name,
            )
        except TypeError:
            # fallback to start_now with token if your registry requires it; preserve behavior
            logger.debug("agent_registry.start_now rejected call without token; retrying with token included")
            mgr, started = await agent_registry.start_now(
                agent_name=agent_name,
                entrypoint=entrypoint,
                room_name=room_name,
                token=token,
            )

        scheduled_time = datetime.now(timezone.utc)
        message = "Agent started immediately. Awaiting candidate to join."
        if not started:
            message = "Agent already running (start request was ignored); token created."

        return ScheduleResponse(
            message=message,
            candidate_id=candidate_id_str,
            agent_name=agent_name,
            room_name=room_name,
            scheduled_time=scheduled_time,
            token=token,
        )


