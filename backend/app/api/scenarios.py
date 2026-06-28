from fastapi import APIRouter
from fastapi import Depends
from sqlmodel import Session, select

from app.db import get_session, seed_anonymous_user
from app.models import Scenario
from app.schemas import ScenarioListResponse
from app.schemas import ScenarioItem
from app.seed import seed_static_scenarios

router = APIRouter(prefix="/scenarios", tags=["Scenario API"])


@router.get("", response_model=ScenarioListResponse)
def list_scenarios(session: Session = Depends(get_session)) -> ScenarioListResponse:
    seed_anonymous_user(session)
    seed_static_scenarios(session)
    scenarios = session.exec(select(Scenario).order_by(Scenario.id)).all()
    return ScenarioListResponse(
        items=[
            ScenarioItem(
                id=str(scenario.id),
                market=scenario.market,
                timeframe=scenario.timeframe,
                description=scenario.description,
                features_snapshot=scenario.features_snapshot,
                chart_data=scenario.chart_data,
            )
            for scenario in scenarios
        ]
    )
