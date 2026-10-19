"""GET /api/case/all"""

from fastapi import APIRouter  # noqa: I001

from ..validators import CaseOut
from ..services import chat_service

router = APIRouter(prefix="/api/case", tags=["case"])


@router.get("/all", response_model=list[CaseOut])
def list_all_cases() -> list[CaseOut]:
    return chat_service.list_cases()
