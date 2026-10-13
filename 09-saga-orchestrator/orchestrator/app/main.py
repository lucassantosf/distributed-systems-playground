import logging
from contextlib import asynccontextmanager
import aio_pika
from fastapi import FastAPI

from app.config import settings
from app.messaging.topology import setup_rabbitmq_topology
from app.api.routers import sagas

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Conectar ao RabbitMQ e garantir a topologia
    logger.info(f"Conectando ao RabbitMQ em {settings.RABBITMQ_URL}...")
    connection = None
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        channel = await connection.channel()
        await setup_rabbitmq_topology(channel)
        app.state.rabbitmq_connection = connection
        app.state.rabbitmq_channel = channel
        logger.info("Topologia RabbitMQ pronta para uso.")
    except Exception as e:
        logger.error(f"Erro ao conectar ou configurar topologia RabbitMQ: {e}", exc_info=True)

    yield

    # Shutdown: Fechar conexões
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
