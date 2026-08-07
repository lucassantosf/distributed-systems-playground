# 05 - Event Streaming Platform

## 📖 Descrição

O **Event Streaming Platform** é um projeto focado na construção de uma plataforma distribuída para publicação, armazenamento e processamento contínuo de eventos utilizando **Apache Kafka**. Diferentemente de um broker tradicional de mensageria, o objetivo deste projeto é tratar os eventos como um fluxo contínuo de informações (Event Stream), permitindo que múltiplos serviços consumam o mesmo histórico de forma independente.

Ao longo do desenvolvimento serão implementados produtores responsáveis por publicar eventos do domínio de pedidos (e-commerce), enquanto diversos consumidores processam essas informações sem qualquer acoplamento entre si. Cada consumidor poderá iniciar sua execução em momentos diferentes, reprocessar eventos antigos, escalar horizontalmente através de Consumer Groups e controlar sua posição de leitura utilizando Offsets.

Para dar contexto real à trilha, a plataforma reutiliza o cenário de pedidos do projeto 01 (Event-Driven Orders): o producer-api persiste o pedido no PostgreSQL e publica o evento (ex.: `OrderCreated`), enquanto os consumidores de notificação, faturamento e analytics processam o mesmo fluxo de forma independente.

O projeto também explora conceitos fundamentais do ecossistema Kafka, como organização de eventos em Topics, distribuição utilizando Partitions, ordenação através de Message Keys, políticas de Retention, Replay de eventos históricos, Retry, Dead Letter Topics (DLT) e monitoramento utilizando Kafka UI.

Ao final, a aplicação representará uma plataforma de Event Streaming capaz de distribuir eventos para múltiplos consumidores independentes, simulando arquiteturas modernas utilizadas em sistemas distribuídos de grande escala.

---

## 🚀 Stack

- **FastAPI** — APIs responsáveis pela publicação contínua de eventos na plataforma.
- **Apache Kafka** — Plataforma de Event Streaming utilizada para armazenamento e distribuição dos eventos.
- **PostgreSQL** — Persistência de dados utilizados pelos produtores e consumidores quando necessário.
- **Docker & Docker Compose** — Orquestração de toda a infraestrutura local.
- **Kafka UI** — Visualização de Topics, Partitions, Consumer Groups, Offsets e mensagens publicadas.

---

## 🎯 Objetivos do Projeto

- Construir uma plataforma baseada em Event Streaming.
- Publicar eventos continuamente utilizando Producers.
- Persistir pedidos e resultados de processamento no PostgreSQL (SQLAlchemy + Alembic).
- Organizar eventos através de múltiplos Topics.
- Distribuir processamento utilizando Partitions.
- Garantir ordenação utilizando Message Keys.
- Escalar consumidores através de Consumer Groups.
- Explorar controle de leitura utilizando Offsets.
- Reprocessar eventos históricos utilizando Replay.
- Configurar políticas de Retention.
- Implementar Retry e Dead Letter Topics.
- Monitorar o ecossistema utilizando Kafka UI.
- Compreender as diferenças arquiteturais entre Kafka e brokers tradicionais de mensageria.

## 🧩 Domínio da Plataforma

Para dar contexto real aos conceitos abordados, a plataforma adota o domínio de **e-commerce / pedidos**, reutilizando o cenário do projeto 01 (Event-Driven Orders).

* **Eventos:** ciclo de vida do pedido (ex.: `OrderCreated`, `OrderUpdated`), definidos na camada `shared/events`.
* **Message Key:** `order_id` — garante que eventos do mesmo pedido sejam gravados em uma única partição, preservando a ordenação.
* **Topics (sugestão inicial):** `orders.created` (e demais eventos do ciclo), com tópicos `-retry` e `-dlt` correspondentes nas etapas de tratamento de falhas.
* **Persistência:** o producer-api persiste o pedido no PostgreSQL antes de publicar (SQLAlchemy + Alembic); cada consumidor pode persistir seus próprios resultados (ex.: fatura no billing, métricas no analytics).
* **Consumidores ativos:** além de consumir, o inventory-consumer reserva estoque e publica eventos derivados (ex.: `InventoryReserved`), demonstrando que um consumidor também pode ser produtor.

**Envelope padrão dos eventos** (referência de contrato — implementação no Card 4):

