from __future__ import annotations

import asyncio
import sys

from src.customer_agent.config import Settings
from src.customer_agent.factory import build_agent
from src.customer_agent.schemas import IncomingMessage


async def main() -> None:
    settings = Settings()
    question = " ".join(sys.argv[1:]).strip() or "你们的退款政策是什么？"
    agent = build_agent(settings)

    result = await agent.handle_message(
        IncomingMessage(
            conversation_id="demo-conversation",
            contact_id="demo-contact",
            content=question,
            user_level="all",
        )
    )

    print(f"intent: {result.intent}")
    print(f"confidence: {result.confidence:.2f}")
    print(f"reply: {result.reply}")
    print(f"action: {result.action.type}")
    if result.action.reason:
        print(f"reason: {result.action.reason}")


if __name__ == "__main__":
    asyncio.run(main())
