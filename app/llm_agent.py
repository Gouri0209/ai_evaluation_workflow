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
from groq import Groq

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


class LLMAgent:
    def __init__(self, model_name: str = "openai/gpt-oss-120b"):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = model_name

        # 1. Define tools in JSON schema format for Groq
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_order",
                    "description": "Retrieve details about an order by order_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "The UUID or ID of the order"}
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_refund_policy",
                    "description": "Check if an order is eligible for a refund according to company policy.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "The UUID or ID of the order"}
                        },
                        "required": ["order_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "issue_refund",
                    "description": "Issue a full refund for a verified eligible order.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "The UUID or ID of the order"}
                        },
                        "required": ["order_id"]
                    }
                }
            }
        ]

    def run_step(self, user_prompt: str, action_history: list):
        """
        Queries Llama 3.3 via Groq to decide the next action based on prompt and history.
        """
        messages = [
            {"role": "system", "content": "You are an automated customer service resolution agent. Follow policy strictly. Use provided tools to investigate and resolve requests."}
        ]
        
        # Append action history to conversation context
        for entry in action_history:
            messages.append({"role": "user", "content": f"Action Taken: {entry['action']}, Result: {entry['result']}"})

        messages.append({"role": "user", "content": user_prompt})

        # Send request to Groq API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto"
        )

        message = response.choices[0].message

        # If model decides to call a tool/action
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            return {
                "type": "action",
                "action_name": tool_call.function.name,
                "params": json.loads(tool_call.function.arguments)
            }
        
        # Otherwise, model provides a final text response
        return {
            "type": "finish",
            "content": message.content
        }