```json
{
  "event_id": "uuid do evento",
  "event_type": "OrderCreated",
  "occurred_at": "timestamp ISO 8601",
  "correlation_id": "id de correlação da requisição",
  "order_id": "id do pedido, mesmo valor usado como Message Key",
  "payload": {}
}
```

A Message Key (`order_id`) é definida no registro Kafka, separada do corpo do evento. Como todos os eventos de um mesmo pedido usam a mesma chave, eles caem na mesma partição e são processados em ordem.

---

# Estrutura Sugerida do Projeto — Event Streaming Platform

A estrutura abaixo representa uma sugestão simples e organizada para o projeto **05 - Event Streaming Platform**, separando claramente produtores, consumidores, infraestrutura e componentes compartilhados. O objetivo é facilitar a evolução incremental da plataforma sem adicionar complexidade desnecessária.

```text
05-event-streaming-platform/
│
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── producer-api/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── kafka/
│   │   ├── models/
│   │   └── main.py
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
│
├── consumers/
│   ├── notification-consumer/
│   │   ├── app/
│   │   │   ├── kafka/
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── billing-consumer/
│   │   ├── app/
│   │   │   ├── kafka/
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── analytics-consumer/
│   │   ├── app/
│   │   │   ├── kafka/
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── inventory-consumer/
│   │   ├── app/
│   │   │   ├── kafka/
│   │   │   ├── services/
│   │   │   ├── models/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│
├── shared/
│   ├── events/
│   ├── schemas/
│   ├── kafka/
│   └── utils/
│
├── infrastructure/
│   ├── kafka/
│   ├── postgres/
│   └── monitoring/
│
└── scripts/
    ├── create-topics.sh
    ├── produce-sample-events.py
    └── reset-consumer-offsets.sh
```

---

# Descrição dos Componentes

## producer-api/

Responsável por receber requisições HTTP e publicar eventos no Apache Kafka. Essa camada representa os **produtores da plataforma**, transformando ações do sistema em eventos distribuídos.

### Principais responsabilidades

* Expor endpoints REST com FastAPI.
* Validar payloads recebidos.
* Persistir pedidos no PostgreSQL (SQLAlchemy + Alembic, mesmo padrão do projeto 01).
* Publicar eventos nos tópicos Kafka corretos após a persistência.
* Registrar logs de publicação.

---

## consumers/

Contém todos os consumidores independentes da plataforma. Cada consumidor possui sua própria aplicação e pode evoluir separadamente.

### notification-consumer/

Simula envio de notificações a partir dos eventos de pedidos consumidos, registrando as notificações enviadas.

### billing-consumer/

Simula processamento financeiro e faturamento, persistindo as faturas geradas a partir dos pedidos.

### analytics-consumer/

Simula geração de métricas e indicadores analíticos, persistindo dados agregados dos pedidos.

### inventory-consumer/

Simula reserva de estoque a partir dos pedidos criados. É um consumidor ativo: além de persistir o estado do estoque, publica eventos derivados (ex.: `InventoryReserved`) de volta ao Kafka, demonstrando o padrão de consumidor-que-também-produz.

### Principais responsabilidades

* Consumir eventos continuamente.
* Processar mensagens de forma independente.
* Persistir seus próprios resultados no PostgreSQL quando fizer sentido (ex.: fatura no billing, métricas no analytics).
* Publicar eventos derivados quando o processamento gerar novas consequências (ex.: `InventoryReserved`).
* Implementar retry e tratamento de falhas.

---

## shared/

Camada compartilhada entre produtores e consumidores. Evita duplicação de contratos e regras comuns.

### events/

Definição dos tipos de eventos e estruturas de payload.

### schemas/

Modelos Pydantic utilizados para serialização e validação.

### kafka/

Configurações comuns de Producer e Consumer Kafka.

### utils/

Funções utilitárias compartilhadas (logging, ids, datas, etc.).

---

## infrastructure/

Arquivos relacionados à infraestrutura local do projeto.

### kafka/

Configurações específicas do cluster Kafka e tópicos.

### postgres/

Scripts de inicialização do banco de dados.

### monitoring/

Configurações futuras de observabilidade e métricas.

---

## scripts/

Scripts auxiliares para desenvolvimento e testes da plataforma.

### create-topics.sh

Criação automática dos tópicos Kafka utilizados no projeto.

### produce-sample-events.py

Geração de eventos fictícios para testes de carga e streaming.

### reset-consumer-offsets.sh

Reinicialização dos offsets para testes de replay.

