# 🔄 Workflow Engine / Saga Orchestrator

## 📖 Descrição

Este projeto implementa um **Workflow Engine** responsável por orquestrar processos distribuídos que envolvem múltiplos serviços e etapas dependentes entre si. A proposta é simular um fluxo de negócio de longa duração no qual cada etapa pode executar de forma independente, possuir diferentes estados e depender do sucesso ou falha de etapas anteriores.

O projeto explora o padrão **Saga** com **orquestração centralizada**, lidando com **retries, timeouts, idempotência, falhas parciais e ações de compensação** — permitindo que um processo distribuído avance, falhe ou seja revertido de forma controlada, mesmo com serviços que possuem suas próprias transações e estados.

---

## 🎯 Objetivos do Projeto

- Implementar o padrão **Saga com Orquestrador Central** — controle explícito do fluxo, em contraste com Coreografia
- Modelar e persistir o **ciclo de vida completo da Saga** no banco, com histórico de steps e audit trail de eventos
- Implementar **transações compensatórias** que desfazem etapas já concluídas em caso de falha posterior
- Dominar o modelo **command/reply** sobre RabbitMQ como comunicação assíncrona entre orquestrador e serviços
- Implementar **retry com backoff exponencial** e **timeout configurável** por step, com compensação automática
- Garantir **idempotência** ponta-a-ponta: o mesmo comando reenviado não gera efeitos colaterais adicionais
- Demonstrar **recovery após falha**: retomar Sagas em andamento após restart do orquestrador
- Expor **API de observabilidade** com status, histórico de steps e audit trail de qualquer Saga

---

## 🧩 Domínio

O domínio simulado é o **processamento de um pedido de e-commerce**. Ao criar um pedido, o sistema dispara uma Saga que orquestra quatro etapas sequenciais, cada uma delegada a um serviço independente (todos **mockados**).

### Fluxo: `ProcessarPedido`

| # | Step | Serviço | Comando | Compensação |
|---|------|---------|---------|-------------|
| 1 | Reservar Estoque | `inventory` | `ReservarEstoque` | `LiberarEstoque` |
| 2 | Processar Pagamento | `payment` | `ProcessarPagamento` | `EstornarPagamento` |
| 3 | Despachar Pedido | `shipping` | `DespacharPedido` | `CancelarDespacho` |
| 4 | Notificar Cliente | `notification` | `NotificarCliente` | *(sem compensação)* |

> `NotificarCliente` é **fire-and-forget**: notificações já enviadas não são desfeitas — uma nova notificação de cancelamento é emitida ao final do rollback.

### Regras de Falha Determinísticas (Mocks)

| Cenário | Condição | Serviço | Comportamento |
|---------|----------|---------|---------------|
| ✅ Happy Path | `total_amount <= 9999.99` sem SKUs especiais | Todos | Sucesso em todos os steps |
| 💳 Pagamento Recusado | `total_amount > 9999.99` | `payment` | Falha → compensa Step 1 |
| 📦 Estoque Indisponível | `sku` contendo `"ESGOTADO"` | `inventory` | Falha Step 1 → Saga FAILED |
| ⏱️ Timeout de Despacho | `order_id` terminando em `"88"` | `shipping` | Sem reply → timeout do orquestrador |
| 🔁 Falha Transitória | `order_id` terminando em `"77"` | `payment` | Falha nas 2 primeiras tentativas; sucesso na 3ª |
| 💥 Falha na Compensação | `order_id` terminando em `"66"` | `inventory` | Compensação `LiberarEstoque` falha → DLQ |

---

## 🏗️ Arquitetura

### Fluxo Happy Path

```
                          FLUXO HAPPY PATH
  ─────────────────────────────────────────────────────────────────

  POST /sagas ──────────────────────────────────► Saga STARTED
       │
       │  ┌──────────────────────────────────────────────────────┐
       │  │  Step 1 · ReservarEstoque                            │
       ├──┤  saga.commands ──► inventory.commands                │
       │  │                             reply: OK ✅  → avança   │
       │  │                        reply: FALHA ❌ → Saga FAILED  │
       │  └──────────────────────────────────────────────────────┘
       │
       │  ┌──────────────────────────────────────────────────────┐
       │  │  Step 2 · ProcessarPagamento                         │
       ├──┤  saga.commands ──► payment.commands                  │
       │  │                             reply: OK ✅  → avança   │
       │  │             reply: FALHA ❌ → ↩️ compensa Step 1     │
       │  └──────────────────────────────────────────────────────┘
       │
       │  ┌──────────────────────────────────────────────────────┐
       │  │  Step 3 · DespacharPedido                            │
       ├──┤  saga.commands ──► shipping.commands                 │
       │  │                             reply: OK ✅  → avança   │
       │  │         reply: FALHA ❌ → ↩️ compensa Steps 1 e 2   │
       │  └──────────────────────────────────────────────────────┘
       │
       │  ┌──────────────────────────────────────────────────────┐
       │  │  Step 4 · NotificarCliente                           │
       └──┤  saga.commands ──► notification.commands             │
          │                             reply: OK ✅  → conclui  │
          └──────────────────────────────────────────────────────┘
               │
               ▼
         Saga COMPLETED ✅
```

