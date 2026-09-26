from sqlalchemy.orm import Session

from app import models
from app.environment import Environment
from app.tasks import Task


class Agent:
    """Base interface. Implement solve() to plug in a real (LLM-backed) agent."""

    def solve(self, env: Environment, db: Session, environment_id: str, task: Task):
        raise NotImplementedError


class MockAgent(Agent):
    """Deterministic rule-based agent used to exercise the environment and
    evaluation engine end to end without an LLM in the loop. Swap in an
    LLM-backed Agent implementation for real benchmarking."""

    def solve(self, env: Environment, db: Session, environment_id: str, task: Task):
        order = db.query(models.Order).filter_by(environment_id=environment_id).first()
        customer_id = order.customer_id

        if task.id == "easy_find_customer":
            env.execute("get_order", {"order_id": order.id})
            env.execute("get_customer", {"customer_id": customer_id})

        elif task.id == "easy_check_order_status":
            env.execute("get_order", {"order_id": order.id})

        elif task.id == "medium_refund_damaged_item":
            env.execute("get_order", {"order_id": order.id})
            check = env.execute("check_refund_policy", {"order_id": order.id})
            if check["result"].get("eligible"):
                env.execute("issue_refund", {"order_id": order.id, "reason": "damaged item"})

        elif task.id == "medium_reject_ineligible_refund":
            env.execute("get_order", {"order_id": order.id})
            check = env.execute("check_refund_policy", {"order_id": order.id})
            if not check["result"].get("eligible"):
                env.execute("deny_refund", {"order_id": order.id, "reason": check["result"].get("reason", "")})

        elif task.id == "medium_ticket_after_refund":
            env.execute("get_order", {"order_id": order.id})
            check = env.execute("check_refund_policy", {"order_id": order.id})
            if check["result"].get("eligible"):
                env.execute("issue_refund", {"order_id": order.id, "reason": "damaged item"})
                t = env.execute("create_ticket", {
                    "order_id": order.id, "customer_id": customer_id,
                    "subject": "Refund confirmation", "priority": "NORMAL",
                })
                ticket_id = t["result"]["ticket_id"]
                env.execute("update_ticket", {"ticket_id": ticket_id, "status": "RESOLVED"})

        elif task.id == "hard_already_refunded":
            env.execute("get_order", {"order_id": order.id})
            env.execute("check_refund_policy", {"order_id": order.id})

        elif task.id == "hard_not_delivered_refund_attempt":
            env.execute("get_order", {"order_id": order.id})
            check = env.execute("check_refund_policy", {"order_id": order.id})
            if not check["result"].get("eligible"):
                env.execute("deny_refund", {"order_id": order.id, "reason": check["result"].get("reason", "")})

        elif task.id == "hard_multi_step_full_resolution":
            env.execute("get_customer", {"customer_id": customer_id})
            env.execute("get_order", {"order_id": order.id})
            env.execute("get_payment", {"order_id": order.id})
            check = env.execute("check_refund_policy", {"order_id": order.id})
            if check["result"].get("eligible"):
                env.execute("issue_refund", {"order_id": order.id, "reason": "damaged item"})
                t = env.execute("create_ticket", {
                    "order_id": order.id, "customer_id": customer_id,
                    "subject": "Refund confirmation", "priority": "NORMAL",
                })
                ticket_id = t["result"]["ticket_id"]
                env.execute("update_ticket", {"ticket_id": ticket_id, "status": "RESOLVED"})


AGENTS = {"mock": MockAgent}

try:
    from app.llm_agent import LLMAgent
    AGENTS["llm"] = LLMAgent
except ImportError:
    pass  # `anthropic` package not installed - only the mock agent is available
