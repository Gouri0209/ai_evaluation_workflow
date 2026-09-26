import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.evaluator import evaluate
from app.tasks import TASKS_BY_ID
from app.schemas import EvaluateRequest, EvaluationOut

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def _to_out(row: models.Evaluation) -> EvaluationOut:
    return EvaluationOut(
        id=row.id, task_id=row.task_id, task_success=row.task_success,
        action_precision=row.action_precision, action_recall=row.action_recall,
        policy_violations=row.policy_violations, invalid_actions=row.invalid_actions,
        steps_taken=row.steps_taken, reward=row.reward, details=json.loads(row.details),
    )


@router.post("", response_model=EvaluationOut)
def run_evaluation(payload: EvaluateRequest, db: Session = Depends(get_db)):
    env_row = db.query(models.Environment).filter_by(id=payload.environment_id).first()
    if not env_row:
        raise HTTPException(status_code=404, detail="environment not found")
    task = TASKS_BY_ID.get(payload.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    row = evaluate(db, payload.environment_id, task)
    return _to_out(row)


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
    row = db.query(models.Evaluation).filter_by(id=evaluation_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return _to_out(row)
