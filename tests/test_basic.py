import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, reset_db
from app.environment import Environment
from app.tasks import TASKS_BY_ID
from app.agent import MockAgent
from app.evaluator import evaluate
from app.main import app


@pytest.fixture(autouse=True)
def _reset():
    reset_db()
    yield


def test_refund_damaged_item_succeeds():
    db = SessionLocal()
    task = TASKS_BY_ID["medium_refund_damaged_item"]
    env_row = Environment.create(db, "t1", task.scenario)
    env = Environment(db, env_row.id, task_id=task.id)
    MockAgent().solve(env, db, env_row.id, task)
    result = evaluate(db, env_row.id, task)
    assert result.task_success is True
    assert result.policy_violations == 0
    db.close()


def test_refund_on_ok_item_is_denied_not_issued():
    db = SessionLocal()
    task = TASKS_BY_ID["medium_reject_ineligible_refund"]
    env_row = Environment.create(db, "t2", task.scenario)
    env = Environment(db, env_row.id, task_id=task.id)
    MockAgent().solve(env, db, env_row.id, task)
    result = evaluate(db, env_row.id, task)
    assert result.task_success is True
    db.close()


def test_direct_refund_on_ineligible_order_raises_policy_violation():
    db = SessionLocal()
    task = TASKS_BY_ID["medium_reject_ineligible_refund"]
    env_row = Environment.create(db, "t3", task.scenario)
    env = Environment(db, env_row.id, task_id=task.id)
    from app import models
    order = db.query(models.Order).filter_by(environment_id=env_row.id).first()
    outcome = env.execute("issue_refund", {"order_id": order.id})
    assert outcome["success"] is False
    assert outcome["result"]["type"] == "PolicyViolation"
    db.close()


def test_api_full_flow():
    client = TestClient(app)
    r = client.post("/environments", json={"name": "api_test", "scenario": "damaged_item_refund"})
    assert r.status_code == 200
    env_id = r.json()["id"]

    r = client.post("/actions", json={
        "environment_id": env_id, "action_name": "check_refund_policy",
        "params": {}, "task_id": "medium_refund_damaged_item",
    })
    assert r.status_code == 200
    assert r.json()["success"] is False  # missing required order_id param

    order = client.get(f"/environments/{env_id}/trajectory")
    assert order.status_code == 200


def test_benchmark_run():
    client = TestClient(app)
    r = client.post("/benchmarks/run", json={
        "task_ids": ["easy_find_customer", "medium_refund_damaged_item"], "agent": "mock",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["total_tasks"] == 2
    assert 0.0 <= body["success_rate"] <= 1.0
