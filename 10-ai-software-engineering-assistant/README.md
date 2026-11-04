# 🤖 AI Software Engineering Assistant

## 📖 Descrição

Este projeto implementa uma plataforma de análise de repositórios de código utilizando Inteligência Artificial. O usuário informa uma URL de um repositório público do GitHub e a aplicação realiza a ingestão, chunking e indexação semântica do código-fonte. A partir disso, é possível conversar com o repositório em linguagem natural — fazendo perguntas sobre a arquitetura, módulos, dependências e comportamentos do sistema — recebendo respostas fundamentadas nos trechos de código mais relevantes.

O projeto aplica o padrão **RAG (Retrieval-Augmented Generation)**: o conteúdo do repositório é fragmentado, transformado em embeddings e armazenado em um banco vetorial. A cada pergunta do usuário, os trechos mais semanticamente próximos são recuperados e enviados como contexto ao LLM, que gera uma resposta embasada no código real do projeto.

---

## 🎯 Objetivos do Projeto

- Implementar um pipeline de **RAG aplicado a código-fonte** do zero
- Entender como realizar **chunking de código** de forma eficaz (por arquivo, por função, por bloco)
- Gerar e persistir **embeddings** usando modelos de linguagem (OpenAI Embeddings ou similar)
- Realizar **busca semântica** via pgvector para recuperar contexto relevante
- Integrar com a **GitHub API** para clonar e extrair arquivos de repositórios públicos
- Construir um **chat interativo** que conversa com o repositório via LLM
- Praticar **Prompt Engineering** para respostas precisas e fundamentadas
- Praticar **processamento assíncrono** com background jobs de ingestão
- Praticar **Clean Architecture, SOLID e DDD pragmático** num projeto de IA real
- Expor uma **API REST** bem estruturada com FastAPI

---

## 🏗️ Arquitetura de Infraestrutura

### Visão Geral dos Componentes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USUÁRIO (Browser)                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTP
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                             │
│   • Formulário para submissão de URL do repositório                 │
│   • Interface de chat (pergunta → resposta)                         │
│   • Status da ingestão (pending / indexing / ready)                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ REST API
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                             │
│                                                                     │
│  ┌──────────────────┐    ┌───────────────────┐                      │
│  │  Ingestion API   │    │    Chat API        │                      │
│  │  POST /repos     │    │  POST /chat        │                      │
│  │  GET  /repos/:id │    │  (question → ans)  │                      │
│  └────────┬─────────┘    └────────┬──────────┘                      │
│           │                       │                                 │
│           ▼                       ▼                                 │
│  ┌──────────────────┐    ┌───────────────────┐                      │
│  │ Background Job   │    │    RAG Engine      │                      │
│  │ (Ingestão async) │    │  1. Embed query    │                      │
│  │                  │    │  2. Vector search  │                      │
│  │  1. Clone repo   │    │  3. Build context  │                      │
│  │  2. Parse files  │    │  4. Call LLM       │                      │
│  │  3. Chunk code   │    └────────┬──────────┘                      │
│  │  4. Embed chunks │             │                                 │
│  │  5. Store vectors│             │                                 │
│  └────────┬─────────┘             │                                 │
└───────────┼───────────────────────┼─────────────────────────────────┘
            │                       │
            ▼                       ▼
┌──────────────────────────────────────────────────────┐
│             PostgreSQL + pgvector                    │
│  • Tabela: repositories (metadados do repo)          │
│  • Tabela: chunks (código fragmentado + embeddings)  │
│  • Busca por similaridade via operador <=>           │
└──────────────────────────────────────────────────────┘
            │                       │
            ▼                       ▼
┌──────────────────┐    ┌───────────────────────────────┐
│   GitHub API     │    │         LLM API               │
│  (repositórios   │    │  (OpenAI / Gemini / Anthropic) │
│   públicos)      │    │  • Chat Completions            │
└──────────────────┘    │  • Embeddings                 │
                        └───────────────────────────────┘
