import logging
from fastapi import APIRouter, HTTPException

from app.api.v1 import schemas
from app.services import meeting_service
from app.helpers import prompt_builder

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/schedule", response_model=schemas.ScheduleResponse)
def schedule_interview(req: schemas.ScheduleRequest):
    """
    Schedules a new AI-powered interview.

    This endpoint takes all necessary information (resume, JD, templates)
    and generates a unique meeting link for the interview.

    **Note:** In a full production system, this would also create a record in a
    database and schedule a job for the `agent_worker` to join the call at the
    specified time.
    """
    try:
        # 1. Generate the prompt for the AI interviewer agent
        # (The evaluation template is used post-interview, so it's not included here)
        agent_instructions = prompt_builder.create_interview_prompt(
            resume=req.candidate_resume,
            job_description=req.job_description,
            interview_template=req.interview_template
        )

        # 2. Generate a unique meeting link
        meeting_link = meeting_service.create_meeting_link(
            room_name=f"interview-{req.candidate_id}",
            participant_name=req.candidate_name
        )

        if not meeting_link:
            raise HTTPException(status_code=500, detail="Failed to generate meeting link. Check LiveKit/TinyURL credentials.")

        # 3. (Production step) Save interview details to a database
        # This would include the agent_instructions, meeting_link, scheduled_time,
        # evaluation_template, and a status (e.g., 'SCHEDULED').
        # A background worker would then poll this database.
        logger.info(f"Successfully scheduled interview for candidate: {req.candidate_id}")
        logger.info(f"Agent prompt length: {len(agent_instructions)} characters.")
        logger.info(f"Meeting link generated: {meeting_link}")


        return schemas.ScheduleResponse(
            message="Interview scheduled successfully. Awaiting candidate to join at the scheduled time.",
            candidate_id=req.candidate_id,
            scheduled_time=req.interview_time,
            meeting_link=meeting_link,
        )

    except Exception as e:
        logger.exception(f"Error scheduling interview for candidate {req.candidate_id}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule interview: {e}")
