"""Generates synthetic enterprise-style records with deliberately injected
data-quality issues, then validates and cleans them. Standalone from the API/
DB used by the workflow engine -- demonstrates the data pipeline independently.
Run: python -m app.data_pipeline
"""
import json
import os
import random
import uuid
from datetime import datetime, timedelta

FIRST_NAMES = ["Asha", "Rohan", "Meera", "Kiran", "Neha", "Vikram", "Priya", "Arjun"]
LAST_NAMES = ["Rao", "Sharma", "Iyer", "Patel", "Nair", "Verma", "Reddy", "Singh"]
PRODUCTS = ["Wireless Mouse", "Mechanical Keyboard", "USB-C Hub", "Laptop Stand",
            "Noise Cancelling Headphones", "Webcam", "Monitor Arm", "Desk Lamp"]
ORDER_STATUSES = ["PLACED", "SHIPPED", "DELIVERED", "CANCELLED"]


def _rand_id():
    return str(uuid.uuid4())


def generate_raw_records(n_customers=200, n_orders=500, corruption_rate=0.08):
    customers = []
    for _ in range(n_customers):
        customers.append({
            "id": _rand_id(),
            "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "email": f"user{random.randint(1, 99999)}@example.com",
        })

    valid_customer_ids = [c["id"] for c in customers]

    orders = []
    for _ in range(n_orders):
        cust_id = random.choice(valid_customer_ids)
        created = datetime.utcnow() - timedelta(days=random.randint(0, 180))
        order = {
            "id": _rand_id(),
            "customer_id": cust_id,
            "product": random.choice(PRODUCTS),
            "status": random.choice(ORDER_STATUSES),
            "amount": round(random.uniform(199, 15000), 2),
            "created_at": created.isoformat(),
        }
        orders.append(order)

    # inject data-quality issues into a copy
    corrupted = [dict(o) for o in orders]
    n_corrupt = int(len(corrupted) * corruption_rate)
    issue_pool = ["missing_fk", "duplicate", "invalid_amount", "bad_timestamp", "missing_field"]

    for _ in range(n_corrupt):
        issue = random.choice(issue_pool)
        target = random.choice(corrupted)

        if issue == "missing_fk":
            target["customer_id"] = _rand_id()  # orphan reference
        elif issue == "duplicate":
            corrupted.append(dict(target))
        elif issue == "invalid_amount":
            target["amount"] = round(random.uniform(-500, -1), 2)
        elif issue == "bad_timestamp":
            target["created_at"] = "not-a-date"
        elif issue == "missing_field":
            target.pop("status", None)

    return customers, corrupted


def validate_and_clean(customers, raw_orders):
    valid_customer_ids = {c["id"] for c in customers}
    seen_ids = set()
    clean, rejected = [], []

    for o in raw_orders:
        errors = []
        if o["id"] in seen_ids:
            errors.append("duplicate_id")
        if o.get("customer_id") not in valid_customer_ids:
            errors.append("orphan_foreign_key")
        if "status" not in o or o.get("status") not in ORDER_STATUSES:
            errors.append("missing_or_invalid_status")
        if not isinstance(o.get("amount"), (int, float)) or o.get("amount", 0) <= 0:
            errors.append("invalid_amount")
        try:
            datetime.fromisoformat(o.get("created_at", ""))
        except ValueError:
            errors.append("invalid_timestamp")

        if errors:
            rejected.append({"record": o, "errors": errors})
        else:
            seen_ids.add(o["id"])
            clean.append(o)

    report = {
        "total_raw": len(raw_orders),
        "clean": len(clean),
        "rejected": len(rejected),
        "rejection_rate": round(len(rejected) / len(raw_orders), 4) if raw_orders else 0,
        "issue_breakdown": _breakdown(rejected),
    }
    return clean, rejected, report


def _breakdown(rejected):
    counts = {}
    for r in rejected:
        for e in r["errors"]:
            counts[e] = counts.get(e, 0) + 1
    return counts


def run(out_dir="data"):
    os.makedirs(out_dir, exist_ok=True)
    customers, raw_orders = generate_raw_records()
    clean, rejected, report = validate_and_clean(customers, raw_orders)

    with open(f"{out_dir}/customers.json", "w") as f:
        json.dump(customers, f, indent=2)
    with open(f"{out_dir}/orders_raw.json", "w") as f:
        json.dump(raw_orders, f, indent=2)
    with open(f"{out_dir}/orders_clean.json", "w") as f:
        json.dump(clean, f, indent=2)
    with open(f"{out_dir}/validation_report.json", "w") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
