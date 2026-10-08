import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification-worker")

async def main():
    logger.info("Inventory worker initialized and waiting for messages...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
