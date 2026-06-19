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
├── settings.py          # Configuração via pydantic-settings
├── api/
│   ├── routes/          # Endpoints HTTP
│   ├── dependencies/    # Injeção de dependências FastAPI
│   └── middlewares/     # Correlation ID e outros (futuro)
├── core/                # Exceções e tipos compartilhados
├── modules/orders/      # Domínio de pedidos (schemas, services, events)
└── infrastructure/      # Postgres, RabbitMQ, logging
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
