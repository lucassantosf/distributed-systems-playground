
# Descrição 

Este projeto explora a arquitetura de microsserviços utilizando FastAPI, gRPC e Protocol Buffers para comunicação entre serviços independentes. Cada serviço possui seu próprio banco PostgreSQL, executado em containers Docker Compose, aplicando conceitos como isolamento de domínios, contratos tipados, comunicação eficiente e integração distribuída entre aplicações.

# Estrutura do Projeto

```
03-grpc-microservice/
├── README.md
├── Makefile              (targets: up, down, logs, e2e, validate-isolation, proto)
├── docker-compose.yml
├── .env                  (variáveis de ambiente para Docker)
├── .env.example
├── .gitignore
│
├── scripts/
│   └── e2e.sh            (teste E2E — make e2e)
│
├── logs/                 (bind mount — logs JSON de todos os serviços)
│
├── shared/
│   ├── protos/           (contratos Protocol Buffers)
│   │   ├── common/
│   │   │   └── types.proto
│   │   ├── user/
│   │   │   └── user.proto
│   │   ├── product/
│   │   │   └── product.proto
│   │   └── order/
│   │       └── order.proto
│   ├── interceptors/     (retry, logging, metadata — shared entre serviços)
│   └── common/
│       └── generated/    (código Python gerado dos protos)
│
├── user-service/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py       (FastAPI app)
│   │   ├── config.py     (settings via pydantic-settings)
│   │   ├── database.py   (SQLAlchemy engine + session)
│   │   ├── models/       (ORM — tabelas do banco)
│   │   ├── schemas/      (Pydantic — request/response)
│   │   ├── repositories/ (acesso a dados — CRUD)
│   │   ├── services/     (regras de negócio)
│   │   ├── routers/      (endpoints REST)
│   │   └── alembic/      (migrations)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env
│
├── product-service/      (mesma estrutura)
└── order-service/        (mesma estrutura)
```

## Arquitetura em Camadas (replicável em todos os serviços)

Cada microserviço segue a mesma organização interna:

