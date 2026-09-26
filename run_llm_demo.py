"""Runs one benchmark task with a real LLM deciding actions, instead of the
scripted MockAgent. Requires ANTHROPIC_API_KEY to be set.

    export ANTHROPIC_API_KEY=sk-ant-...
    python run_llm_demo.py
"""
import os
import sys

from app.database import SessionLocal, reset_db
from app.environment import Environment
from app.tasks import TASKS_BY_ID
from app.evaluator import evaluate

if not os.getenv("ANTHROPIC_API_KEY"):
    sys.exit("Set ANTHROPIC_API_KEY first: export ANTHROPIC_API_KEY=sk-ant-...")

from app.llm_agent import LLMAgent  # imported after the key check

TASK_ID = sys.argv[1] if len(sys.argv) > 1 else "medium_refund_damaged_item"

reset_db()
db = SessionLocal()
task = TASKS_BY_ID[TASK_ID]
agent = LLMAgent()

env_row = Environment.create(db, name=f"llm_{task.id}", scenario=task.scenario)
env = Environment(db, env_row.id, task_id=task.id)

print(f"Task: {task.description}\n")
agent.solve(env, db, env_row.id, task)

result = evaluate(db, env_row.id, task)
status = "PASS" if result.task_success else "FAIL"
print(f"\n[{status}] reward={result.reward:.2f} precision={result.action_precision:.2f} "
      f"recall={result.action_recall:.2f} steps={result.steps_taken} "
      f"violations={result.policy_violations}")

db.close()
