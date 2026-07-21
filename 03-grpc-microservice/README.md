
# Descrição 

Este projeto explora a arquitetura de microsserviços utilizando FastAPI, gRPC e Protocol Buffers para comunicação entre serviços independentes. Cada serviço possui seu próprio banco PostgreSQL, executado em containers Docker Compose, aplicando conceitos como isolamento de domínios, contratos tipados, comunicação eficiente e integração distribuída entre aplicações.

# Estrutura do Projeto

```
03-grpc-microservice/
├── README.md
├── Makefile              (compile protos)
├── docker-compose.yml
├── .env                  (variáveis de ambiente para Docker)
├── .env.example
├── .gitignore
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
│   └── common/           (código compartilhado)
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

| Serviço        | URL                          |
|----------------|------------------------------|
| user-service   | http://localhost:8001/health |
| product-service| http://localhost:8002/health |
| order-service  | http://localhost:8003/health |

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

# Epic 4 — Introdução ao gRPC [*]

## Card 10 — Criar contratos Protocol Buffers [*]

Descrição: Definir mensagens e serviços compartilhados.

## Card 11 — Implementar servidor gRPC do User Service [*]

Descrição: Expor usuários através de contratos tipados.

## Card 12 — Consumir User Service via gRPC [*]

Descrição: Criar cliente e validar comunicação remota.

# Epic 5 — gRPC no Product Service [*]

## Card 13 — Implementar servidor gRPC do Product Service [*]

Descrição: Expor informações de produtos via gRPC.

## Card 14 — Consumir Product Service via gRPC [*]

Descrição: Validar comunicação remota entre serviços.

## Card 15 — Consolidar comunicação entre serviços [*]

Descrição: Garantir contratos consistentes e reutilizáveis.

# Epic 6 — Order Service [*]

## Card 16 — Implementar domínio de pedidos [*]

Descrição: Criar entidade, persistência e regras principais.

## Card 17 — Criar API REST de pedidos [*]

Descrição: Receber requisições para criação de pedidos.

## Card 18 — Integrar Order com User Service [*]

Descrição: Validar existência do usuário usando gRPC.

# Epic 7 — Integração Completa [*]

## Card 19 — Integrar Order com Product Service [*]

Descrição: Buscar produto antes de criar pedidos.

## Card 20 — Validar regras de negócio distribuídas [*]

Descrição: Criar pedidos somente com dados válidos.

## Card 21 — Calcular valores utilizando Product Service [*]

Descrição: Nunca confiar em preços enviados pelo cliente.

# Epic 8 — Tratamento de Falhas [*]

## Card 22 — Tratar erros entre microsserviços [*]

Descrição: Usuário inexistente, produto inválido e timeouts.

## Card 23 — Padronizar respostas de erro [*]

Descrição: Retornar erros consistentes entre serviços.

## Card 24 — Implementar timeout nas chamadas gRPC [*]

Descrição: Evitar bloqueios em falhas de comunicação.

# Epic 9 — Robustez [*]

## Card 25 — Adicionar interceptors gRPC [*]

Descrição: Registrar logs automaticamente em cada chamada.

## Card 26 — Implementar metadata das requisições [*]

Descrição: Compartilhar informações entre serviços.

## Card 27 — Criar logs estruturados [*]

Descrição: Facilitar rastreamento e depuração distribuída.

# Epic 10 — Finalização [*]

## Card 28 — Implementar retry nas chamadas gRPC [*]

Descrição: Recuperar falhas temporárias automaticamente.

## Card 29 — Validar isolamento entre serviços [*]

Descrição: Nenhum serviço acessa banco de outro.

## Card 30 — Executar fluxo completo de pedidos [*]

Descrição: Validar comunicação ponta a ponta entre microsserviços.