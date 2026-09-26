"""Real agent implementation: an LLM decides which action to call at each step,
using Anthropic's tool-use API, instead of following a fixed script.

Requires ANTHROPIC_API_KEY to be set. Model is configurable via
ANTHROPIC_MODEL (default: claude-sonnet-5).

Usage:
    from app.llm_agent import LLMAgent
    AGENTS["llm"] = LLMAgent   # or just call it directly, see run_llm_demo.py
"""
import json
import os

from sqlalchemy.orm import Session

from app import models
from app.agent import Agent
from app.environment import Environment
from app.tasks import Task

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# Action name -> (description, required params) - mirrors Environment.a_* methods
ACTION_SPECS = {
    "get_customer": ("Look up a customer by id.", {"customer_id": "string"}),
    "list_orders": ("List order ids belonging to a customer.", {"customer_id": "string"}),
    "get_order": ("Get an order's status, item condition, refund status, amount.", {"order_id": "string"}),
    "get_payment": ("Get the payment record for an order.", {"order_id": "string"}),
    "check_refund_policy": ("Check whether an order is eligible for a refund.", {"order_id": "string"}),
    "issue_refund": ("Issue a refund for an order. Only valid if eligible.", {"order_id": "string", "reason": "string"}),
    "deny_refund": ("Deny a refund for an order, with a reason.", {"order_id": "string", "reason": "string"}),
    "create_ticket": ("Open a support ticket.", {"order_id": "string", "customer_id": "string", "subject": "string", "priority": "string"}),
    "update_ticket": ("Update a ticket's status (OPEN/IN_PROGRESS/RESOLVED/CLOSED).", {"ticket_id": "string", "status": "string"}),
}


def _tool_schema():
    tools = []
    for name, (desc, params) in ACTION_SPECS.items():
        tools.append({
            "name": name,
            "description": desc,
            "input_schema": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in params},
                "required": list(params.keys()),
            },
        })
    tools.append({
        "name": "finish",
        "description": "Call this once the task is complete and no further action is needed.",
        "input_schema": {"type": "object", "properties": {}},
    })
    return tools


class LLMAgent(Agent):
    """Calls the Anthropic API to decide each action dynamically."""

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()

    def solve(self, env: Environment, db: Session, environment_id: str, task: Task):
        order = db.query(models.Order).filter_by(environment_id=environment_id).first()
        customer_id = order.customer_id

        system = (
            "You are a customer support agent. You can only act through the tools "
            "provided - you have no other way to read or change data. Call 'finish' "
            "once the task is resolved. Do not call more than "
            f"{task.max_steps} actions total."
        )
        messages = [{
            "role": "user",
            "content": (
                f"Task: {task.description}\n"
                f"order_id: {order.id}\ncustomer_id: {customer_id}\n"
                "Resolve this using the available tools."
            ),
        }]

        for _ in range(task.max_steps):
            response = self.client.messages.create(
                model=MODEL, max_tokens=1024, system=system,
                messages=messages, tools=_tool_schema(),
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls or any(c.name == "finish" for c in tool_calls):
                break

            tool_results = []
            for call in tool_calls:
                outcome = env.execute(call.name, call.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(outcome["result"]),
                })
            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason != "tool_use":
                break