```

### Fluxo de Ingestão

```
URL do Repo
    │
    ▼
GitHub API ──► listar arquivos do repositório
    │
    ▼
Parser de Arquivos ──► filtrar extensões relevantes (.py, .ts, .go, etc.)
    │
    ▼
Chunker de Código ──► fragmentar por tamanho fixo com overlap
    │
    ▼
Embedding Model ──► gerar vetor por chunk
    │
    ▼
pgvector ──► persistir chunk + embedding
```

### Fluxo de Chat (RAG)

```
Pergunta do Usuário
    │
    ▼
Embedding Model ──► vetorizar a pergunta
    │
    ▼
pgvector ──► buscar top-K chunks mais similares
    │
    ▼
Prompt Builder ──► montar contexto: [instrução de sistema + chunks + pergunta]
    │
    ▼
LLM API ──► gerar resposta baseada no contexto
    │
    ▼
Resposta + Sources (arquivos que embasaram a resposta)
```

---

## 🧱 Arquitetura de Software

### Decisão Arquitetural

O projeto adota **Clean Architecture + SOLID + DDD pragmático** como guia de organização do código. O objetivo é manter o núcleo da aplicação (domínio e casos de uso) completamente desacoplado de frameworks, banco de dados e provedores externos (OpenAI, GitHub, etc.).

> **Princípio central:** o núcleo deve conseguir executar seus casos de uso sem precisar conhecer qual framework, banco de dados, provedor de IA ou serviço externo está sendo utilizado.

O que **não** será adotado (para manter a complexidade sob controle): microserviços, arquitetura hexagonal completa, CQRS, Event Sourcing.

---

### Estrutura de Pastas

```
src/
├── domain/                        # Conceitos e regras do negócio. Não conhece FastAPI, PostgreSQL ou OpenAI.
│   ├── entities/
│   │   ├── repository.py          # Entidade: repositório analisado (id, url, status, metadados)
│   │   └── code_chunk.py          # Entidade: fragmento de código indexado (content, file_path, embedding)
│   └── exceptions/                # Exceções de domínio (ex: RepositoryNotReady, RepositoryNotFound)
│
├── application/                   # Casos de uso. Coordena o que precisa acontecer, sem saber como.
│   ├── use_cases/
│   │   ├── ingest_repository.py   # Orquestra: clonar → chunkar → embedar → persistir
│   │   └── chat_with_repository.py # Orquestra: embedar query → buscar → montar prompt → chamar LLM
│   ├── interfaces/                # Contratos (interfaces/protocolos) que a infraestrutura deve implementar
│   │   ├── repository_provider.py # Contrato: como acessar arquivos de um repositório remoto
│   │   ├── vector_store.py        # Contrato: como armazenar e buscar chunks por similaridade
│   │   ├── embedding_provider.py  # Contrato: como gerar embeddings de um texto
│   │   ├── llm_provider.py        # Contrato: como chamar um LLM e obter resposta
│   │   ├── repository_store.py    # Contrato: como persistir e consultar metadados de repositórios
│   │   └── task_dispatcher.py     # Contrato: como despachar tarefas em background
│   └── dtos/                      # Objetos de transferência de dados entre camadas
│       ├── ingest_repository_dto.py  # DTO de entrada para o Use Case IngestRepository
│       ├── chat_request_dto.py       # DTO de entrada para o Use Case ChatWithRepository
│       ├── chat_response_dto.py      # DTO de saída do Use Case ChatWithRepository (answer + sources)
│       └── file_content_dto.py       # DTO que representa um arquivo recuperado do GitHub (path + content)
│
├── infrastructure/                # Implementações concretas dos contratos definidos na camada de aplicação.
│   ├── github/
│   │   └── github_repository_provider.py  # Implementa RepositoryProvider usando GitHub REST API v3
│   ├── llm/
│   │   └── openai_llm_provider.py         # Implementa LLMProvider usando OpenAI Chat Completions
│   ├── embeddings/
│   │   └── openai_embedding_provider.py   # Implementa EmbeddingProvider usando OpenAI Embeddings
│   ├── persistence/
│   │   ├── models.py                      # Modelos SQLAlchemy (separados das entidades de domínio)
│   │   ├── pg_vector_store.py             # Implementa VectorStore usando PostgreSQL + pgvector
│   │   └── pg_repository_store.py         # Implementa RepositoryStore usando SQLAlchemy
│   └── background/
│       └── asyncio_task_dispatcher.py     # Implementa TaskDispatcher usando asyncio.create_task
│
├── presentation/                  # Recebe requisições HTTP, valida entradas, entrega respostas.
│   └── api/
│       ├── routes/
│       │   ├── repos.py           # Endpoints: POST /repos, GET /repos/{id}
│       │   └── chat.py            # Endpoint: POST /chat
│       ├── schemas/               # Schemas Pydantic de entrada e saída dos endpoints
│       │   ├── repo_schemas.py
│       │   └── chat_schemas.py
│       └── dependencies.py        # Injeção de dependências: monta e injeta os Use Cases com suas implementações
│
└── main.py                        # Ponto de entrada: cria o app FastAPI e registra os routers
```

---

### Contratos e Implementações

A tabela abaixo documenta cada contrato definido na camada de `application/interfaces/` e sua implementação correspondente na infraestrutura. Se amanhã qualquer implementação precisar ser trocada, a alteração fica **restrita à infraestrutura** — nenhum caso de uso precisa mudar.

| Necessidade do sistema | Contrato (`application/interfaces/`) | Implementação (`infrastructure/`) |
|---|---|---|
| Acessar arquivos do repositório | `RepositoryProvider` | `GithubRepositoryProvider` (GitHub REST API v3) |
| Gerar embeddings de texto | `EmbeddingProvider` | `OpenAIEmbeddingProvider` (OpenAI Embeddings) |
| Chamar um LLM | `LLMProvider` | `OpenAILLMProvider` (OpenAI Chat Completions) |
| Armazenar e buscar chunks | `VectorStore` | `PgVectorStore` (PostgreSQL + pgvector) |
| Persistir metadados de repos | `RepositoryStore` | `PgRepositoryStore` (SQLAlchemy) |
| Despachar tarefas em background | `TaskDispatcher` | `AsyncioTaskDispatcher` (asyncio.create_task) |

> **Nota sobre `RepositoryStore`:** o nome intencionalmente evita `RepositoryRepository` (padrão Repository aplicado à entidade `Repository`), que causaria confusão de leitura. `RepositoryStore` é equivalente e mais claro.

---

### Regras que este projeto segue

Para não transformar Clean Architecture em burocracia:

1. **Modelos SQLAlchemy ficam na infraestrutura.** As entidades de domínio (`domain/entities/`) são classes Python puras, sem herdar de `Base` do SQLAlchemy.
2. **Use Cases não recebem objetos `Request` do FastAPI.** A camada de apresentação converte a requisição em um DTO antes de chamar o Use Case.
3. **O domínio não importa bibliotecas externas.** Nem `openai`, nem `httpx`, nem `sqlalchemy`.
4. **Use Cases não chamam OpenAI diretamente.** Utilizam os contratos (`EmbeddingProvider`, `LLMProvider`).
5. **Não criar interfaces para absolutamente tudo.** Abstrair apenas o que representa uma dependência externa ou um contrato importante.
6. **Não criar camadas desnecessárias.** Uma classe só precisa existir se tiver uma responsabilidade real.

---

### Conceitos de DDD utilizados

O projeto adota DDD de forma leve, principalmente para organizar o vocabulário e os conceitos do negócio:

| Conceito | Descrição |
|---|---|
| `Repository` | O repositório GitHub analisado — entidade principal do sistema |
| `CodeChunk` | Fragmento de código extraído do repositório, com seu embedding |
| `SourceReference` | Referência ao arquivo e trecho que fundamentou uma resposta do LLM |

> Padrões táticos mais avançados do DDD (Aggregates, Domain Events, Factories) não serão adotados na Fase 1, pois não trazem benefício real para o escopo atual.

---

## 🧠 Conceitos Arquiteturais Praticados

- **Retrieval-Augmented Generation (RAG)** — padrão central do projeto
- **Code Chunking e Embeddings** — estratégias para fragmentar e vetorizar código
- **Vector Search / Semantic Search** — busca por similaridade com pgvector
- **Context Management e Prompt Engineering** — montagem de contexto eficaz para o LLM
- **Clean Architecture** — separação de domínio, casos de uso, infraestrutura e apresentação
- **SOLID** — especialmente Inversão de Dependência (DIP) e Responsabilidade Única (SRP)
- **DDD Pragmático** — vocabulário e entidades do negócio, sem complexidade excessiva
- **Dependency Injection** — injeção das implementações nos casos de uso via `dependencies.py`
- **Processamento Assíncrono e Background Jobs** — ingestão sem bloquear a requisição
- **Integração com APIs Externas** — GitHub API e LLM APIs

---

## 🛠️ Stack

| Componente | Tecnologia |
|---|---|
| Frontend | React |
| Backend | FastAPI (Python) |
| Banco vetorial | PostgreSQL + pgvector |
| Embeddings / LLM | OpenAI API (ou compatível) |
| Integração GitHub | GitHub REST API v3 |
| ORM / Migrations | SQLAlchemy + Alembic |
| Containerização | Docker + Docker Compose |

---

## 📋 Epics e Cards

### Epic 1 — Infraestrutura Base e Estrutura do Projeto

**[OK] Card 1.1 — Setup Inicial do Projeto e Estrutura de Pastas**

Criar a estrutura de pastas do projeto conforme definida na seção de Arquitetura de Software (`src/domain/`, `src/application/`, `src/infrastructure/`, `src/presentation/`). Inicializar o repositório com `docker-compose.yml` orquestrando os serviços: `api` (FastAPI) e `db` (PostgreSQL + pgvector). O backend deve ter uma rota `GET /health` que retorne `{ "status": "ok" }`. O `main.py` deve criar o app FastAPI e registrar os routers.

**[*] Card 1.2 — Setup do PostgreSQL com pgvector e Migrations**

Configurar o container do PostgreSQL com a extensão `pgvector` habilitada. Criar as migrations iniciais com Alembic. Os **modelos SQLAlchemy** ficam em `infrastructure/persistence/models.py` — separados das entidades de domínio.

Tabelas a criar:
- `repositories`: `id` (UUID), `github_url`, `name`, `status` (`pending` | `indexing` | `ready` | `error`), `created_at`, `indexed_at`
- `chunks`: `id` (UUID), `repository_id` (FK), `file_path`, `content` (text), `embedding` (vector), `chunk_index`, `created_at`

Validar que a busca por similaridade (`<=>`) funciona com um script simples de smoke test inserindo 2 vetores e consultando o mais próximo.

**[*] Card 1.3 — Configuração via Variáveis de Ambiente**

Centralizar toda configuração em `.env` usando `pydantic-settings` em `src/settings.py`. Variáveis esperadas: `DATABASE_URL`, `OPENAI_API_KEY`, `GITHUB_TOKEN` (opcional, para maior rate limit), `EMBEDDING_MODEL` (default: `text-embedding-3-small`), `LLM_MODEL` (default: `gpt-4o-mini`), `VECTOR_SEARCH_TOP_K` (default: `5`). Incluir `.env.example` com valores fictícios documentados.

**[*] Card 1.4 — Definição dos Contratos (Interfaces)**

Criar os contratos em `src/application/interfaces/` como classes abstratas Python (usando `abc.ABC` e `@abstractmethod`):
- `EmbeddingProvider`: método `embed(text: str) -> list[float]`
- `LLMProvider`: método `complete(prompt: str) -> str`
- `RepositoryProvider`: método `list_files(owner: str, repo: str) -> list[FileContentDTO]` — retorna lista de `FileContentDTO` (definido em `application/dtos/file_content_dto.py`)
- `VectorStore`: métodos `save_chunks(chunks)` e `search(embedding, repo_id, top_k) -> list[CodeChunk]`
- `RepositoryStore`: métodos `save(repo)`, `get_by_id(id)`, `update_status(id, status)`
- `TaskDispatcher`: método `dispatch(coro) -> None`

Esses contratos são o coração da Clean Architecture: os Use Cases dependem deles, nunca das implementações concretas.

**[*] Card 1.5 — Dependency Injection em `dependencies.py`**

Implementar `src/presentation/api/dependencies.py` como o ponto central de montagem das dependências. Este arquivo instancia as implementações concretas da infraestrutura e as injeta nos Use Cases via FastAPI `Depends`. Exemplo de responsabilidade: `get_chat_use_case()` retorna uma instância de `ChatWithRepository` já configurada com `OpenAIEmbeddingProvider`, `PgVectorStore` e `OpenAILLMProvider`.

---

### Epic 2 — Integração com GitHub

**[*] Card 2.1 — Endpoint de Submissão de Repositório**

Implementar os schemas Pydantic em `presentation/api/schemas/repo_schemas.py` e os endpoints em `presentation/api/routes/repos.py`:
- `POST /repos`: recebe `{ "github_url": "https://github.com/owner/repo" }`, valida o formato da URL, converte para `IngestRepositoryDTO`, cria o registro via `RepositoryStore` com `status = "pending"`, despacha o Use Case `IngestRepository` em background via `TaskDispatcher` e retorna `{ "id": "uuid", "status": "pending" }` imediatamente — sem aguardar a ingestão terminar.
- `GET /repos/{id}`: retorna o status atual da ingestão consultando o `RepositoryStore`.

A rota **não** chama diretamente a infraestrutura — usa os contratos via injeção de dependências.

**[*] Card 2.2 — GitHub API Client (`GithubRepositoryProvider`)**

Criar `infrastructure/github/github_repository_provider.py` implementando o contrato `RepositoryProvider`. Usando a GitHub REST API v3:
- Listar arquivos recursivamente via `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`
- Filtrar extensões relevantes: `.py`, `.ts`, `.js`, `.go`, `.java`, `.rb`, `.rs`, `.md`
- Recuperar conteúdo raw via `GET /repos/{owner}/{repo}/contents/{path}`
- Respeitar rate limit: usar `GITHUB_TOKEN` se configurado, tratar erro 403/429

Retornar lista de `FileContent` (path + content como string).

---

### Epic 3 — Pipeline de Ingestão

**[*] Card 3.1 — Use Case `IngestRepository`**

Criar `application/use_cases/ingest_repository.py`. Este Use Case recebe um `IngestRepositoryDTO` (com `repo_id` e `github_url`) e orquestra:
1. Atualiza `status` para `"indexing"` via `RepositoryStore`
2. Lista e baixa arquivos via `RepositoryProvider`
3. Gera chunks de cada arquivo (delegado ao `CodeChunker`)
4. Gera embedding de cada chunk via `EmbeddingProvider`
5. Persiste chunks + embeddings via `VectorStore`
6. Atualiza `status` para `"ready"` (ou `"error"` em caso de exceção)

O Use Case depende apenas dos contratos — não conhece OpenAI, PostgreSQL ou GitHub.

**[*] Card 3.2 — Code Chunker**

Criar `src/application/chunker.py` como módulo auxiliar puro (sem dependências externas) com a lógica de chunking. Estratégia: quebrar o conteúdo de cada arquivo em blocos de tamanho fixo (ex: 400 linhas ou ~1500 caracteres) com overlap de 10% para preservar contexto entre chunks adjacentes. Arquivos menores que o tamanho máximo são tratados como um único chunk. Preservar metadados: `file_path` e `chunk_index`. Registrar nos logs quantos chunks foram gerados por arquivo. O Use Case `IngestRepository` chama o chunker internamente antes de gerar os embeddings.

**[*] Card 3.3 — `OpenAIEmbeddingProvider`**

Criar `infrastructure/embeddings/openai_embedding_provider.py` implementando o contrato `EmbeddingProvider`. Chamar a API de embeddings da OpenAI (modelo configurado via `EMBEDDING_MODEL`). Processar em batches de até 20 textos por requisição para respeitar limites de rate. Logar progresso (ex: `"Embedded 40/200 chunks for repo X"`).

**[*] Card 3.4 — `PgVectorStore` e `PgRepositoryStore`**

Criar `infrastructure/persistence/pg_vector_store.py` implementando `VectorStore`: método `save_chunks` persiste a lista de `CodeChunk` (incluindo embedding) e método `search` executa a query de similaridade `ORDER BY embedding <=> :query_embedding LIMIT :top_k` filtrada por `repository_id`.

Criar `infrastructure/persistence/pg_repository_store.py` implementando `RepositoryStore`: `save`, `get_by_id` e `update_status` usando SQLAlchemy.

**[*] Card 3.5 — `AsyncioTaskDispatcher`**

Criar `infrastructure/background/asyncio_task_dispatcher.py` implementando o contrato `TaskDispatcher` usando `asyncio.create_task`. Esta implementação é suficiente para a Fase 1 e será substituída por Celery na Fase 2 sem alterar nenhum Use Case ou rota — apenas a implementação registrada no `dependencies.py`.

**[*] Card 3.6 — Script de Validação da Ingestão**

Criar `scripts/validate_ingestion.py` que submete a URL de um repositório pequeno e público via `POST /repos`, aguarda a ingestão via polling em `GET /repos/{id}` e valida:
- `status` chegou a `"ready"`
- Existem registros na tabela `chunks` para o repositório
- Os embeddings têm a dimensão esperada (ex: 1536 para `text-embedding-3-small`)

---

### Epic 4 — RAG Engine e Chat

**[*] Card 4.1 — Use Case `ChatWithRepository`**

Criar `application/use_cases/chat_with_repository.py`. Este Use Case recebe um `ChatRequestDTO` (com `repo_id` e `question`) e orquestra:
1. Valida que o repositório existe e está com `status = "ready"` via `RepositoryStore`
2. Gera embedding da pergunta via `EmbeddingProvider`
3. Busca top-K chunks similares via `VectorStore`
4. Monta o prompt com instrução de sistema + chunks como contexto + pergunta
5. Chama o LLM via `LLMProvider`
6. Retorna `ChatResponseDTO` com `answer` e `sources` (lista de `file_path` dos chunks usados)

O chat é **stateless**: cada requisição é independente, sem histórico persistido.

**[*] Card 4.2 — `OpenAILLMProvider`**

Criar `infrastructure/llm/openai_llm_provider.py` implementando o contrato `LLMProvider`. Chamar a OpenAI Chat Completions API com o modelo configurado via `LLM_MODEL`. O método `complete` recebe o prompt já montado pelo Use Case e retorna o texto da resposta.

**[*] Card 4.3 — Endpoint de Chat**

Implementar schemas Pydantic em `presentation/api/schemas/chat_schemas.py` e o endpoint em `presentation/api/routes/chat.py`:
- `POST /chat`: recebe `{ "repo_id": "uuid", "question": "..." }`, converte para `ChatRequestDTO`, chama `ChatWithRepository` e retorna `{ "answer": "...", "sources": ["path/to/file.py", ...] }`.

**[*] Card 4.4 — Script de Validação do Chat**

Criar `scripts/validate_chat.py` que, após ingestão bem-sucedida de um repositório, faz 3 perguntas ao endpoint `POST /chat` e valida:
- Respostas não estão vazias
- Campo `sources` contém ao menos um arquivo
- Latência de cada chamada é registrada

---

### Epic 5 — Frontend React

**[*] Card 5.1 — Setup do Frontend**

Criar a aplicação React em `frontend/` usando Vite + TypeScript. Configurar proxy no `vite.config.ts` apontando `/api` para o backend FastAPI. Adicionar ao `docker-compose.yml` o serviço `frontend` rodando `npm run dev`. O app deve renderizar um título e confirmar conexão com o backend via `GET /health`.

**[*] Card 5.2 — Tela de Submissão de Repositório**

Criar a tela inicial com campo de texto para URL do GitHub e botão "Analisar". Ao submeter, chamar `POST /repos` e exibir status via polling em `GET /repos/{id}` com feedback visual: `"Aguardando..."`, `"Indexando..."` e `"Pronto ✓"`. Ao atingir `"ready"`, navegar para a tela de chat com o `repo_id`.

**[*] Card 5.3 — Tela de Chat**

Criar a interface de chat: histórico de mensagens (usuário à direita, assistente à esquerda), campo de input com envio por Enter ou botão "Enviar", loading state enquanto aguarda resposta. Exibir abaixo de cada resposta a lista de arquivos-fonte (`sources`) como chips ou lista colapsável.

**[*] Card 5.4 — UX e Feedbacks Visuais**

Adicionar tratamento de erros com mensagens claras (ex: `"URL inválida"`, `"Repositório não encontrado"`, `"Erro ao conectar com o servidor"`). Garantir que a interface seja responsiva. Aplicar tema limpo e minimalista.

---

### Epic 6 — Validação End-to-End e Documentação

**[*] Card 6.1 — Fluxo Completo Ponta-a-Ponta**

Criar `scripts/validate_e2e.py` que executa o fluxo completo:
1. Submeter URL de repositório público via `POST /repos`
2. Aguardar ingestão completar (`status = "ready"`)
3. Fazer 3 perguntas ao `POST /chat`
4. Validar que todas as respostas contêm `answer` e `sources`
5. Imprimir relatório `PASS/FAIL` por etapa

**[*] Card 6.2 — Documentação Final de Setup**

Atualizar o README com a seção de **Setup** e **Executar**: pré-requisitos (Docker, chave da OpenAI), instruções para `.env`, comandos para subir (`docker compose up --build`) e validar (`curl /health`).

---

## 🔮 Fase 2 — Funcionalidades Avançadas (Backlog)

> Cards planejados para após a conclusão da Fase 1. Não fazem parte do MVP.

| Card | Descrição |
|---|---|
| **F2-1** | **Redis + Celery (TaskDispatcher)** — substituir `AsyncioTaskDispatcher` por `CeleryTaskDispatcher` implementando o mesmo contrato `TaskDispatcher`. Nenhum Use Case ou rota precisará mudar — apenas a implementação registrada em `dependencies.py` e a configuração do Docker Compose |
| **F2-2** | **Histórico de Conversas** — criar entidade `Conversation` no domínio, persistir mensagens e respostas, e permitir retomar conversas anteriores. O chat deixa de ser stateless |
| **F2-3** | **Tool Calling com LLM** — permitir que o LLM chame ferramentas (ex: buscar um arquivo específico, listar módulos do repo) em vez de depender apenas do RAG passivo |
| **F2-4** | **Rastreabilidade de Respostas** — exibir na UI os trechos exatos de código que embasaram cada resposta, com destaque visual e link para o arquivo no GitHub |
| **F2-5** | **Análise de Dependências** — Use Case `AnalyzeRepository`: gerar mapa de dependências entre módulos (imports, chamadas entre serviços) e expô-lo na UI |
| **F2-6** | **Análise de Impacto de Alterações** — Use Case `AnalyzeCodeImpact`: dado um arquivo ou função, identificar quais outras partes do sistema seriam impactadas por uma mudança |
| **F2-7** | **Cache de Embeddings** — evitar re-embedding de arquivos que não mudaram entre re-ingestões do mesmo repositório, usando hash do conteúdo como chave de cache |
| **F2-8** | **Suporte a Repositórios Privados** — autenticação com GitHub OAuth para acessar repos privados do usuário autenticado |