| Camada | Responsabilidade |
|--------|------------------|
| **config.py** | Configurações centralizadas (DATABASE_URL, nome do serviço). Usa `pydantic-settings` para ler variáveis do `.env`. |
| **database.py** | Cria a engine de conexão com o PostgreSQL, define a `Base` do SQLAlchemy e fornece a sessão do banco (`get_db`). |
| **models/** | Entidades SQLAlchemy que mapeiam tabelas do banco. Cada arquivo representa uma tabela (ex: `user.py` → tabela `users`). |
| **schemas/** | Schemas Pydantic para validação de entrada e saída. Separa o que o cliente envia (`UserCreate`) do que a API retorna (`UserResponse`). |
| **repositories/** | Camada de acesso a dados. Executa queries CRUD no banco isolando a lógica de persistência da regra de negócio. |
| **services/** | Regras de negócio. Validações que dependem de múltiplos campos ou de dados existentes (ex: email único). Chamado pelos routers. |
| **routers/** | Endpoints FastAPI. Cada router define as rotas REST de uma entidade (ex: `POST /users`, `GET /users/{id}`). |
| **alembic/** | Migrations do banco. Permite versionar e aplicar mudanças no schema de forma controlada. |

## Como rodar

```bash
docker compose up --build
```

As migrations são executadas automaticamente na inicialização de cada serviço (via `entrypoint.sh`). Não é necessário rodar `alembic upgrade head` manualmente.

## Migrations (referência)

Para gerar novas migrations (exemplo com user-service):

```bash
# Gerar migration (autogenerate a partir dos models)
docker compose exec user-service alembic revision --autogenerate -m "descrição"

# Aplicar migrations pendentes
docker compose exec user-service alembic upgrade head

# Verificar versão atual
docker compose exec user-service alembic current

# Reverter última migration
docker compose exec user-service alembic downgrade -1
```

## Portas

| Serviço        | REST (FastAPI)               | gRPC                          |
|----------------|------------------------------|-------------------------------|
| user-service   | http://localhost:8001/health | localhost:50051               |
| product-service| http://localhost:8002/health | localhost:50052               |
| order-service  | http://localhost:8003/health | — (cliente apenas)            |

## Protocol Buffers (gRPC)

Os contratos gRPC ficam em `shared/protos/`. Para compilar e gerar o código Python:

```bash
# Instalar dependência (na máquina host)
pip install grpcio-tools

# Compilar todos os protos
make proto

# Ou diretamente
python -m grpc_tools.protoc \
    -I./shared/protos \
    --python_out=./shared/common/generated \
    --grpc_python_out=./shared/common/generated \
    ./shared/protos/common/types.proto \
    ./shared/protos/user/user.proto \
    ./shared/protos/product/product.proto \
    ./shared/protos/order/order.proto
```

Os arquivos gerados ficam em `shared/common/generated/`.

## Makefile

| Target                 | Descrição |
|------------------------|-----------|
| `make up`              | Sobe todos os containers (cria `./logs` com permissão 777) |
| `make down`            | Para todos os containers |
| `make restart`         | Reinicia os containers |
| `make logs`            | Mostra logs dos 3 serviços |
| `make logs-user`       | Logs do user-service |
| `make logs-product`    | Logs do product-service |
| `make logs-order`      | Logs do order-service |
| `make logs-pretty`     | Logs formatados (JSON pretty-print) |
| `make logs-clear`      | Limpa todos os logs |
| `make proto`           | Compila os arquivos .proto |
| `make clean`           | Remove arquivos gerados |
| `make validate-isolation` | Verifica isolamento de rede entre serviços e bancos |
| `make e2e`             | Executa 25 testes de fluxo completo |

## Logs Estruturados

Todos os serviços emitem logs em **JSON** com os seguintes campos:

```json
{
  "timestamp": "2026-07-28T20:36:12Z",
  "service": "order-service",
  "level": "INFO",
  "logger": "uvicorn.access",
  "message": "POST /orders/ 201",
  "request_id": "a1b2c3d4-...",
  "method": "POST",
  "path": "/orders/",
  "status_code": 201
}
```

**Características:**

- **`ResilientFileHandler`** — recria automaticamente arquivos de log deletados externamente
- **`JsonFormatter`** — logs em JSON para processamento automatizado
- **`ServiceContextFilter`** — injeta service name, request-id em cada registro
- **`request_id` via `contextvars`** — propagado através de `set_request_id()`/`get_request_id()`
- **Propagação HTTP → gRPC** — request-id via metadata gRPC (ASCII only)
- **Bind mount `./logs:/logs`** — todos os logs centralizados no host
- **Rotas com/sem trailing slash** — `/orders` e `/orders/` para evitar redirect 307

## gRPC Features

### Interceptors

| Interceptor | Tipo | Descrição |
|---|---|---|
| `LoggingServerInterceptor` | Server | Loga chamadas gRPC recebidas (método, peer, status) |
| `LoggingClientInterceptor` | Client | Loga chamadas gRPC enviadas (target, método, latência) |
| `RetryClientInterceptor` | Client | Retry com exponential backoff em falhas temporárias |

### Retry

O `RetryClientInterceptor` tenta novamente em códigos `UNAVAILABLE` e `DEADLINE_EXCEEDED`:

```
Tentativa 1 → falha → espera 0.5s
Tentativa 2 → falha → espera 1.2s
Tentativa 3 → falha → espera 2.8s → erro final
```

### Timeout

Todas as chamadas gRPC usam `GRPC_TIMEOUT=5` segundos configurado via variável de ambiente.

### Metadata

O `request_id` é propagado automaticamente:
- Requisição HTTP chega → `set_request_id()` gera/captura o ID
- Chamada gRPC parte → `LoggingClientInterceptor` injeta o request-id no metadata
- Servidor gRPC recebe → `LoggingServerInterceptor` extrai e aplica via `set_request_id()`

## Tratamento de Erros

### Erros padronizados

| Tipo | HTTP | Descrição |
|---|---|---|
| `MicroserviceError` | 400-503 | Erro genérico de microsserviço (contém `service` e `type`) |
| `UserNotFoundError` | 404 | Usuário não encontrado |
| `ProductNotFoundError` | 404 | Produto não encontrado |
| `InsufficientStockError` | 409 | Estoque insuficiente |
| `ServiceUnavailableError` | 503 | Serviço remoto indisponível (após retry) |
| `ServiceTimeoutError` | 504 | Timeout na chamada gRPC |

### Formato de resposta de erro

```json
{
  "error": "user-service",
  "message": "User test@example.com not found",
  "type": "microservice_error"
}
```

## Isolamento de Rede

Cada serviço e seu banco estão em redes Docker separadas. A comunicação entre serviços ocorre exclusivamente via gRPC em uma rede compartilhada.

```
user-db ── user-net ── user-service ──┐
                                       ├── grpc-net
product-db ── product-net ── product-service ──┘
                                       │
order-db ── order-net ── order-service ┘
```

Validado por: `make validate-isolation`

# Epic 1 — Fundação [OK]

## Card 1 — Criar estrutura inicial do projeto [OK]

    Descrição: Organizar serviços, diretórios e Docker Compose.

## Card 2 — Configurar infraestrutura local [OK]

    Descrição: Subir FastAPI, PostgreSQL e rede entre containers.

## Card 3 — Configurar bancos independentes [OK]

    Descrição: Cada serviço possui seu próprio banco de dados.

# Epic 2 — User Service [OK]

## Card 4 — Implementar domínio de usuários [OK]

Descrição: Criar entidade, persistência e regras básicas.

## Card 5 — Criar API REST de usuários [OK]

Descrição: Cadastrar e consultar usuários via HTTP.

## Card 6 — Validar funcionamento do User Service [OK]

Descrição: Garantir persistência e consultas corretamente.

# Epic 3 — Product Service [OK]

## Card 7 — Implementar domínio de produtos [OK]

Descrição: Criar entidade, persistência e estoque inicial.

## Card 8 — Criar API REST de produtos [OK]

Descrição: Cadastrar e consultar produtos via HTTP.

## Card 9 — Validar funcionamento do Product Service [OK]

Descrição: Garantir persistência e consultas corretamente.

# Epic 4 — Introdução ao gRPC [OK]

## Card 10 — Criar contratos Protocol Buffers [OK]

Descrição: Definir mensagens e serviços compartilhados.

## Card 11 — Implementar servidor gRPC do User Service [OK]

Descrição: Expor usuários através de contratos tipados.

## Card 12 — Consumir User Service via gRPC [OK]

Descrição: Criar cliente e validar comunicação remota.

# Epic 5 — gRPC no Product Service [OK]

## Card 13 — Implementar servidor gRPC do Product Service [OK]

Descrição: Expor informações de produtos via gRPC.

## Card 14 — Consumir Product Service via gRPC [OK]

Descrição: Validar comunicação remota entre serviços.

## Card 15 — Consolidar comunicação entre serviços [OK]

Descrição: Garantir contratos consistentes e reutilizáveis.

# Epic 6 — Order Service [OK]

## Card 16 — Implementar domínio de pedidos [OK]

Descrição: Criar entidade, persistência e regras principais.

## Card 17 — Criar API REST de pedidos [OK]

Descrição: Receber requisições para criação de pedidos.

## Card 18 — Integrar Order com User Service [OK]

Descrição: Validar existência do usuário usando gRPC.

# Epic 7 — Integração Completa [OK]

## Card 19 — Integrar Order com Product Service [OK]

Descrição: Buscar produto antes de criar pedidos.

## Card 20 — Validar regras de negócio distribuídas [OK]

Descrição: Criar pedidos somente com dados válidos.

## Card 21 — Calcular valores utilizando Product Service [OK]

Descrição: Nunca confiar em preços enviados pelo cliente.

# Epic 8 — Tratamento de Falhas [OK]

## Card 22 — Tratar erros entre microsserviços [OK]

Descrição: Usuário inexistente, produto inválido e timeouts.

## Card 23 — Padronizar respostas de erro [OK]

Descrição: Retornar erros consistentes entre serviços.

## Card 24 — Implementar timeout nas chamadas gRPC [OK]

Descrição: Evitar bloqueios em falhas de comunicação.

# Epic 9 — Robustez [OK]

## Card 25 — Adicionar interceptors gRPC [OK]

Descrição: Registrar logs automaticamente em cada chamada.

## Card 26 — Implementar metadata das requisições [OK]

Descrição: Compartilhar informações entre serviços.

## Card 27 — Criar logs estruturados [OK]

Descrição: Facilitar rastreamento e depuração distribuída.

# Epic 10 — Finalização [OK]

## Card 28 — Implementar retry nas chamadas gRPC [OK]

Descrição: Recuperar falhas temporárias automaticamente.

## Card 29 — Validar isolamento entre serviços [OK]

Descrição: Nenhum serviço acessa banco de outro.

## Card 30 — Executar fluxo completo de pedidos [OK]

Descrição: Validar comunicação ponta a ponta entre microsserviços. 25 testes E2E (Makefile: `make e2e`).