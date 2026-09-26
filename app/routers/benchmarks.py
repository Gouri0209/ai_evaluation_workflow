from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.environment import Environment
from app.tasks import TASKS, TASKS_BY_ID
from app.agent import AGENTS
from app.evaluator import evaluate
from app.schemas import BenchmarkRunRequest, BenchmarkResultOut
from app.routers.evaluations import _to_out

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post("/run", response_model=BenchmarkResultOut)
def run_benchmark(payload: BenchmarkRunRequest, db: Session = Depends(get_db)):
    if payload.agent not in AGENTS:
        raise HTTPException(status_code=400, detail=f"unknown agent '{payload.agent}'")
    agent = AGENTS[payload.agent]()

    task_ids = payload.task_ids or [t.id for t in TASKS]
    tasks = []
    for tid in task_ids:
        t = TASKS_BY_ID.get(tid)
        if not t:
            raise HTTPException(status_code=404, detail=f"task '{tid}' not found")
        tasks.append(t)

    evaluations = []
    for task in tasks:
        env_row = Environment.create(db, name=f"bench_{task.id}", scenario=task.scenario)
        env = Environment(db, env_row.id, task_id=task.id)
        agent.solve(env, db, env_row.id, task)
        eval_row = evaluate(db, env_row.id, task)
        evaluations.append(_to_out(eval_row))

    n = len(evaluations)
    result = BenchmarkResultOut(
        total_tasks=n,
        success_rate=round(sum(e.task_success for e in evaluations) / n, 3) if n else 0,
        avg_reward=round(sum(e.reward for e in evaluations) / n, 3) if n else 0,
        avg_precision=round(sum(e.action_precision for e in evaluations) / n, 3) if n else 0,
        avg_recall=round(sum(e.action_recall for e in evaluations) / n, 3) if n else 0,
        total_policy_violations=sum(e.policy_violations for e in evaluations),
        evaluations=evaluations,
    )
    return result
