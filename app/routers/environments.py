from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.environment import Environment, ActionError

router = APIRouter(prefix="/environments", tags=["environments"])


@router.post("", response_model=schemas.EnvironmentOut)
def create_environment(payload: schemas.EnvironmentCreate, db: Session = Depends(get_db)):
    try:
        env = Environment.create(db, payload.name, payload.scenario)
    except ActionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return env


@router.get("/{env_id}", response_model=schemas.EnvironmentOut)
def get_environment(env_id: str, db: Session = Depends(get_db)):
    env = db.query(models.Environment).filter_by(id=env_id).first()
    if not env:
        raise HTTPException(status_code=404, detail="environment not found")
    return env


@router.get("/{env_id}/trajectory")
def get_trajectory(env_id: str, db: Session = Depends(get_db)):
    actions = (
        db.query(models.AgentAction)
        .filter_by(environment_id=env_id)
        .order_by(models.AgentAction.step_number)
        .all()
    )
    return [
        {"step": a.step_number, "action": a.action_name, "success": a.success,
         "task_id": a.task_id}
        for a in actions
    ]
