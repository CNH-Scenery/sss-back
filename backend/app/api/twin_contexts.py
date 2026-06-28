from fastapi import APIRouter

from app.schemas import TwinContextGenerateResponse

router = APIRouter(prefix="/twin-contexts", tags=["TwinContext API"])


@router.post("/generate", response_model=TwinContextGenerateResponse)
def generate_twin_context() -> TwinContextGenerateResponse:
    return TwinContextGenerateResponse()


@router.get("/latest", response_model=TwinContextGenerateResponse)
def get_latest_twin_context() -> TwinContextGenerateResponse:
    return TwinContextGenerateResponse()
