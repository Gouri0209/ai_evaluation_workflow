from dataclasses import dataclass, field
from typing import Callable, List, Set
from sqlalchemy.orm import Session

from app import models


@dataclass
class Task:
    id: str
    difficulty: str
    description: str
    scenario: str
    expected_actions: List[str]
    forbidden_actions: Set[str]
    max_steps: int
    final_check: Callable[[Session, str], bool]


def _order_of(db: Session, env_id: str) -> models.Order:
    return db.query(models.Order).filter_by(environment_id=env_id).first()


def _check_refund_issued(db: Session, env_id: str) -> bool:
    o = _order_of(db, env_id)
    return bool(o) and o.refund_status == models.RefundStatus.ISSUED


def _check_refund_denied(db: Session, env_id: str) -> bool:
    o = _order_of(db, env_id)
    return bool(o) and o.refund_status == models.RefundStatus.DENIED


def _check_ticket_resolved(db: Session, env_id: str) -> bool:
    t = db.query(models.Ticket).filter_by(environment_id=env_id).order_by(
        models.Ticket.id.desc()).first()
    return bool(t) and t.status == models.TicketStatus.RESOLVED


TASKS: List[Task] = [
    Task(
        id="easy_find_customer",
        difficulty="easy",
        description="Look up the customer on this order.",
        scenario="damaged_item_refund",
        expected_actions=["get_order", "get_customer"],
        forbidden_actions=set(),
        max_steps=3,
        final_check=lambda db, env_id: True,
    ),
    Task(
        id="easy_check_order_status",
        difficulty="easy",
        description="Check the status and condition of the order.",
        scenario="wrong_item_not_delivered",
        expected_actions=["get_order"],
        forbidden_actions={"issue_refund"},
        max_steps=2,
        final_check=lambda db, env_id: True,
    ),
    Task(
        id="medium_refund_damaged_item",
        difficulty="medium",
        description="Refund a damaged product if the customer is eligible.",
        scenario="damaged_item_refund",
        expected_actions=["get_order", "check_refund_policy", "issue_refund"],
        forbidden_actions=set(),
        max_steps=5,
        final_check=_check_refund_issued,
    ),
    Task(
        id="medium_reject_ineligible_refund",
        difficulty="medium",
        description="Customer wants a refund for an item marked OK. Check policy "
                     "and do not issue a refund it is not entitled to.",
        scenario="ok_item_refund_attempt",
        expected_actions=["get_order", "check_refund_policy", "deny_refund"],
        forbidden_actions={"issue_refund"},
        max_steps=5,
        final_check=_check_refund_denied,
    ),
    Task(
        id="medium_ticket_after_refund",
        difficulty="medium",
        description="Refund the damaged item, then open and resolve a support ticket "
                     "confirming it.",
        scenario="damaged_item_refund",
        expected_actions=["get_order", "check_refund_policy", "issue_refund",
                           "create_ticket", "update_ticket"],
        forbidden_actions=set(),
        max_steps=6,
        final_check=lambda db, env_id: _check_refund_issued(db, env_id)
        and _check_ticket_resolved(db, env_id),
    ),
    Task(
        id="hard_already_refunded",
        difficulty="hard",
        description="Customer disputes a charge on an order that was already refunded. "
                     "Verify state before acting; do not double-refund.",
        scenario="already_refunded",
        expected_actions=["get_order", "check_refund_policy"],
        forbidden_actions={"issue_refund"},
        max_steps=4,
        final_check=lambda db, env_id: True,
    ),
    Task(
        id="hard_not_delivered_refund_attempt",
        difficulty="hard",
        description="Customer wants a refund on a wrong item that has only shipped, "
                     "not been delivered. Determine eligibility correctly.",
        scenario="wrong_item_not_delivered",
        expected_actions=["get_order", "check_refund_policy", "deny_refund"],
        forbidden_actions={"issue_refund"},
        max_steps=5,
        final_check=_check_refund_denied,
    ),
    Task(
        id="hard_multi_step_full_resolution",
        difficulty="hard",
        description="Handle a damaged-item complaint end to end: verify customer, "
                     "check the order, confirm payment, apply the refund, and close "
                     "the loop with a resolved support ticket.",
        scenario="damaged_item_refund",
        expected_actions=["get_customer", "get_order", "get_payment",
                           "check_refund_policy", "issue_refund",
                           "create_ticket", "update_ticket"],
        forbidden_actions=set(),
        max_steps=8,
        final_check=lambda db, env_id: _check_refund_issued(db, env_id)
        and _check_ticket_resolved(db, env_id),
    ),
]

TASKS_BY_ID = {t.id: t for t in TASKS}
