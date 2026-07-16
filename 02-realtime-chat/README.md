# Realtime Chat

Chat em tempo real construído como projeto de estudo de sistemas distribuídos. O usuário entra com um username e uma sala, e todas as mensagens são entregues em tempo real para todos os participantes da sala.

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | React + TypeScript + Vite |
| Backend | Python + FastAPI + WebSocket |
| Banco de dados | PostgreSQL |
| Cache / Pub/Sub | Redis |
| Infraestrutura | Docker Compose |

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e Docker Compose
- Git

## Como rodar

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd distributed-systems-playground/02-realtime-chat

# Suba todos os serviços
docker compose up --build
```

Aguardar até todos os serviços estarem prontos. Você verá no terminal:

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### Verificar se está rodando

```bash
# Testar o backend
curl http://localhost:8000/

# Ver logs em tempo real
docker compose logs -f
```

### Parar os serviços

```bash
docker compose down
```

### Limpar dados (banco e volumes)

```bash
docker compose down -v
```

## Como usar

1. Acesse http://localhost:5173
2. Digite um **Username** e uma **Room**
3. Clique em **Join Chat** (ou pressione Enter)
4. Abra outra aba no navegador com a mesma sala para testar com dois usuários
5. Envie mensagens — elas aparecem em tempo real em todas as abas

## Funcionalidades

- Salas de chat isoladas (rooms)
- Mensagens em tempo real via WebSocket
- Histórico de mensagens persistido no PostgreSQL
- Lista de usuários online na sala
- Indicadores de entrada e saída (`Lucas joined` / `Lucas left`)
- Mensagens próprias diferenciadas (cor e posição)
- Auto-scroll na lista de mensagens
- Reconexão automática com backoff exponencial
- Heartbeat do servidor para detectar conexões mortas
- Pub/Sub via Redis para distribuição de mensagens

## Arquitetura (visão geral)

```
┌──────────┐    WebSocket    ┌──────────┐    SQL     ┌────────────┐
│ Frontend │◄───────────────►│ Backend  │◄──────────►│ PostgreSQL │
│  (React) │                 │ (FastAPI)│            └────────────┘
└──────────┘                 └────┬─────┘
                                  │ Pub/Sub
                                  ▼
                            ┌──────────┐
                            │  Redis   │
                            └──────────┘
```

**Fluxo de uma mensagem:**

1. Usuário envia mensagem pelo frontend
2. Backend recebe via WebSocket
3. Mensagem é persistida no PostgreSQL
4. Mensagem é publicada no Redis (canal da sala)
5. Subscriber recebe do Redis e broadcasta para todos da sala via WebSocket
6. Frontend atualiza a interface em tempo real

## Estrutura do projeto

```
02-realtime-chat/
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py              # Ponto de entrada, rotas e WebSocket
│   │   ├── config.py            # Configurações (DB, Redis)
│   │   ├── domain/              # Entidades de negócio
│   │   ├── infrastructure/      # Conexão com banco de dados
│   │   ├── repositories/        # Acesso a dados
│   │   └── services/            # Lógica de aplicação
│   └── tests/
└── frontend/
    └── src/
        ├── pages/               # Tela inicial e chat
        ├── features/chat/       # Componentes do chat
        ├── components/          # Componentes reutilizáveis
        ├── types/               # Interfaces TypeScript
        └── styles/              # CSS global
```

## Comandos úteis

```bash
# Logs de um serviço específico
docker compose logs -f backend
docker compose logs -f frontend

# Reiniciar apenas o backend (após mudanças no código)
docker compose restart backend

# Rodar testes do backend
docker compose exec backend uv run python -m unittest discover tests -v

# Acessar o shell do container
docker compose exec backend bash
docker compose exec frontend sh
```

---

## TODO List — Cards de desenvolvimento

### Epic 1 — Fundação [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 1 | Criar estrutura inicial do projeto | OK |
| 2 | Subir ambiente Docker (FastAPI, PostgreSQL, Redis) | OK |
| 3 | Configurar banco de dados | OK |

### Epic 2 — Primeira Interface [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 4 | Criar tela inicial (Username, Room, Join Chat) | OK |
| 5 | Criar tela de conversa (layout sem WebSocket) | OK |

### Epic 3 — Primeiro WebSocket [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 6 | Criar endpoint WebSocket | OK |
| 7 | Manter usuários conectados (Connection Manager) | OK |
| 8 | Enviar mensagem para o servidor | OK |

### Epic 4 — Broadcast [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 9 | Enviar mensagem para todos | OK |
| 10 | Adicionar username às mensagens | OK |
| 11 | Criar salas (rooms) | OK |

### Epic 5 — Persistência [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 12 | Criar entidade Message | OK |
| 13 | Salvar mensagens no PostgreSQL | OK |
| 14 | Carregar histórico ao entrar na sala | OK |

### Epic 6 — Redis Pub/Sub [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 15 | Publicar mensagens no Redis | OK |
| 16 | Consumir mensagens do Redis | OK |

### Epic 7 — Presença Online [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 17 | Mostrar usuários online | OK |
| 18 | Detectar desconexão | OK |

### Epic 8 — Melhorias do Chat [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 19 | Indicador de entrada e saída (joined/left) | OK |
| 20 | Timestamp das mensagens (HH:MM) | OK |
| 21 | Auto-scroll na lista de mensagens | OK |
| 22 | Diferenciar mensagens próprias (cor e posição) | OK |

### Epic 9 — Robustez [OK]

| Card | Descrição | Status |
|------|-----------|--------|
| 23 | Reconexão automática com backoff | OK |
| 24 | Heartbeat/Ping do servidor | OK |
| 25 | Remoção de conexões mortas | OK |
