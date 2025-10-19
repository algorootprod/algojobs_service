import uuid
import requests
from urllib.parse import quote_plus
from livekit import api

from app.core.config import settings

def _generate_token(identity: str, name: str, room: str) -> str:
    """Generates a LiveKit JWT token for a participant."""
    if not all([settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET]):
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set.")
        
    access_token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(name)
        .with_grants(api.VideoGrants(room_join=True, room=room))
    )
    return access_token.to_jwt()

def _get_tiny_url(long_url: str) -> str:
    """Shortens a URL using the TinyURL API."""
    if not settings.TINYURL_API_KEY:
        # If no key, return the long URL as a fallback
        return long_url

    api_url = "https://api.tinyurl.com/create"
    headers = {
        "Authorization": f"Bearer {settings.TINYURL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"url": long_url}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("tiny_url", long_url)
    except requests.exceptions.RequestException:
        # On failure, return the original URL
        return long_url

def create_meeting_link(room_name: str, participant_name: str) -> str:
    """
    Creates a unique, shareable meeting link for a participant.
    """
    user_identity = f"user-{uuid.uuid4().hex[:8]}"
    
    token = _generate_token(identity=user_identity, name=participant_name, room=room_name)
    
    # Construct the full meeting URL
    meet_link = (
        f"{settings.MEET_HOST}?liveKitUrl={quote_plus(settings.LIVEKIT_WS_URL)}"
        f"&token={quote_plus(token)}"
    )
    
    # Shorten the URL for easier sharing
    short_link = _get_tiny_url(meet_link)
    return short_link
