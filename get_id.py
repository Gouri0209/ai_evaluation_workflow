from app.database import SessionLocal
from app.models import Customer, Environment, Order

db = SessionLocal()

# Get the latest environment created
latest_env = db.query(Environment).all()[-1]

# Get the customer and order attached specifically to that environment
cust = db.query(Customer).filter_by(environment_id=latest_env.id).first()
order = db.query(Order).filter_by(environment_id=latest_env.id).first()

print("Environment ID:", latest_env.id)
print("Customer ID:   ", cust.id if cust else "None")
print("Order ID:      ", order.id if order else "None")

db.close()