"""
tools/jd_matcher.py
-------------------
Matches a parsed resume against a job description using a Groq LLM.
Returns a structured JSON response evaluating the fit. Handles 429 rate limits gracefully.
"""

import time
import logging
from typing import List, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq

from config.settings import settings
from config.prompts import MATCH_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class MatchResult(BaseModel):
    """Pydantic model for the structured JSON output from the LLM."""
    score: int = Field(
        description="An integer from 0 to 100 representing how accurately the candidate matches the job."
    )
    reasoning: str = Field(
        description="A concise, 2-3 sentence honest explanation of why this specific score was awarded."
    )
    key_matches: List[str] = Field(
        description="List of specific skills, tools, or projects from the resume that directly match the role."
    )
    gaps: List[str] = Field(
        description="List of missing technologies, domain requirements, or qualifications from the job description."
    )


def match_resume_to_job(resume_text: str, job_description: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    Compares a candidate's resume to a job description using a Groq LLM
    and returns a structured evaluation with realistic, differentiated scoring.
    Retries automatically on 429 rate limits and falls back across active models.
    """
    candidate_models = [
        settings.groq_model,
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "qwen/qwen3.6-27b",
        "groq/compound"
    ]
    # Deduplicate while preserving order
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    parser = JsonOutputParser(pydantic_object=MatchResult)
    prompt = ChatPromptTemplate.from_messages([
        ("system", MATCH_SYSTEM_PROMPT + "\n\n{format_instructions}"),
        ("human", "### Candidate Resume:\n{resume_text}\n\n### Target Job Description:\n{job_description}")
    ])

    for model_name in models_to_try:
        try:
            llm = ChatGroq(
                api_key=settings.groq_api_key,
                model=model_name,
                temperature=0.15,
            )
            chain = prompt | llm | parser

            for attempt in range(1, max_retries + 1):
                try:
                    result = chain.invoke({
                        "resume_text": resume_text[:3000],
                        "job_description": job_description[:3000],
                        "format_instructions": parser.get_format_instructions()
                    })
                    if "score" in result:
                        result["score"] = int(result["score"])
                    return result
                except Exception as e:
                    err_str = str(e)
                    if "404" in err_str or "decommissioned" in err_str or "model_not_found" in err_str:
                        logger.warning(f"Groq model {model_name} unavailable ({e}), trying next fallback model...")
                        break  # Break inner retry loop to try next model
                    elif "429" in err_str or "Rate limit" in err_str or "rate_limit" in err_str:
                        wait_secs = 4 * attempt
                        logger.warning(f"Groq 429 Rate limit hit on {model_name} (attempt {attempt}/{max_retries}), retrying in {wait_secs}s…")
                        time.sleep(wait_secs)
                    else:
                        logger.warning(f"Error evaluating on {model_name} (attempt {attempt}/{max_retries}): {e}")
                        time.sleep(2)
        except Exception as outer_e:
            logger.warning(f"Failed to initialize model {model_name}: {outer_e}")
            continue

    return {
        "score": 0,
        "reasoning": "Error or rate limit during matching evaluation.",
        "key_matches": [],
        "gaps": []
    }
