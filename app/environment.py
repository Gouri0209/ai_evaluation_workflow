import json
import random
from typing import Any, Dict

from sqlalchemy.orm import Session

from app import models


class ActionError(Exception):
    pass


class PolicyViolation(Exception):
    pass


SCENARIOS = {
    "damaged_item_refund": dict(
        order_status=models.OrderStatus.DELIVERED,
        item_condition=models.ItemCondition.DAMAGED,
        refund_status=models.RefundStatus.NOT_ISSUED,
    ),
    "ok_item_refund_attempt": dict(
        order_status=models.OrderStatus.DELIVERED,
        item_condition=models.ItemCondition.OK,
        refund_status=models.RefundStatus.NOT_ISSUED,
    ),
    "already_refunded": dict(
        order_status=models.OrderStatus.DELIVERED,
        item_condition=models.ItemCondition.DAMAGED,
        refund_status=models.RefundStatus.ISSUED,
    ),
    "wrong_item_not_delivered": dict(
        order_status=models.OrderStatus.SHIPPED,
        item_condition=models.ItemCondition.WRONG_ITEM,
        refund_status=models.RefundStatus.NOT_ISSUED,
    ),
}


class Environment:
    """Wraps a DB-backed scenario and exposes a constrained action set.
    Every action call is logged as an AgentAction row."""

    def __init__(self, db: Session, environment_id: str, task_id: str = None):
        self.db = db
        self.env_id = environment_id
        self.task_id = task_id
        self._step = 0

    # ---- seeding ----
    @staticmethod
    def create(db: Session, name: str, scenario: str) -> models.Environment:
        if scenario not in SCENARIOS:
            raise ActionError(f"unknown scenario '{scenario}'")
        env = models.Environment(name=name, scenario=scenario)
        db.add(env)
        db.flush()

        cust = models.Customer(environment_id=env.id, name="Asha Rao",
                                email="asha@example.com", tier="STANDARD")
        prod = models.Product(environment_id=env.id, name="Wireless Mouse",
                               price=799.0, category="electronics")
        db.add_all([cust, prod])
        db.flush()

        cfg = SCENARIOS[scenario]
        order = models.Order(
            environment_id=env.id, customer_id=cust.id, product_id=prod.id,
            status=cfg["order_status"], item_condition=cfg["item_condition"],
            refund_status=cfg["refund_status"], total_amount=prod.price,
        )
        db.add(order)
        db.flush()

        payment = models.Payment(order_id=order.id, amount=prod.price, status="CAPTURED")
        db.add(payment)

        if cfg["refund_status"] == models.RefundStatus.ISSUED:
            db.add(models.Refund(order_id=order.id, amount=prod.price,
                                  status=models.RefundStatus.ISSUED, reason="prior refund"))

        db.commit()
        db.refresh(env)
        return env

    # ---- dispatch ----
    def execute(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._step += 1
        handler = getattr(self, f"a_{action_name}", None)
        if handler is None:
            return self._log(action_name, params, False, {"error": f"unknown action '{action_name}'"})
        try:
            result = handler(**params)
            return self._log(action_name, params, True, result)
        except (ActionError, PolicyViolation) as e:
            return self._log(action_name, params, False, {"error": str(e), "type": type(e).__name__})
        except TypeError as e:
            return self._log(action_name, params, False, {"error": f"bad params: {e}"})

    def _log(self, action_name, params, success, result) -> Dict[str, Any]:
        row = models.AgentAction(
            environment_id=self.env_id, task_id=self.task_id, step_number=self._step,
            action_name=action_name, params=json.dumps(params), result=json.dumps(result),
            success=success,
        )
        self.db.add(row)
        self.db.commit()
        return {"success": success, "result": result, "step_number": self._step}

    # ---- helpers ----
    def _order(self, order_id: str) -> models.Order:
        order = self.db.query(models.Order).filter_by(id=order_id, environment_id=self.env_id).first()
        if not order:
            raise ActionError(f"order '{order_id}' not found")
        return order

    def _customer(self, customer_id: str) -> models.Customer:
        c = self.db.query(models.Customer).filter_by(id=customer_id, environment_id=self.env_id).first()
        if not c:
            raise ActionError(f"customer '{customer_id}' not found")
        return c

    def _ticket(self, ticket_id: str) -> models.Ticket:
        t = self.db.query(models.Ticket).filter_by(id=ticket_id, environment_id=self.env_id).first()
        if not t:
            raise ActionError(f"ticket '{ticket_id}' not found")
        return t

    # ---- actions (agent-callable) ----
    def a_get_customer(self, customer_id: str):
        c = self._customer(customer_id)
        return {"id": c.id, "name": c.name, "email": c.email, "tier": c.tier}

    def a_list_orders(self, customer_id: str):
        orders = self.db.query(models.Order).filter_by(customer_id=customer_id, environment_id=self.env_id).all()
        return {"orders": [o.id for o in orders]}

    def a_get_order(self, order_id: str):
        o = self._order(order_id)
        return {
            "id": o.id, "status": o.status.value, "item_condition": o.item_condition.value,
            "refund_status": o.refund_status.value, "total_amount": o.total_amount,
            "customer_id": o.customer_id,
        }

    def a_get_payment(self, order_id: str):
        self._order(order_id)
        p = self.db.query(models.Payment).filter_by(order_id=order_id).first()
        if not p:
            raise ActionError(f"no payment for order '{order_id}'")
        return {"amount": p.amount, "status": p.status, "method": p.method}

    def a_check_refund_policy(self, order_id: str):
        o = self._order(order_id)
        eligible = (
            o.status == models.OrderStatus.DELIVERED
            and o.item_condition != models.ItemCondition.OK
            and o.refund_status == models.RefundStatus.NOT_ISSUED
        )
        reason = "eligible" if eligible else self._ineligible_reason(o)
        return {"eligible": eligible, "reason": reason}

    @staticmethod
    def _ineligible_reason(o: models.Order) -> str:
        if o.status != models.OrderStatus.DELIVERED:
            return f"order not delivered (status={o.status.value})"
        if o.item_condition == models.ItemCondition.OK:
            return "item condition OK, no defect reported"
        if o.refund_status != models.RefundStatus.NOT_ISSUED:
            return f"refund already {o.refund_status.value.lower()}"
        return "not eligible"

    def a_issue_refund(self, order_id: str, reason: str = ""):
        o = self._order(order_id)
        eligible = (
            o.status == models.OrderStatus.DELIVERED
            and o.item_condition != models.ItemCondition.OK
            and o.refund_status == models.RefundStatus.NOT_ISSUED
        )
        if not eligible:
            raise PolicyViolation(f"refund not permitted: {self._ineligible_reason(o)}")
        o.refund_status = models.RefundStatus.ISSUED
        refund = models.Refund(order_id=o.id, amount=o.total_amount,
                                status=models.RefundStatus.ISSUED, reason=reason)
        self.db.add(refund)
        self.db.commit()
        return {"order_id": o.id, "refund_status": o.refund_status.value, "amount": o.total_amount}

    def a_deny_refund(self, order_id: str, reason: str = ""):
        o = self._order(order_id)
        o.refund_status = models.RefundStatus.DENIED
        self.db.add(models.Refund(order_id=o.id, amount=0.0,
                                   status=models.RefundStatus.DENIED, reason=reason))
        self.db.commit()
        return {"order_id": o.id, "refund_status": o.refund_status.value}

    def a_create_ticket(self, order_id: str = None, customer_id: str = None,
                         subject: str = "", priority: str = "NORMAL"):
        t = models.Ticket(environment_id=self.env_id, order_id=order_id, customer_id=customer_id,
                           subject=subject, priority=priority, status=models.TicketStatus.OPEN)
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        return {"ticket_id": t.id, "status": t.status.value}

    def a_update_ticket(self, ticket_id: str, status: str):
        t = self._ticket(ticket_id)
        try:
            t.status = models.TicketStatus(status)
        except ValueError:
            raise ActionError(f"invalid ticket status '{status}'")
        self.db.commit()
        return {"ticket_id": t.id, "status": t.status.value}
