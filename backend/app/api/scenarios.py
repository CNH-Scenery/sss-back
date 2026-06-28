from fastapi import APIRouter

from app.schemas import ScenarioListResponse

router = APIRouter(prefix="/scenarios", tags=["Scenario API"])


@router.get("", response_model=ScenarioListResponse)
def list_scenarios() -> ScenarioListResponse:
    return ScenarioListResponse(items=[])