---

# Visão Arquitetural Simplificada

```text
               Producer API
                     │
                     ▼
                Apache Kafka
        ┌───────┼──────┬────────┐
        ▼       ▼      ▼        ▼
 Notification Billing Analytics Inventory
   Consumer  Consumer  Consumer  Consumer
```

* **Producer API** publica eventos continuamente.
* **Kafka** armazena e distribui o stream de eventos.
* **Consumers** processam o mesmo fluxo de forma independente.
* **Inventory Consumer** é um consumidor ativo: reserva estoque e publica eventos derivados de volta ao Kafka.
* Novos consumidores podem ser adicionados sem alterar os produtores.

---

# Observações de Evolução

Essa estrutura foi pensada para crescer naturalmente ao longo dos cards do projeto. Inicialmente você poderá ter apenas um produtor e um consumidor; os demais diretórios podem permanecer vazios até as etapas correspondentes da trilha. Dessa forma o repositório continua simples no início, mas já preparado para evoluir até uma plataforma completa de Event Streaming baseada em Apache Kafka.

Decisões de escopo desta trilha:

* **Domínio:** e-commerce/pedidos, reutilizando o cenário do projeto 01 (Event-Driven Orders).
* **Persistência:** producer-api e consumidores persistem dados no PostgreSQL (SQLAlchemy + Alembic).
* **Testes:** sem testes automatizados — a validação será manual (curl, Kafka UI e scripts auxiliares).

# [*] Epic 1 — Fundação da Plataforma

### [*] Card 1 — Criar estrutura inicial do projeto
**Descrição:** Organizar a estrutura base do projeto separando Producer API, Consumers, componentes compartilhados e arquivos de infraestrutura, preparando um ambiente limpo para evolução incremental da plataforma.

---

### [*] Card 2 — Configurar ambiente Docker
**Descrição:** Configurar Docker Compose contendo Apache Kafka, PostgreSQL e Kafka UI, garantindo a comunicação entre a infraestrutura. As aplicações FastAPI serão adicionadas ao Compose nas etapas em que forem criadas.

---

### [*] Card 3 — Validar infraestrutura Kafka
**Descrição:** Confirmar que todos os containers estão operacionais, validar o cluster através do Kafka UI e garantir que os serviços conseguem se comunicar corretamente.

---

# [*] Epic 2 — Publicação de Eventos

### [*] Card 4 — Definir contratos dos eventos
**Descrição:** Modelar os principais eventos do domínio de pedidos (ex.: `OrderCreated`, `OrderUpdated`) em `shared/events`, seguindo o envelope padrão documentado na seção Domínio da Plataforma e padronizando estrutura, payload e informações compartilhadas entre produtores e consumidores.

---

### [*] Card 5 — Criar Producer API
**Descrição:** Desenvolver uma API responsável por receber requisições HTTP, validar os contratos definidos no Card 4, persistir o pedido no PostgreSQL (SQLAlchemy + Alembic) e publicar o evento correspondente na plataforma Kafka.

---

### [*] Card 6 — Publicar primeiro Event Stream
**Descrição:** Implementar a publicação contínua de eventos de pedidos (ex.: `OrderCreated`) e validar sua chegada aos tópicos utilizando o Kafka UI.

---

# [*] Epic 3 — Organização dos Topics

### [*] Card 7 — Criar Topics por domínio
**Descrição:** Separar eventos em tópicos específicos do domínio de pedidos (ex.: `orders.created`, `orders.updated`), organizando o fluxo e facilitando evolução e manutenção da plataforma.

---

### [*] Card 8 — Direcionar eventos corretamente
**Descrição:** Garantir que cada tipo de evento seja publicado apenas no tópico correspondente ao seu domínio.

---

### [*] Card 9 — Criar e configurar o primeiro consumidor
**Descrição:** Criar o primeiro consumidor do zero — o notification-consumer — conectando-o ao tópico `orders.created`, processando os eventos recebidos e registrando as notificações enviadas. O padrão criado aqui será replicado para os demais consumidores ao longo da trilha.

---

# [*] Epic 4 — Partitions

### [*] Card 10 — Configurar Partitions
**Descrição:** Dividir os tópicos em múltiplas partições (ex.: 3 por tópico) para permitir paralelismo e maior capacidade de processamento.

---

