# 01 — Event-Driven Orders

Projeto de estudo sobre **Arquitetura Orientada a Eventos** com FastAPI, PostgreSQL e RabbitMQ.

A API publica eventos de pedidos que são consumidos por workers independentes (notificações, faturamento, e-mail). O foco inclui retries, Dead Letter Queues (DLQ), idempotência, logs estruturados e correlation IDs.

## Stack

- **API:** FastAPI
- **Banco:** PostgreSQL (fase 2+)
- **Mensageria:** RabbitMQ (fase 3+)
- **Workers:** processos separados para notificações, faturamento e e-mail

## Estrutura de pastas

```
src/
├── main.py              # Factory create_app() e instância app
├── settings.py          # Configuração via pydantic-settings (.env support)
├── api/
│   ├── routes/          # Endpoints HTTP
│   ├── dependencies/    # Injeção de dependências FastAPI
│   └── middlewares/     # Correlation ID e outros (futuro)
├── core/                # Exceções e tipos compartilhados
├── modules/orders/      # Domínio de pedidos (models, schemas, services, events)
│   └── models.py        # Modelo SQLAlchemy `Order`
└── infrastructure/      # Postgres, RabbitMQ, logging
	└── database/        # SQLAlchemy engine, Base, init_db()
alembic/                 # Migrations Alembic (config + versions)
docker/                  # Docker configuration
└── Containerfile        # Build image (dev) — uvicorn --reload
docker-compose.yml       # Compose with api + db services
.env.example             # Example env vars (DB credentials)
.env                     # Local env (ignored by git / docker)
workers/                 # Entrypoints dos workers (futuro)
tests/                   # Testes automatizados
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # opcional
```

## Executar

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Validar

```bash
curl -i http://localhost:8000/health
# HTTP/1.1 200 OK
# {"status":"ok","service":"Event-Driven Orders API"}
```

## Testes

```bash
pytest
```

## Próximas fases

| Fase | Entregável |
|------|------------|
| 2 | Docker Compose (API + Postgres + RabbitMQ) |
| 3 | CRUD de pedidos + publicação de evento `OrderCreated` |
| 4 | Workers + DLQ + retries + idempotência |
| 5 | Correlation ID + logs estruturados |

## Banco de Dados (SQLAlchemy + Alembic)

Este projeto agora inclui integração com PostgreSQL usando SQLAlchemy e Alembic para migrações.

- Dependências adicionadas: `sqlalchemy`, `alembic`, `psycopg2-binary` (ver `requirements.txt`).
- Local: a aplicação em `development` chama `init_db()` no startup para executar `Base.metadata.create_all()` automaticamente (útil para desenvolvimento rápido).
- Migrações: o diretório `alembic/` contém a configuração e uma migration inicial que cria a tabela `orders`.

Model `Order` mapeado em `src/modules/orders/models.py` com campos:

```
id
customer_name
total_amount
status
created_at
```

Validação / uso:

- Para subir o ambiente com o banco e a API (dev com `--reload`):

```bash
docker compose up --build
```

- Validar que a tabela existe (executar no container do Postgres):

```bash
docker compose exec db psql -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-orders_db} -c "\d+ orders"
```

- Usar Alembic (opcional, recomendado para prod/mudanças controladas):

1. Ajuste `DATABASE_URL` em `.env` (ou exporte variável de ambiente).
2. Rodar migração:

```bash
# localmente, com deps instaladas
alembic upgrade head

# ou dentro do container (se tiver alembic instalado na imagem)
docker compose run --rm api alembic upgrade head
```

Notas:
- `init_db()` com retry está disponível para reduzir condições de corrida ao subir com Docker Compose; ainda assim, para produção prefira executar migrações via Alembic.
- `.env.example` contém exemplos de `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `DATABASE_URL`.

## Mensageria (RabbitMQ)

O `docker-compose.yml` agora inclui um serviço `rabbitmq` com o plugin de management (`rabbitmq:3-management`).

- **Portas expostas por padrão (host):**
	- Management UI: `15672` (mapeado para `${RABBITMQ_HOST_PORT}`)
	- AMQP: `5672` (mapeado para `${RABBITMQ_AMQP_PORT}`)

- **Credenciais:** padrão `guest`/`guest`, configuráveis via `.env` (`RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`).

Validação / uso:

- Subir serviços:

```bash
docker compose up -d --build
```

- Acessar a dashboard do RabbitMQ no host:

```
http://localhost:15672
```

- Faça login com as credenciais configuradas em `.env` (padrão `guest`/`guest`).

- Verifique que o serviço AMQP está acessível na porta `5672` para clientes/producers/consumers.

## Eventos (publisher)

Ao criar um pedido (`POST /orders`) a aplicação agora publica um evento simples no RabbitMQ:

```json
{ "event": "order_created", "order_id": 123 }
```

Detalhes:
- O evento é publicado na fila `orders` (a aplicação declara a fila antes de publicar).
- Você pode visualizar as mensagens na dashboard do RabbitMQ: abra a UI em `http://localhost:15672`, vá em "Queues" e clique na fila `orders`. As mensagens aparecerão na coluna "Ready" se nenhuma consumer estiver conectado.

## Workers

### Email worker

Um worker simples foi adicionado em `workers/email/worker.py`. Ele consome mensagens da fila `orders` e simula o envio de e-mail escrevendo uma linha em `workers/email/sent_emails.log`.

Como executar via Docker Compose:

```bash
docker compose up -d --build email_worker
```

Validação:

- Crie um pedido via `POST /orders`.
- Observe o log do worker ou abra o arquivo local `workers/email/sent_emails.log` (ele é montado no container):

```bash
# ver logs do container
docker compose logs -f email_worker

# ou verificar arquivo local
cat workers/email/sent_emails.log
```

### Billing worker

Um worker adicional foi adicionado em `workers/billing/worker.py` para demonstrar o desacoplamento. Ele também consome mensagens da fila `orders` e simula a geração de invoice escrevendo uma linha em `workers/billing/generated_invoices.log`.

Como executar via Docker Compose:

```bash
docker compose up -d --build billing_worker
```

Validação:

- Crie um pedido via `POST /orders`.
- Observe o log do worker ou abra o arquivo local `workers/billing/generated_invoices.log`:

```bash
# ver logs do container
docker compose logs -f billing_worker

# ou verificar arquivo local
cat workers/billing/generated_invoices.log
```




