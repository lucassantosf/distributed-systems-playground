import logging
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI

from app.config import settings
from app.messaging.topology import setup_rabbitmq_topology
from app.messaging.publisher import CommandPublisher
from app.messaging.consumer import start_replies_consumer, stop_replies_consumer
from app.core.engine import SagaEngine
from app.database import AsyncSessionLocal
from app.api.routers import sagas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar ao RabbitMQ e garantir a topologia
    logger.info(f"Conectando ao RabbitMQ em {settings.RABBITMQ_URL}...")
    connection = None
    consumer_task = None
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        await setup_rabbitmq_topology(channel)
        app.state.rabbitmq_connection = connection
        app.state.rabbitmq_channel = channel
        logger.info("Topologia RabbitMQ pronta para uso.")

        # Instancia publisher, engine e consumer
        publisher = CommandPublisher(channel=channel)
        engine = SagaEngine(session_factory=AsyncSessionLocal, publisher=publisher)
        app.state.publisher = publisher
        app.state.engine = engine

        # Inicia consumer de replies como asyncio task em background
        consumer_task = start_replies_consumer(channel=channel, engine=engine)
        app.state.consumer_task = consumer_task
        logger.info("Consumer de replies iniciado como asyncio task.")
    except Exception as e:
        logger.error(f"Erro ao conectar ou configurar RabbitMQ/Consumer: {e}", exc_info=True)

    yield

    # Shutdown: Fechar consumer e conexões
    if consumer_task and not consumer_task.done():
        logger.info("Encerrando consumer de replies...")
        await stop_replies_consumer(consumer_task)

    if connection and not connection.is_closed:
        logger.info("Encerrando conexão com RabbitMQ...")
        await connection.close()


app = FastAPI(
    title="Saga Orchestrator",
    description="Workflow Engine / Saga Orchestrator API",
    version="0.1.0",
    lifespan=lifespan,
)

# Registra as rotas de Sagas
app.include_router(sagas.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "orchestrator",
    }
