import re
import json
import logging
from openai import OpenAI

# Configure a logger for this module
logger = logging.getLogger(__name__)

# It's good practice to initialize the client once.
# In a real app, API keys should be managed securely (e.g., via config).
try:
    # Using AsyncOpenAI for non-blocking API calls in an async FastAPI context
    client = OpenAI()
    MODEL = "gpt-4o-mini"
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None

def _safe_parse_json(text: str) -> dict | None:
    """
    Safely attempts to parse a JSON string, extracting the first valid JSON object
    if the string contains surrounding text.
    """
    try:
        # First, try to load the whole string
        return json.loads(text)
    except json.JSONDecodeError:
        # If that fails, search for a JSON object within the string
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.warning("Found a JSON-like block but failed to parse it.")
                return None
    return None

async def evaluate_interview_transcript(
    transcript: dict,
    evaluation_template: str,
    job_description: str,
    resume_text: str,
) -> dict:
    """
    Evaluates a candidate's interview transcript using an LLM.

    Args:
        transcript: The interview transcript as a dictionary.
        evaluation_template: The system prompt/template for the LLM.
        job_description: The job description text.
        resume_text: The candidate's resume text.

    Returns:
        A dictionary containing the structured evaluation.
    """
    if not client:
        raise ConnectionError("OpenAI client is not initialized. Check API key and configuration.")

    # Construct the prompts
    system_prompt = evaluation_template
    user_prompt = (
        f"Transcript JSON:\n{json.dumps(transcript, indent=2)}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Candidate Resume:\n{resume_text}\n\n"
        "Please return the evaluation JSON exactly as required by the system prompt."
    )

    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,  # Lower temperature for more deterministic output
            response_format={"type": "json_object"} # Use JSON mode for reliability
        )

        response_text = response.choices[0].message.content
        parsed_json = _safe_parse_json(response_text)

        if not parsed_json:
            logger.error("Failed to parse JSON from model output.")
            return {"error": "Failed to parse model output", "raw_output": response_text}

        return parsed_json

    except Exception as e:
        logger.exception("An error occurred while calling the OpenAI API.")
        raise RuntimeError(f"OpenAI API call failed: {e}")
