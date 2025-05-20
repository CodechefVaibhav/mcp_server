import json
from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from app.services.candidate_service import search_candidates
from app.prompts.candidate_prompt import generate_candidate_prompt
import asyncio

router = APIRouter()

async def event_generator(experience: int, location: str, department: str):
    """
    Yields two Server-Sent Events:

    1) prompt — the natural-language instruction sent to the LLM or other agent
       Event name: "prompt"
       Data payload: str

    2) results — the list of candidate records matching the criteria
       Event name: "results"
       Data payload: List[Dict[str, Any]]
    """
    # Step 1: stream the generated prompt
    prompt = generate_candidate_prompt(experience, location, department)
    yield {"event": "prompt", "data": prompt}
    await asyncio.sleep(1)

    # Step 2: stream the search results
    results = search_candidates(experience, location, department)
    yield {"event": "results", "data": json.dumps(results)}


@router.get(
    "/candidate/search/sse",
    status_code=200,
    summary="Search candidates with Server-Sent Events"
)
async def candidate_search_sse(
    experience: int = Query(..., ge=0, description="Minimum years of experience"),
    location:   str = Query(...,       description="Candidate location"),
    department: str = Query(...,       description="Functional department")
) -> EventSourceResponse:
    """
    Streams a two-step SSE:
      1) **prompt**:
         - Event name: "prompt"
         - Data:    a string instruction, e.g.
                    "Find candidates with at least 5 years of experience, located in Mumbai, in the Engineering department."

      2) **results**:
         - Event name: "results"
         - Data:    a JSON array of candidate objects matching the criteria, e.g.
           [
             {"id":"1","name":"Alice",…},
             {"id":"3","name":"Charlie",…}
           ]
    """
    return EventSourceResponse(event_generator(experience, location, department))
