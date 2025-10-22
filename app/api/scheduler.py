import logging
import uuid
from fastapi import APIRouter, HTTPException
from app import schemas
from app.services.dispatch_service import create_token_with_agent_dispatch
from app.helpers import prompt_builder
from app.services.agent_registry import agent_registry
from app.core.entrypoint_function import entrypoint
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/schedule", response_model=schemas.ScheduleResponse)
async def schedule_interview(req: schemas.ScheduleRequest):
    """
    Schedules a new AI-powered interview.

    This endpoint takes all necessary information (resume, JD, templates)
    and generates a unique token for the interview.
    """
    try:
        agent_instructions = prompt_builder.create_interview_prompt(
            resume=req.candidate_resume,
            job_description=req.job_description,
            interview_template=req.interview_template
        )

        room_name = f"interview-{uuid.uuid4()}"  # Generate a random room name using UUID
        agent_name = f"agent-{uuid.uuid4()}"  # Generate a random agent name using UUID

        token = create_token_with_agent_dispatch(
            agent_name=agent_name,
            room_name=room_name,
            metadata={"prompt": agent_instructions},
            identity=str(req.candidate_id)  # use candidate_id as participant identity
        )

        mgr, sched_task = await agent_registry.create_and_schedule(
        agent_name=agent_name,
        entrypoint=entrypoint,  # closure to pass req/meta
        start_time=req.interview_time,
        room_name=room_name,
        token=token,
        )

        if not token:
            logger.error("Failed to create LiveKit token for agent dispatch")
            raise HTTPException(status_code=500, detail="Failed to create access token for interview.")

        return schemas.ScheduleResponse(
            message="Interview scheduled successfully. Awaiting candidate to join at the scheduled time.",
            candidate_id=req.candidate_id,
            agent_name=agent_name,
            room_name=room_name,
            scheduled_time=req.interview_time,
            token=token,
        )

    except Exception as e:
        logger.exception(f"Error scheduling interview for candidate {req.candidate_id}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule interview: {e}")

@router.post("/stop/{agent_name}")
async def stop_interview(agent_name: str):
    """
    Force-stop a running AI interview worker.
    """
    ok = await agent_registry.stop_agent(agent_name)
    if not ok:
        raise HTTPException(status_code=500, detail=f"Failed to stop agent {agent_name}")
    return {"message": f"Agent {agent_name} stopped successfully."}

