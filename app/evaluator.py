import json
from typing import Dict, Any
from sqlalchemy.orm import Session

from app import models
from app.tasks import Task


def evaluate(db: Session, environment_id: str, task: Task) -> Dict[str, Any]:
    actions = (
        db.query(models.AgentAction)
        .filter_by(environment_id=environment_id, task_id=task.id)
        .order_by(models.AgentAction.step_number)
        .all()
    )

    steps_taken = len(actions)
    taken_names = [a.action_name for a in actions]
    taken_set = set(taken_names)
    expected_set = set(task.expected_actions)

    invalid_actions = sum(
        1 for a in actions
        if not a.success and json.loads(a.result).get("type") != "PolicyViolation"
    )
    policy_violations = sum(
        1 for a in actions
        if a.action_name in task.forbidden_actions
        or json.loads(a.result).get("type") == "PolicyViolation"
    )

    precision = len(taken_set & expected_set) / len(taken_set) if taken_set else 0.0
    recall = len(taken_set & expected_set) / len(expected_set) if expected_set else 1.0

    within_budget = steps_taken <= task.max_steps
    final_state_ok = task.final_check(db, environment_id)
    task_success = final_state_ok and within_budget and policy_violations == 0

    reward = (
        0.5 * (1.0 if task_success else 0.0)
        + 0.2 * recall
        + 0.1 * precision
        + 0.1 * (1.0 if within_budget else 0.0)
        - 0.15 * policy_violations
        - 0.05 * invalid_actions
    )
    reward = max(0.0, min(1.0, reward))

    details = {
        "actions_taken": taken_names,
        "expected_actions": task.expected_actions,
        "forbidden_actions": list(task.forbidden_actions),
        "within_step_budget": within_budget,
        "final_state_correct": final_state_ok,
    }

    row = models.Evaluation(
        environment_id=environment_id, task_id=task.id, task_success=task_success,
        action_precision=round(precision, 3), action_recall=round(recall, 3),
        policy_violations=policy_violations, invalid_actions=invalid_actions,
        steps_taken=steps_taken, reward=round(reward, 3), details=json.dumps(details),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
