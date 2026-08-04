from fastapi import APIRouter

router = APIRouter()

@router.get("", status_code=200)
def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy"}
