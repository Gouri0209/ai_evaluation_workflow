"""Runs the full pipeline without needing the API server:
seed environment -> agent solves task -> evaluator scores trajectory.
Also runs the full benchmark suite and the data pipeline.
"""
import json

from app.database import SessionLocal, reset_db
from app.environment import Environment
from app.tasks import TASKS
from app.agent import MockAgent
from app.evaluator import evaluate
from app import data_pipeline


def main():
    reset_db()
    db = SessionLocal()
    agent = MockAgent()

    print("=" * 60)
    print("RUNNING BENCHMARK SUITE")
    print("=" * 60)

    results = []
    for task in TASKS:
        env_row = Environment.create(db, name=f"demo_{task.id}", scenario=task.scenario)
        env = Environment(db, env_row.id, task_id=task.id)
        agent.solve(env, db, env_row.id, task)
        result = evaluate(db, env_row.id, task)
        results.append(result)
        status = "PASS" if result.task_success else "FAIL"
        print(f"[{status}] {task.id:38s} reward={result.reward:.2f} "
              f"precision={result.action_precision:.2f} recall={result.action_recall:.2f} "
              f"steps={result.steps_taken} violations={result.policy_violations}")

    n = len(results)
    print("-" * 60)
    print(f"success_rate={sum(r.task_success for r in results)/n:.2%}  "
          f"avg_reward={sum(r.reward for r in results)/n:.3f}")

    print()
    print("=" * 60)
    print("RUNNING DATA PIPELINE")
    print("=" * 60)
    report = data_pipeline.run()
    print(json.dumps(report, indent=2))

    db.close()


if __name__ == "__main__":
    main()
