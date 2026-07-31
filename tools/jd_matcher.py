"""
tools/jd_matcher.py
-------------------
Matches a parsed resume against a job description using a Groq LLM.
Returns a structured JSON response evaluating the fit.
"""

from typing import List, Dict, Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq

from config.settings import settings
from config.prompts import MATCH_SYSTEM_PROMPT


class MatchResult(BaseModel):
    """Pydantic model for the structured JSON output from the LLM."""
    score: int = Field(
        description="An integer from 0 to 100 representing how well the resume matches the job description."
    )
    reasoning: str = Field(
        description="A concise explanation of why this score was given."
    )
    key_matches: List[str] = Field(
        description="List of key skills or experiences from the resume that strongly match the job."
    )
    gaps: List[str] = Field(
        description="List of critical skills or requirements from the job description missing in the resume."
    )


def match_resume_to_job(resume_text: str, job_description: str) -> Dict[str, Any]:
    """
    Compares a candidate's resume to a job description using a Groq LLM
    and returns a structured evaluation.

    Args:
        resume_text (str): The parsed text of the candidate's resume.
        job_description (str): The full text of the job description.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - score (int): 0-100 match score.
            - reasoning (str): Explanation for the score.
            - key_matches (List[str]): Matching elements.
            - gaps (List[str]): Missing elements.
    """
    # 1. Initialize the Groq LLM
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.0  # Keep it deterministic for scoring
    )

    # 2. Setup the JSON output parser with our Pydantic model
    parser = JsonOutputParser(pydantic_object=MatchResult)

    # 3. Create the prompt template
    # We use the MATCH_SYSTEM_PROMPT from config.prompts and inject the formatting instructions
    prompt = ChatPromptTemplate.from_messages([
        ("system", MATCH_SYSTEM_PROMPT + "\n\n{format_instructions}"),
        ("human", "Resume:\n{resume_text}\n\nJob Description:\n{job_description}")
    ])

    # 4. Construct the LCEL chain
    chain = prompt | llm | parser

    # 5. Invoke the chain
    try:
        result = chain.invoke({
            "resume_text": resume_text,
            "job_description": job_description,
            "format_instructions": parser.get_format_instructions()
        })
        return result
    except Exception as e:
        # In case of parsing or API errors, return a safe fallback dictionary
        return {
            "score": 0,
            "reasoning": f"Error during matching: {str(e)}",
            "key_matches": [],
            "gaps": []
        }
