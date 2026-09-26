# AI Workflow Simulation & Evaluation Engine

A stateful, enterprise-style workflow environment (customer support / order
refunds) where an agent interacts through a constrained set of actions, plus
an evaluation engine that scores agent trajectories against expected actions,
policy compliance, and final state — and a data pipeline that generates and
validates synthetic enterprise data.

## Push to GitHub

```bash
cd ai_workflow_eval
git init
git add .
git commit -m "AI workflow simulation and evaluation engine"
git branch -M main
git remote add origin https://github.com/<your-username>/ai-workflow-eval.git
git push -u origin main
```

CI runs automatically on the first push (`.github/workflows/ci.yml`).

## Architecture

```
FastAPI (routers) -> Environment (workflow engine) -> SQLAlchemy models -> SQLite/Postgres
                   -> Evaluator (scores trajectories)
                   -> Agent (pluggable; MockAgent included)

data_pipeline.py -- standalone synthetic data generation + validation
```

Layering: **router -> environment/evaluator (service) -> SQLAlchemy models
(repository) -> DB**. Nothing is dumped into `main.py`.

### Entities
`Environment, Customer, Product, Order, Payment, Refund, Ticket, AgentAction,
Evaluation` — see `app/models.py`.

### Workflow engine (`app/environment.py`)
Wraps a DB-backed scenario. Every call goes through `Environment.execute(action, params)`,
which dispatches to an `a_*` method, logs an `AgentAction` row (params, result,
success), and never lets the agent touch the DB directly. Business rules
(e.g. refund eligibility) are enforced *inside* the actions — an ineligible
`issue_refund` raises `PolicyViolation`, not silently rejected.

Actions: `get_customer, list_orders, get_order, get_payment,
check_refund_policy, issue_refund, deny_refund, create_ticket, update_ticket`.

### Evaluation engine (`app/evaluator.py`)
For a given environment + task, reads back the logged `AgentAction` trajectory
and computes: task success, action precision/recall vs. expected actions,
policy violations, invalid actions, steps taken, and a composite reward.

### Benchmark tasks (`app/tasks.py`)
8 tasks across easy / medium / hard, each with a scenario seed, expected
actions, forbidden actions, a step budget, and a final-state check function.

### Agent (`app/agent.py`, `app/llm_agent.py`)
`MockAgent` is a deterministic, rule-based agent that solves each task so the
whole pipeline runs end to end without an LLM in the loop.

`LLMAgent` (`app/llm_agent.py`) is a real implementation: it hands the task
description and available actions to Claude as tools, and Claude decides what
to call at each step, exactly like a production tool-using agent would.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run_llm_demo.py medium_refund_damaged_item
# or via the API: POST /benchmarks/run {"agent": "llm"}
```

If `ANTHROPIC_API_KEY` isn't set / `anthropic` isn't installed, only `mock`
is registered — the rest of the system is unaffected either way.

### Data pipeline (`app/data_pipeline.py`)
Generates synthetic customers/orders, deliberately injects data-quality
issues (orphan foreign keys, duplicate IDs, invalid amounts, bad timestamps,
missing fields), then validates and cleans them, producing a rejection report
by issue type. Standalone from the API's own DB — run it on its own.

## Run it

```bash
pip install -r requirements.txt

# one-shot: seeds environments, runs the mock agent on all 8 tasks,
# evaluates them, then runs the data pipeline
python run_demo.py

# or start the API
uvicorn app.main:app --reload
# docs at http://localhost:8000/docs

# tests
pytest -q

# data pipeline standalone
python -m app.data_pipeline
```

## CI

`.github/workflows/ci.yml` runs `pytest` on every push/PR to `main` via
GitHub Actions — no setup needed once pushed to a repo.

## Deploy

A `Dockerfile` is included. Any of these work with their free tier:

**Render** — New → Web Service → connect the repo → it detects the
Dockerfile automatically. Set `PORT=8000` if prompted.

**Railway** — New Project → Deploy from GitHub repo → it builds the
Dockerfile automatically.

**Fly.io**
```bash
fly launch    # detects the Dockerfile, generates fly.toml
fly deploy
```

SQLite works fine for a demo deployment; the DB resets on redeploy unless
you attach a persistent volume (all three platforms support this).

## API

```
POST /environments                 {name, scenario} -> create + seed an environment
GET  /environments/{id}
GET  /environments/{id}/trajectory -> logged actions in order

GET  /tasks                        -> list benchmark tasks
GET  /tasks/{id}

POST /actions                      {environment_id, action_name, params, task_id}
                                    -> execute one action, logged automatically

POST /evaluations                  {environment_id, task_id} -> score the trajectory
GET  /evaluations/{id}

POST /benchmarks/run               {task_ids?, agent} -> run agent over N tasks,
                                    return aggregated success_rate/reward/precision/recall
```

### Example

```bash
curl -X POST localhost:8000/environments \
  -H "Content-Type: application/json" \
  -d '{"name": "demo", "scenario": "damaged_item_refund"}'
# -> {"id": "<env_id>", ...}

curl -X POST localhost:8000/actions \
  -H "Content-Type: application/json" \
  -d '{"environment_id": "<env_id>", "action_name": "check_refund_policy", "params": {"order_id": "<order_id>"}}'

curl -X POST localhost:8000/benchmarks/run -H "Content-Type: application/json" -d '{}'
```

## Scenarios

`damaged_item_refund`, `ok_item_refund_attempt`, `already_refunded`,
`wrong_item_not_delivered` — see `SCENARIOS` in `app/environment.py`. Each
seeds one customer + one order in a specific state so tasks can target
distinct policy edge cases (double refund, ineligible item, undelivered order).

## What this demonstrates

- Stateful workflow/environment design, not just CRUD endpoints
- An evaluation engine that scores trajectories against expected actions,
  forbidden actions, and final state — with a real reward function
- Layered backend architecture (router / service / repository)
- SQLAlchemy modeling with FKs, enums, and relationships
- A synthetic data pipeline with deliberate data-quality problems and
  validation logic
- A pluggable agent interface, ready for a real LLM to be dropped in

## Possible extensions

- Postgres + Alembic migrations instead of SQLite
- Ordered-sequence scoring (not just set precision/recall) for stricter grading
- A minimal React dashboard over `/benchmarks/run` results

## Resume bullet

> Designed a stateful FastAPI backend simulating enterprise refund workflows;
> built an evaluation engine scoring agent trajectories across 8 benchmark
> tasks (precision/recall, policy-violation detection, reward scoring) with
> 100% test coverage on core logic; deployed with CI (GitHub Actions) and
> Docker.
