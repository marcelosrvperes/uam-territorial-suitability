from fastapi import APIRouter

from uam_territorial_suitability.criteria import CRITERIA, Criterion

router = APIRouter()


@router.get("/criteria", response_model=list[Criterion])
def list_criteria() -> list[Criterion]:
    """Return the territorial aptitude criteria currently defined for the tool."""
    return CRITERIA


@router.post("/aptitude")
def compute_aptitude() -> None:
    """Compute territorial aptitude for a candidate site given user-supplied datasets.

    Not implemented yet — Gate G3 is scaffolding the project structure first.
    The actual pipeline (validate → apply criteria → aggregate via AHP → output)
    lands in a follow-up iteration.
    """
    raise NotImplementedError("Aptitude pipeline not implemented yet (Gate G3 in progress).")
