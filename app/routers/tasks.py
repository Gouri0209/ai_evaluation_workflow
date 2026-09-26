from fastapi import APIRouter, HTTPException

from app.tasks import TASKS, TASKS_BY_ID

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks():
    return [
        {"id": t.id, "difficulty": t.difficulty, "description": t.description,
         "max_steps": t.max_steps}
        for t in TASKS
    ]


@router.get("/{task_id}")
def get_task(task_id: str):
    t = TASKS_BY_ID.get(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="task not found")
    return {
        "id": t.id, "difficulty": t.difficulty, "description": t.description,
        "scenario": t.scenario, "expected_actions": t.expected_actions,
        "forbidden_actions": list(t.forbidden_actions), "max_steps": t.max_steps,
    }
