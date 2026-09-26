from typing import Optional, Any, Dict, List
from pydantic import BaseModel


class EnvironmentCreate(BaseModel):
    name: str = "env"
    scenario: str = "damaged_item_refund"


class EnvironmentOut(BaseModel):
    id: str
    name: str
    scenario: str

    class Config:
        from_attributes = True


class ActionRequest(BaseModel):
    environment_id: str
    action_name: str
    params: Dict[str, Any] = {}
    task_id: Optional[str] = None


class ActionResult(BaseModel):
    success: bool
    result: Dict[str, Any]
    step_number: int


class TaskOut(BaseModel):
    id: str
    difficulty: str
    description: str
    max_steps: int


class EvaluateRequest(BaseModel):
    environment_id: str
    task_id: str


class EvaluationOut(BaseModel):
    id: str
    task_id: str
    task_success: bool
    action_precision: float
    action_recall: float
    policy_violations: int
    invalid_actions: int
    steps_taken: int
    reward: float
    details: Dict[str, Any]

    class Config:
        from_attributes = True


class BenchmarkRunRequest(BaseModel):
    task_ids: Optional[List[str]] = None
    agent: str = "mock"


class BenchmarkResultOut(BaseModel):
    total_tasks: int
    success_rate: float
    avg_reward: float
    avg_precision: float
    avg_recall: float
    total_policy_violations: int
    evaluations: List[EvaluationOut]
