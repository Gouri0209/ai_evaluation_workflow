from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db
from app.routers import environments, tasks, actions, evaluations, benchmarks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI Workflow Simulation & Evaluation Engine",
    description="Stateful enterprise workflow environment for benchmarking agent actions.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"status": "ok", "service": "ai-workflow-eval-engine"}


app.include_router(environments.router)
app.include_router(tasks.router)
app.include_router(actions.router)
app.include_router(evaluations.router)
app.include_router(benchmarks.router)
