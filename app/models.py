import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, Enum
)
from sqlalchemy.orm import relationship

from app.database import Base


def uid():
    return str(uuid.uuid4())


class OrderStatus(str, enum.Enum):
    PLACED = "PLACED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class ItemCondition(str, enum.Enum):
    OK = "OK"
    DAMAGED = "DAMAGED"
    WRONG_ITEM = "WRONG_ITEM"
    MISSING = "MISSING"


class RefundStatus(str, enum.Enum):
    NOT_ISSUED = "NOT_ISSUED"
    PENDING = "PENDING"
    ISSUED = "ISSUED"
    DENIED = "DENIED"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Environment(Base):
    __tablename__ = "environments"
    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    scenario = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.utcnow)

    customers = relationship("Customer", back_populates="environment", cascade="all,delete")
    orders = relationship("Order", back_populates="environment", cascade="all,delete")
    products = relationship("Product", back_populates="environment", cascade="all,delete")
    tickets = relationship("Ticket", back_populates="environment", cascade="all,delete")
    actions = relationship("AgentAction", back_populates="environment", cascade="all,delete")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    tier = Column(String, default="STANDARD")

    environment = relationship("Environment", back_populates="customers")
    orders = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String, default="general")

    environment = relationship("Environment", back_populates="products")


class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    customer_id = Column(String, ForeignKey("customers.id"))
    product_id = Column(String, ForeignKey("products.id"))
    status = Column(Enum(OrderStatus), default=OrderStatus.DELIVERED)
    item_condition = Column(Enum(ItemCondition), default=ItemCondition.OK)
    refund_status = Column(Enum(RefundStatus), default=RefundStatus.NOT_ISSUED)
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    environment = relationship("Environment", back_populates="orders")
    customer = relationship("Customer", back_populates="orders")
    payment = relationship("Payment", back_populates="order", uselist=False, cascade="all,delete")
    refund = relationship("Refund", back_populates="order", uselist=False, cascade="all,delete")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True, default=uid)
    order_id = Column(String, ForeignKey("orders.id"))
    amount = Column(Float, nullable=False)
    status = Column(String, default="CAPTURED")
    method = Column(String, default="CARD")

    order = relationship("Order", back_populates="payment")


class Refund(Base):
    __tablename__ = "refunds"
    id = Column(String, primary_key=True, default=uid)
    order_id = Column(String, ForeignKey("orders.id"))
    amount = Column(Float, nullable=False)
    status = Column(Enum(RefundStatus), default=RefundStatus.PENDING)
    reason = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="refund")


class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True)
    subject = Column(String, default="")
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN)
    priority = Column(String, default="NORMAL")

    environment = relationship("Environment", back_populates="tickets")


class AgentAction(Base):
    __tablename__ = "agent_actions"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    task_id = Column(String, nullable=True)
    step_number = Column(Integer, nullable=False)
    action_name = Column(String, nullable=False)
    params = Column(Text, default="{}")
    result = Column(Text, default="{}")
    success = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    environment = relationship("Environment", back_populates="actions")


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(String, primary_key=True, default=uid)
    environment_id = Column(String, ForeignKey("environments.id"))
    task_id = Column(String, nullable=False)
    task_success = Column(Boolean, default=False)
    action_precision = Column(Float, default=0.0)
    action_recall = Column(Float, default=0.0)
    policy_violations = Column(Integer, default=0)
    invalid_actions = Column(Integer, default=0)
    steps_taken = Column(Integer, default=0)
    reward = Column(Float, default=0.0)
    details = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
