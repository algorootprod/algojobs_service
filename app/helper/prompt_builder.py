def create_interview_prompt(resume: str, job_description: str, interview_template: str) -> str:
    """
    Merges the candidate resume, job description, and interview template
    into a single, comprehensive prompt for the AI interviewer agent.
    """
    
    prompt = f"""
{interview_template}

Here is the context for the interview you are about to conduct.

--- JOB DESCRIPTION ---
{job_description}
--- END JOB DESCRIPTION ---


--- CANDIDATE RESUME ---
{resume}
--- END CANDIDATE RESUME ---

Please begin the interview when you are ready. Greet the candidate by name and start with your first question.
"""
    return prompt
