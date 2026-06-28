from fastapi import APIRouter

from app.schemas import MessageResponse, WatchlistCreate

router = APIRouter(prefix="/watchlists", tags=["Watchlist API"])


@router.post("", response_model=MessageResponse)
def create_watchlist(payload: WatchlistCreate) -> MessageResponse:
    return MessageResponse(message=f"watchlist contract accepted for {payload.market}")


@router.get("", response_model=MessageResponse)
def list_watchlists() -> MessageResponse:
    return MessageResponse(message="watchlist list contract")
