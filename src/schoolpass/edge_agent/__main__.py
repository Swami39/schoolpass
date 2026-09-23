"""Entrypoint: ``python -m schoolpass.edge_agent``."""

from __future__ import annotations

import asyncio
import logging
import signal

from schoolpass.edge_agent.agent import EdgeAgent
from schoolpass.edge_agent.config import EdgeConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    config = EdgeConfig.from_env()
    agent = EdgeAgent(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, agent.stop)
        except NotImplementedError:
            pass  # Windows
    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        agent.stop()
        loop.run_until_complete(agent.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
