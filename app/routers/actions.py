from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.environment import Environment
from app.schemas import ActionRequest, ActionResult

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post("", response_model=ActionResult)
def execute_action(payload: ActionRequest, db: Session = Depends(get_db)):
    env_row = db.query(models.Environment).filter_by(id=payload.environment_id).first()
    if not env_row:
        raise HTTPException(status_code=404, detail="environment not found")

    env = Environment(db, payload.environment_id, task_id=payload.task_id)
    return env.execute(payload.action_name, payload.params)