### Comunicação Orquestrador ↔ Serviços via RabbitMQ

```
  Cliente        Orchestrator      PostgreSQL       RabbitMQ       Serviço
     │                │                │               │               │
     │  POST /sagas   │                │               │               │
     ├───────────────►│                │               │               │
     │                │ INSERT saga    │               │               │
     │                ├───────────────►│               │               │
     │                │ INSERT step    │               │               │
     │                ├───────────────►│               │               │
     │  202 Accepted  │                │               │               │
     │◄───────────────┤                │               │               │
     │                │                │  publish cmd  │               │
     │                ├───────────────────────────────►│               │
     │                │                │               │  deliver cmd  │
     │                │                │               ├──────────────►│
     │                │                │               │               │ · processa
     │                │                │               │               │ · aplica mock
     │                │                │               │  reply: OK    │
     │                │                │               │◄──────────────┤
     │                │ consume reply  │               │               │
     │                │◄───────────────────────────────┤               │
     │                │ UPDATE step    │               │               │
     │                ├───────────────►│               │               │
     │                │    (repete para cada step...)  │               │
     │                │ UPDATE saga    │               │               │
     │                ├───────────────►│               │               │
     │ GET /sagas/{id}│                │               │               │
     ├───────────────►│                │               │               │
     │   {COMPLETED}  │                │               │               │
     │◄───────────────┤                │               │               │
```

### Fluxo de Compensação

```
                    FLUXO DE COMPENSAÇÃO
  ─────────────────────────────────────────────────────────────────

  EXECUÇÃO (ordem normal ──►)

    Step 1                 Step 2                 Step 3
    ReservarEstoque   ──►  ProcessarPagamento ──►  DespacharPedido
    ───────────────        ──────────────────      ───────────────
    COMPLETED ✅           COMPLETED ✅             FAILED ❌
                                                          │
                                                 falha detectada
                                                          │
                                                          ▼
  COMPENSAÇÃO (ordem inversa ◄──)

    Step 2                            Step 1
    EstornarPagamento        ◄──      LiberarEstoque
    ─────────────────                ──────────────
    COMPENSATED ↩️                    COMPENSATED ↩️

                           Saga COMPENSATED ❌
```

### Por que RabbitMQ e não Kafka?

O padrão Saga Orchestration é baseado em **command/reply**: o orquestrador envia um comando e aguarda resposta correlacionada. Esse modelo é nativamente suportado pelo RabbitMQ via direct exchange, routing keys e correlation_id — sem partições, offsets ou consumer groups. O Kafka foi explorado no [Projeto 05](../05-event-streaming-platform/) e brilha em event streaming/coreografia; para orquestração centralizada o overhead não agrega valor.

---

## 🛠️ Stack

| Componente | Tecnologia |
|------------|------------|
| Orquestrador (API + Engine) | Python 3.12 + FastAPI |
| Serviços Mockados | Python 3.12 (workers via `aio_pika`) |
| Mensageria | RabbitMQ 3 (management plugin) |
| Banco de Dados | PostgreSQL 16 (SQLAlchemy + Alembic) |
| Lock Distribuído | Redis 7 |
| Infra | Docker Compose + Makefile |

---

## 📁 Estrutura do Projeto

