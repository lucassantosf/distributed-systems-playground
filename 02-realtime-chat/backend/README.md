# Backend

API em tempo real construída com FastAPI. Gerencia conexões WebSocket, persiste mensagens no PostgreSQL e distribui mensagens entre instâncias via Redis Pub/Sub.

## Estrutura

```text
backend/
├── app/
│   ├── main.py                  # Ponto de entrada, rotas HTTP e WebSocket
│   ├── config.py                # Configurações via variáveis de ambiente
│   ├── domain/
│   │   └── message.py           # Entidade Message (dataclass)
│   ├── infrastructure/
│   │   └── database.py          # Conexão asyncpg + criação do schema
│   ├── repositories/
│   │   └── message_repository.py # CRUD de mensagens no PostgreSQL
│   └── services/
│       ├── connection_manager.py # Gerenciamento de conexões WebSocket + heartbeat
│       ├── message_service.py   # Lógica de persistência de mensagens
│       ├── redis_publisher.py   # Publica mensagens no Redis
│       └── redis_subscriber.py  # Consome mensagens do Redis e broadcasta
└── tests/
    ├── test_main.py             # Testes do fluxo WebSocket
    ├── test_messages.py         # Testes do repositório de mensagens
    └── test_message_service.py  # Testes do serviço de mensagens
```

## Camadas

| Camada | Responsabilidade |
|--------|-----------------|
| `domain/` | Entidades de negócio (Message) |
| `infrastructure/` | Conexão com PostgreSQL e inicialização do schema |
| `repositories/` | Queries e acesso a dados |
| `services/` | Lógica de aplicação (ConnectionManager, Redis, persistência) |
| `main.py` | Rotas HTTP, WebSocket e startup da aplicação |

## Endpoints HTTP

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Status do backend e conexão com o banco |
| GET | `/rooms` | Lista todas as salas e seus usuários conectados |
| GET | `/history/{room}` | Histórico de mensagens da sala |

## WebSocket

| Rota | Descrição |
|------|-----------|
| `/ws/{room}/{username}` | Conecta o usuário à sala via WebSocket |

**Mensagens recebidas pelo servidor:**
- Texto normal → persiste no PostgreSQL, publica no Redis
- `{"type": "pong"}` → atualiza heartbeat do cliente

**Mensagens enviadas pelo servidor:**
- `Connected to room: {room}` — confirmação de conexão
- `Active users: user1, user2` — lista de usuários na sala
- `System: {username} joined` — usuário entrou
- `System: {username} left` — usuário saiu
- `{"type": "ping"}` — heartbeat a cada 30s
- `{username}: {message}` — mensagem de chat

## Services

### ConnectionManager

Gerencia todas as conexões WebSocket ativas. Armazena em memória um dicionário de salas → usuários → WebSockets.

- **add_connection** / **remove_connection** — registra e remove clientes
- **broadcast_text** — envia mensagem de texto para todos na sala
- **update_pong** — registra resposta do heartbeat
- **start_heartbeat** — task assíncrona que envia ping a cada 30s e remove conexões sem pong há mais de 60s

### Redis Publisher / Subscriber

- **Publisher** publica mensagens no canal `chat:{room}`
- **Subscriber** pattern-subscribe em `chat:*` e broadcasta para os clientes conectados
- Permite escalabilidade horizontal: múltiplas instâncias do backend compartilham mensagens via Redis

## Configuração

Variáveis de ambiente (configuradas no `docker-compose.yml`):

| Variável | Valor padrão | Descrição |
|----------|-------------|-----------|
| `DATABASE_URL` | `postgresql://chatuser:chatpass@postgres:5432/chatdb` | Conexão PostgreSQL |
| `REDIS_URL` | `redis://redis:6379` | Conexão Redis |

## Testes

```bash
# Dentro do container
docker compose exec backend uv run python -m unittest discover tests -v

# Fora do container
cd backend && uv run python -m unittest discover tests -v
```

## Rodar localmente (fora do Docker)

```bash
cd backend
uv sync
DATABASE_URL=postgresql://chatuser:chatpass@localhost:5432/chatdb \
REDIS_URL=redis://localhost:6379 \
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
