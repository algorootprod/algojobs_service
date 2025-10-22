import json
import logging
from typing import Optional, Dict, Any
from livekit import api
from app.core.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Dispatch")

def generate_token(identity: str, name: str, room: str) -> str:
    """Generates a LiveKit JWT token for a participant.""" 
    access_token = (
        api.AccessToken(config.LIVEKIT_API_KEY, config.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(api.VideoGrants(room_join=True, room=room))
    )
    return access_token.to_jwt()


async def create_agent_dispatch(
    agent_name: str,
    room_name: str,
    prompt: str,
) -> Optional[api.AgentDispatch]:

    if prompt:
        metadata = {
                    "prompt": prompt, 
                    }
    else:
        metadata["prompt"] = "Your and interview agent named karan"

    # Create API client
    lkapi = api.LiveKitAPI(url=config.LIVEKIT_URL, api_key=config.LIVEKIT_API_KEY, api_secret=config.LIVEKIT_API_SECRET)
    
    try:
        request = api.CreateAgentDispatchRequest(
            agent_name=agent_name,
            room=room_name,
            metadata=json.dumps(metadata),
        )
        
        # Create the dispatch
        dispatch = await lkapi.agent_dispatch.create_dispatch(request)
        return dispatch
        
    except Exception as e:
        logger.error(f"Failed to create agent dispatch: {e}")
        return None
        
    finally:
        # Always close the API client
        await lkapi.aclose()

from livekit.api import (
  AccessToken,
  RoomAgentDispatch,
  RoomConfiguration,
  VideoGrants,
)

def create_token_with_agent_dispatch(
    agent_name: str,
    room_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    identity: str = "my_participant",
) -> Optional[str]:
    """
    Create a LiveKit JWT access token configured with an agent dispatch.

    Args:
        agent_name: Name of the registered LiveKit agent to dispatch.
        room_name: Target room where the agent will join.
        metadata: Arbitrary metadata dict passed to the agent.
        identity: Optional identity string for the participant (default: "my_participant").

    Returns:
        JWT token string on success, or None on failure.
    """
    if not agent_name:
        logger.error("create_token_with_agent_dispatch: agent_name is required")
        return None
    if not room_name:
        logger.error("create_token_with_agent_dispatch: room_name is required")
        return None

    # Safe metadata serialization
    metadata_json = "{}"
    if metadata:
        try:
            metadata_json = json.dumps(metadata, default=str)
        except Exception:
            logger.exception("Failed to serialize metadata; falling back to empty object")
            metadata_json = "{}"

    try:
        # Create the token with the given grants
        token = (
            AccessToken()
            .with_identity(identity)
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .with_room_config(
                RoomConfiguration(
                    agents=[RoomAgentDispatch(agent_name=agent_name, metadata=metadata_json)]
                )
            )
            .to_jwt()
        )

        logger.info(
            f"Created LiveKit token with agent dispatch: agent='{agent_name}', room='{room_name}', identity='{identity}'"
        )
        return token

    except Exception as e:
        logger.exception(f"Failed to create LiveKit access token: {e}")
        return None