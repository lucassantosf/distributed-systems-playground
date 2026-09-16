# Distributed Systems Playground

Um conjunto de projetos práticos para explorar conceitos de arquitetura de software e sistemas distribuídos.

Cada projeto aborda um tema diferente de forma incremental — da teoria à implementação, com stacks realistas e cenários próximos do que se vê em produção.

---

## Projetos

### 01 — Event-Driven Orders
API de pedidos orientada a eventos com **FastAPI**, **PostgreSQL** e **RabbitMQ**.

Workers desacoplados consomem eventos de pedidos para notificação, faturamento e e-mail. Explora retries, Dead Letter Queue (DLQ), idempotência, logs estruturados e correlation IDs.

---

### 02 — Realtime Chat
Chat em tempo real com **React**, **FastAPI**, **WebSocket**, **PostgreSQL** e **Redis Pub/Sub**.

Cada mensagem percorre o caminho: WebSocket → persistência no banco → publicação no Redis → broadcast para todos na sala. Explora salas isoladas, presença online, reconexão automática e heartbeat. Integra com a plataforma de observabilidade do projeto 06.

---

### 03 — gRPC Microservice
Três microsserviços independentes (User, Product, Order) que se comunicam via **gRPC** e **Protocol Buffers**.

Cada serviço tem seu próprio banco PostgreSQL e se isola em redes Docker separadas. Explora contratos tipados, interceptors, retry com backoff exponencial, propagação de request-id entre serviços e logs estruturados.

---

### 04 — CQRS E-commerce
Separação de escrita e leitura aplicada a um e-commerce, usando **Command API** (PostgreSQL), **RabbitMQ**, **Projection Worker** e **Query API** (Redis como Read Model).

A escrita acontece no banco transacional; os eventos propagam as mudanças; o worker projeta um modelo de leitura otimizado no Redis. Explora consistência eventual, campos derivados, DLQ, retry com backoff e reconciliação do Read Model.

---

### 05 — Event Streaming Platform
Plataforma de streaming de eventos com **Apache Kafka**.

Um Producer API publica eventos de pedidos; múltiplos consumidores independentes (notificação, faturamento, analytics, estoque) processam o mesmo fluxo sem acoplamento. Explora Topics, Partitions, Message Keys, Consumer Groups, Offsets, Replay, Retention, Retry Topics e Dead Letter Topics.

---

### 06 — Observability
Plataforma central de observabilidade com os três pilares — **Métricas**, **Logs** e **Traces** — construída para ser reutilizada pelos outros projetos.

- **Métricas:** Prometheus + Thanos + Alertmanager
- **Logs:** Filebeat → Logstash → OpenSearch
- **Traces:** OpenTelemetry SDK → OTel Collector → Grafana Tempo
- **Visualização:** Grafana com data links entre os três sinais

---

## Fio condutor

Os projetos não são isolados. Um mesmo domínio (pedidos / e-commerce) reaparece em vários deles, e alguns se integram diretamente — o chat (02) e o Kafka (05) se conectam à plataforma de observabilidade (06); o CQRS (04) evolui naturalmente a partir dos eventos do projeto 01; o projeto 05 retoma o mesmo cenário de pedidos com uma infraestrutura de streaming mais robusta.

A ideia é que cada projeto ensine um conceito novo sem jogar fora o que veio antes.