### [*] Card 11 — Implementar Message Keys
**Descrição:** Utilizar `order_id` como Message Key, garantindo que todos os eventos de um mesmo pedido sejam gravados em uma única partição, preservando a ordenação.

---

### [*] Card 12 — Validar distribuição das mensagens
**Descrição:** Acompanhar como o Kafka distribui automaticamente os eventos entre diferentes partições.

---

# [*] Epic 5 — Consumer Groups

### [*] Card 13 — Criar Consumer Groups
**Descrição:** Organizar consumidores em grupos independentes para compartilhar processamento sem duplicar o consumo dos eventos.

---

### [*] Card 14 — Escalar consumidores horizontalmente
**Descrição:** Executar múltiplas instâncias do mesmo consumidor para dividir automaticamente a carga de processamento.

---

### [*] Card 15 — Validar Rebalanceamento
**Descrição:** Observar como o Kafka redistribui partições quando consumidores entram ou deixam um Consumer Group.

---

# [*] Epic 6 — Offsets e Replay

### [*] Card 16 — Explorar funcionamento dos Offsets
**Descrição:** Entender como cada consumidor controla individualmente sua posição de leitura dentro de um tópico.

---

### [*] Card 17 — Reiniciar consumidores
**Descrição:** Reiniciar consumidores preservando ou redefinindo offsets para compreender diferentes estratégias de processamento.

---

### [*] Card 18 — Realizar Replay de eventos
**Descrição:** Reprocessar eventos históricos utilizando offsets anteriores sem necessidade de republicar novas mensagens. O replay é limitado pela janela de retenção configurada no Card 19.

---

# [*] Epic 7 — Retention

### [*] Card 19 — Configurar políticas de Retention
**Descrição:** Definir quanto tempo os eventos permanecerão armazenados antes de serem removidos automaticamente. Essa janela delimita até onde é possível realizar Replay (Card 18).

---

### [*] Card 20 — Criar consumidores tardios
**Descrição:** Demonstrar que novos consumidores conseguem processar eventos publicados antes da sua inicialização. Exemplo mental: eventos de pedidos são publicados desde as 09:00; ao iniciar o analytics às 10:00, ele lê o histórico completo a partir das 09:00 — não apenas o que chegar a partir daí.

---

### [*] Card 21 — Validar Event Streaming
**Descrição:** Comprovar que eventos permanecem disponíveis durante o período de retenção para diferentes consumidores.

---

# [*] Epic 8 — Tratamento de Falhas

### [*] Card 22 — Implementar Retry
**Descrição:** Reprocessar automaticamente eventos que apresentarem falhas temporárias durante sua execução, utilizando retry topics com backoff no consumidor (ex.: `orders.created-retry`).

---

### [*] Card 23 — Criar Dead Letter Topic
**Descrição:** Encaminhar eventos inválidos ou que esgotarem as tentativas de retry para um tópico DLT dedicado (ex.: `orders.created-dlt`), sem interromper o fluxo principal da plataforma.

---

### [*] Card 24 — Validar recuperação de falhas
**Descrição:** Garantir que falhas isoladas não afetem os demais consumidores nem interrompam o Event Stream.

---

# [*] Epic 9 — Plataforma Distribuída

### [*] Card 25 — Adicionar novos consumidores
**Descrição:** Integrar novos serviços independentes (ex.: inventory-consumer, que reserva estoque) utilizando apenas os eventos existentes, sem alterar os produtores. O inventory-consumer também serve de exemplo de consumidor ativo, publicando eventos derivados de volta ao Kafka.

---

### [*] Card 26 — Validar desacoplamento arquitetural
**Descrição:** Demonstrar que produtores desconhecem completamente quem consome seus eventos e como serão processados.

---

### [*] Card 27 — Monitorar a plataforma
**Descrição:** Utilizar Kafka UI para acompanhar tópicos, partições, offsets, lag e comportamento dos consumidores.

---

# [*] Epic 10 — Consolidação

### [*] Card 28 — Simular alto volume de eventos
**Descrição:** Publicar continuamente centenas de eventos para observar escalabilidade e comportamento da plataforma.

---

### [*] Card 29 — Executar fluxo completo
**Descrição:** Validar publicação, distribuição, processamento, replay e recuperação de falhas em um cenário integrado.

---

### [*] Card 30 — Consolidar arquitetura de Event Streaming
**Descrição:** Revisar todos os conceitos implementados e validar o funcionamento completo da plataforma baseada em Apache Kafka.