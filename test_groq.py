import os
from app.llm_agent import LLMAgent

# Check API Key
if not os.getenv("GROQ_API_KEY"):
    print("ERROR: GROQ_API_KEY is not set in environment variables.")
else:
    agent = LLMAgent()
    decision = agent.run_step(
        user_prompt="Customer wants a refund for order ord_12345 because the item arrived broken.",
        action_history=[]
    )

    print("\n--- Groq Agent Decision ---")
    print(decision)