```
09-saga-orchestrator/
├── orchestrator/
│   ├── app/
│   │   ├── api/routers/
│   │   │   ├── sagas.py         # POST /sagas, GET /sagas, GET /sagas/{id}/timeline
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── engine.py        # SagaEngine — coordena execução e compensação
│   │   │   ├── state_machine.py # Transições de estado por step e por Saga
│   │   │   └── workflow.py      # Definição declarativa do fluxo (steps + compensações)
│   │   ├── messaging/
│   │   │   ├── publisher.py     # Publica comandos → {service}.commands
│   │   │   └── consumer.py      # Consome replies ← saga.replies (asyncio task)
│   │   ├── models/saga.py       # Saga, SagaStep, SagaEvent (SQLAlchemy)
│   │   ├── repositories/saga_repository.py
│   │   ├── schemas/saga.py
│   │   ├── config.py
│   │   └── main.py              # FastAPI app + lifespan (inicia consumer)
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── services/
│   ├── inventory/worker.py
│   ├── payment/worker.py
│   ├── shipping/worker.py
│   └── notification/worker.py
├── scripts/
│   ├── verify_happy_path.py
│   ├── verify_compensation.py
│   ├── verify_retry.py
│   ├── verify_idempotency.py
│   ├── verify_timeout.py
│   └── stress_test.py
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 🚀 Como Executar

```bash
make up          # sobe todos os containers
make migrate     # executa migrations do Alembic
make health      # verifica saúde dos serviços
make verify-happy  # valida o happy path completo
make stress      # stress test de throughput
```

| Serviço | Porta |
|---------|-------|
| Orchestrator API | `8090` |
| RabbitMQ Management | `15672` |
| PostgreSQL | `5490` |
| Redis | `6490` |

---

## 📋 Epics e Cards

### Epic 1 — Setup Base: Infraestrutura, Serviços Mockados e Topologia RabbitMQ

**[OK] Card 1.1 — Estrutura de Pastas e Docker Compose**

Criar o `docker-compose.yml` com todos os serviços: `orchestrator`, `inventory`, `payment`, `shipping`, `notification`, `rabbitmq`, `postgres` e `redis`. Usar `depends_on` com `condition: service_healthy` para que os workers só subam após a infraestrutura estar pronta.

**[ ] Card 1.2 — Workers dos Serviços Mockados**

Implementar os quatro workers Python que consomem sua fila de comandos (ex: `inventory.commands`), aplicam as regras de falha determinísticas e publicam a reply em `saga.replies`. Cada worker trata tanto comandos de execução quanto de compensação na mesma fila, distinguidos pelo campo `command_type`.

**[ ] Card 1.3 — Regras de Falha Determinísticas**

Isolar a lógica de mock em uma função pura `apply_business_rules(command_type, payload, attempt) -> (success, result, error)` em cada worker. O campo `attempt` no payload permite que o cenário `"77"` (falha transitória) saiba em qual tentativa está e retorne sucesso apenas na 3ª.

**[ ] Card 1.4 — Topologia RabbitMQ**

Declarar exchanges, filas e bindings no startup: exchange `saga.commands` (direct) roteando para filas por serviço, fila `saga.replies` para o orquestrador consumir, e DLX `saga.dlx` → DLQ `saga.dlq` configurados via `x-dead-letter-exchange` em cada fila de comando. A declaração deve ser idempotente para suportar restarts.

**[ ] Card 1.5 — API HTTP do Orquestrador**

Implementar os endpoints `POST /sagas`, `GET /sagas`, `GET /sagas/{id}` e `GET /sagas/{id}/timeline`. O `POST /sagas` valida o payload, persiste a Saga no Postgres e dispara o primeiro step de forma assíncrona, retornando `202 Accepted` com o `saga_id`.

---

### Epic 2 — Modelagem da State Machine e Persistência

**[ ] Card 2.1 — Schema do Banco de Dados**

Criar três modelos SQLAlchemy: `Saga` (instância do workflow com status e payload), `SagaStep` (cada etapa com `command_id` único para idempotência, `attempts` e timestamps) e `SagaEvent` (audit trail append-only — nunca atualizado, apenas inserido). Gerar migrations com Alembic.

**[ ] Card 2.2 — Definição Declarativa do Workflow**

Implementar `workflow.py` com uma lista de `StepDefinition` descrevendo serviço, `command_type`, `compensation_command`, `timeout_seconds` e `max_attempts` de cada step. Essa separação torna o engine genérico — ele não conhece os steps específicos, apenas executa a sequência definida.

**[ ] Card 2.3 — State Machine: Transições de Estado**

Implementar `state_machine.py` com as transições válidas para `Saga` e `SagaStep`, lançando `InvalidTransitionError` em transições ilegais. A state machine deve ser testável isoladamente, sem dependência de banco ou RabbitMQ.

**[ ] Card 2.4 — SagaEngine: Motor de Execução**

Implementar `engine.py` com os métodos `start_saga`, `handle_reply`, `start_compensation` e `handle_timeout`. O Engine é o único componente que conhece o estado atual da Saga e decide o próximo passo — toda ação registra um `SagaEvent` no banco para rastreabilidade completa.

---

### Epic 3 — Happy Path End-to-End

**[ ] Card 3.1 — Publicação de Comandos**

Implementar `publisher.py` que serializa o comando (`command_id`, `command_type`, `saga_id`, `attempt`, `payload`) e publica no exchange `saga.commands` com routing key igual ao nome do serviço. O `command_id` é gerado pelo Engine e persistido no `SagaStep` antes da publicação.

**[ ] Card 3.2 — Consumer de Replies como AsyncIO Task**

Implementar `consumer.py` como asyncio task iniciada no `lifespan` do FastAPI, consumindo `saga.replies` em loop contínuo. Faz `ack` apenas após `engine.handle_reply` concluir com sucesso — em caso de exceção, faz `nack` com `requeue=False` para a mensagem ir para a DLQ.

**[ ] Card 3.3 — Fluxo Happy Path Completo**

Integrar Engine + Publisher + Consumer para que `POST /sagas` desencadeie o fluxo completo até `Saga COMPLETED`. Validar que todos os `SagaEvent`s foram registrados, o `current_step_index` foi atualizado a cada transição e o `GET /sagas/{id}` reflete o estado correto.

**[ ] Card 3.4 — Script de Validação do Happy Path**

Criar `verify_happy_path.py` que cria uma Saga, faz polling até `COMPLETED` (timeout 30s) e valida que todos os 4 steps estão `COMPLETED` com o número correto de eventos no timeline.

---

### Epic 4 — Compensating Transactions (Rollback Distribuído)

**[ ] Card 4.1 — Lógica de Compensação no SagaEngine**

Implementar `start_compensation` no Engine: filtrar steps `COMPLETED` em ordem decrescente de `step_index` e publicar seus comandos de compensação. A Saga transiciona para `COMPENSATING` ao iniciar e para `COMPENSATED` quando todos os steps atingirem `COMPENSATED`.

**[ ] Card 4.2 — Compensações nos Workers**

Implementar nos workers os handlers para `LiberarEstoque`, `EstornarPagamento` e `CancelarDespacho`, tratados na mesma fila de comandos e distinguidos por `command_type`. Steps que nunca completaram (ex: o step que falhou) não recebem compensação.

**[ ] Card 4.3 — Script de Validação de Compensação**

Criar `verify_compensation.py` que cria uma Saga com `total_amount > 9999.99` e valida que o Step 1 termina `COMPENSATED`, o Step 2 termina `FAILED`, a Saga atinge `COMPENSATED` e o timeline contém os eventos de rollback na ordem correta.

**[ ] Card 4.4 — Retry na Compensação e Falha Irrecuperável**

Garantir que compensações também possuem retry com `max_attempts` próprio. Se esgotadas, o step fica em `COMPENSATING_FAILED` e a Saga em `FAILED` — estado que exige intervenção manual. Validar com `order_id` terminando em `"66"` e confirmar mensagem na `saga.dlq`.

---

### Epic 5 — Retries e Timeouts

**[ ] Card 5.1 — Retry com Backoff Exponencial**

Quando `handle_reply` recebe falha com tentativas restantes: incrementar `attempts`, calcular `delay = base_delay * 2^(attempts-1)` com jitter de ±10% e agendar re-publicação via `asyncio.create_task`. Um novo `command_id` é gerado por tentativa; o campo `attempt` no payload informa ao mock em qual tentativa está.

**[ ] Card 5.2 — Timeout Configurável por Step**

Ao publicar um comando, criar uma `asyncio.Task` que aguarda `timeout_seconds` e chama `handle_timeout`. Quando a reply chega, a task é cancelada via `task.cancel()`. O `handle_timeout` verifica se o step ainda está `RUNNING` antes de agir e registra o evento `StepTimeout` no audit trail.

**[ ] Card 5.3 — Script de Validação de Timeout**

Criar `verify_timeout.py` para o cenário de timeout no shipping (`order_id` terminando em `"88"`): aguardar o timeout disparar, verificar o evento `StepTimeout` no timeline e confirmar que a Saga termina `COMPENSATED` com os steps anteriores compensados.

**[ ] Card 5.4 — Configuração por Variáveis de Ambiente**

Expor `STEP_TIMEOUT_SECONDS`, `STEP_MAX_ATTEMPTS` e `RETRY_BASE_DELAY_SECONDS` via env vars com defaults razoáveis. Incluir valores acelerados no `docker-compose.yml` (ex: `STEP_TIMEOUT_SECONDS=5`) para que os scripts de verificação rodem em segundos, não minutos.

---

### Epic 6 — Idempotência

**[ ] Card 6.1 — Idempotency Key nos Comandos**

O `command_id` (UUID v4) é a idempotency key de cada tentativa: gerado pelo Engine, persistido no `SagaStep.command_id` (coluna UNIQUE), enviado no payload e retornado intacto no reply. Em retry, um novo `command_id` é gerado — cada tentativa é semanticamente uma nova requisição ao serviço.

**[ ] Card 6.2 — Serviços Mockados Idempotentes**

Cada worker mantém um dicionário `{command_id: reply_payload}`. Se um `command_id` já visto chegar, retornar o resultado anterior sem re-executar a lógica de negócio. Simula o comportamento de serviços reais (ex: gateways de pagamento com idempotency-key).

**[ ] Card 6.3 — Proteção contra Replies Duplicadas**

O `handle_reply` deve verificar, dentro de uma transação com `SELECT FOR UPDATE`, se o `SagaStep` já está em status terminal antes de processar. Se sim, fazer `ack` e ignorar — evitando race conditions em cenários de múltiplas instâncias do orquestrador rodando em paralelo.

**[ ] Card 6.4 — Script de Validação de Idempotência**

Criar `verify_idempotency.py` que, após o Step 1 completar, re-publica manualmente sua reply em `saga.replies` e verifica que a Saga progride normalmente sem processar o Step 1 uma segunda vez — confirmando nos logs a mensagem de "duplicate reply ignored".

---

### Epic 7 — Observabilidade do Workflow

**[ ] Card 7.1 — Endpoint de Status da Saga**

`GET /sagas/{saga_id}` retorna status, `current_step`, timestamps, `duration_ms` e a lista de steps com status individual, número de tentativas e duração. Permite acompanhar o progresso em tempo real.

**[ ] Card 7.2 — Endpoint de Timeline / Audit Trail**

`GET /sagas/{saga_id}/timeline` retorna todos os `SagaEvent`s em ordem cronológica com `event_type`, `step` e `payload`. O audit trail é a "caixa-preta" do workflow: permite reconstruir exatamente o que aconteceu e quando — essencial para debugging e suporte.

**[ ] Card 7.3 — Listagem e Filtros de Sagas**

`GET /sagas` com filtros por `status`, `order_id`, `from_date`/`to_date` e paginação via `limit`/`offset`. Retorna lista resumida (sem steps e events) para não sobrecarregar a resposta em listagens.

**[ ] Card 7.4 — Logs Estruturados com Contexto da Saga**

Configurar o logger para emitir JSON com `saga_id`, `step_name`, `command_id` e `attempt` em todos os logs de execução. Usar `contextvars.ContextVar` para propagar o contexto sem poluir as assinaturas de função.

---

### Epic 8 — Cenários Avançados e Stress Test

**[ ] Card 8.1 — Script de Cenários Determinísticos Completos**

Criar `verify_all_scenarios.py` que executa os 6 cenários da tabela de falhas em sequência e imprime um relatório `PASSED/FAILED` consolidado para cada um.

**[ ] Card 8.2 — Recovery após Falha do Orquestrador**

No `lifespan`, o orquestrador faz scan no banco por Sagas com steps em `RUNNING` há mais de N segundos e re-publica seus comandos. Validar: derrubar o container no meio de uma Saga, reiniciar e confirmar que ela conclui normalmente graças à idempotência do `command_id`.

**[ ] Card 8.3 — Sagas Concorrentes em Paralelo**

Disparar 20 Sagas em paralelo via `asyncio.gather` e validar que todas chegam ao status final esperado sem interferência entre elas. O Redis é usado como lock distribuído (`SET NX EX`) no `handle_reply` para evitar race conditions em scale-out do orquestrador.

**[ ] Card 8.4 — Stress Test de Throughput**

Criar `stress_test.py` que dispara N Sagas (default 100), mede throughput (Sagas/s) e latência P50/P95/P99 de ponta a ponta, e valida que 0 Sagas ficam travadas sem status final.

---

## 📚 Lessons Learned

*(a preencher ao longo da implementação)*