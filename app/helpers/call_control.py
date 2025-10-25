from livekit.agents import function_tool, RunContext, get_job_context
from livekit.api import DeleteRoomRequest
from aiohttp.client_exceptions import ClientConnectionError
from livekit import api
import logging
import aiohttp
import json
from livekit import rtc
from aiohttp.client_exceptions import ClientOSError
import ssl
from typing import Optional, Mapping
from livekit.api.twirp_client import TwirpError
from app.call_tools.call_logger import CallLogger
import re
from livekit.rtc.participant import RemoteParticipant

logger = logging.getLogger("call_control")

async def hangup(reason: Optional[str] = None):
    """Helper function to hang up the call by deleting the room"""
    try:
        job_ctx = get_job_context()
        room_name = job_ctx.room.name

        call_logger = CallLogger()
        call_logger.mark_call_end(room_name=room_name, hangup_reason=reason)

        logger.info(f"Attempting to delete room: {room_name}")

        await job_ctx.api.room.delete_room(DeleteRoomRequest(room=room_name))
        logger.info(f"Room '{room_name}' deleted successfully.")

    except TwirpError as e:
        if e.code == "not_found":
            logger.warning(f"Room '{room_name}' not found during deletion. May have already been deleted.")
        else:
            logger.error(f"Twirp error while deleting room: {e}")
            raise

    except ClientOSError as e:
        if isinstance(e.__cause__, ssl.SSLError) and "APPLICATION_DATA_AFTER_CLOSE_NOTIFY" in str(e.__cause__):
            logger.warning("SSL error during delete_room: room likely already closed. Safe to ignore.")
        else:
            logger.error(f"Unexpected ClientOSError while deleting room: {e}")
            raise

    except (RuntimeError, ClientConnectionError) as e:
        if "Session is closed" in str(e) or "Server disconnected" in str(e):
            logger.warning("LiveKit session already closed. Skipping delete_room.")
        else:
            logger.error(f"Unexpected connection/runtime error while deleting room: {e}")
            raise

    except Exception as e:
        logger.error(f"Unhandled error while deleting room: {e}")
        raise

@function_tool()
async def end_call(ctx: RunContext) -> dict:
    """
    Called when the user wants to end the call.
    """
    try:
        await ctx.session.generate_reply(instructions="Thanks the user for their precious time.")
        
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()

        await hangup(reason="Agent ended the call")

        return {
            "status": "success",
            "message": "Call ended and room deleted."
        }

    except aiohttp.ClientError as e:
        logger.warning(f"Network error while deleting room: {e}")
        return {
            "status": "warning",
            "message": "Call ended, but room deletion may have failed due to network issue.",
            "error": str(e)
        }

    except Exception as e:
        logger.error(f"Unexpected error in end_call tool: {e}")
        return {
            "status": "error",
            "message": "Failed to end the call gracefully.",
            "error": str(e)
        }
