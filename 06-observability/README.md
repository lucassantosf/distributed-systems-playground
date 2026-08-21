# 06 - Observability

## 📖 Descrição

Plataforma central de observabilidade baseada nos três pilares de telemetria — **Métricas, Logs e Traces** — para ser reutilizada pelos demais projetos da trilha.

O Grafana funciona como ponto único de visualização e correlação entre os três sinais, permitindo investigar um problema partindo de uma métrica, navegar até o trace relacionado e chegar aos logs correspondentes.

---

## 🎯 Objetivos do Projeto

- Compreender os três pilares da observabilidade (Metrics, Logs e Traces) e o papel de cada um.
- Construir uma plataforma de observabilidade standalone e reutilizável para toda a trilha.
- Configurar o pipeline completo de métricas com Prometheus e estender o armazenamento com Thanos.
- Montar o pipeline de logs com Filebeat → Logstash → OpenSearch, equivalente ao ambiente de produção.
- Instrumentar aplicações com OpenTelemetry SDK para geração de traces distribuídos.
- Emitir logs estruturados em JSON com `trace_id` e `span_id` para permitir correlação entre sinais.
- Configurar dashboards provisionados automaticamente no Grafana para os três pilares.
- Configurar **data links** no Grafana que permitam navegar de uma métrica até o trace e depois até os logs correspondentes.
- Implementar alertas no Alertmanager para condições críticas (alta latência, taxa de erros, serviço down).
- Documentar e aplicar na prática a integração desta plataforma com outros projetos da trilha.

---

## 🚀 Stack

### 📊 Metrics

| Componente | Papel |
|---|---|
| **Prometheus** | Coleta métricas via scraping das aplicações e expõe para o Thanos |
| **Thanos Sidecar** | Acoplado ao Prometheus; lê blocos TSDB recentes e envia para a rede Thanos |
| **Thanos Store** | Consulta e serve dados históricos/antigos armazenados a longo prazo |
| **Thanos Querier** | Ponto único de consulta (PromQL); une e deduplica dados recentes (Sidecar) e antigos (Store) |

> Dados de métricas persistidos via **Docker Volume**.

---

### 📝 Logs

| Componente | Papel |
|---|---|
| **Filebeat** | Agente que monitora e coleta arquivos de log das aplicações |
| **Logstash** | Processa, transforma e estrutura os eventos antes do armazenamento |
| **OpenSearch** | Armazena, indexa e disponibiliza os logs para consulta |

---

### 🔎 Traces

| Componente | Papel |
|---|---|
| **OpenTelemetry SDK** | Instrumenta as aplicações, cria Spans e propaga contexto entre serviços |
| **OTel Collector** | Recebe, processa e encaminha a telemetria das aplicações |
| **Grafana Tempo** | Armazena e disponibiliza os traces distribuídos |

> Dados de traces persistidos via **Docker Volume**.

---

### 📈 Grafana

Camada de visualização central. Conecta-se a:
- **Prometheus / Thanos** → Metrics
- **OpenSearch** → Logs
- **Tempo** → Traces

---

## 🗺️ Arquitetura

```
                         APPLICATIONS
                              │
               ┌──────────────┼──────────────┐
               │              │              │
            Metrics          Logs          Traces
               │              │              │
               ▼              ▼              ▼
          Prometheus        Filebeat       OTel SDK
               │              │              │
               ▼              ▼              ▼
            Thanos         Logstash      OTel Collector
               │              │              │
               ▼              ▼              ▼
        Docker Volume      OpenSearch        Tempo
        (Metrics Data)         │              │
                               │         Docker Volume
                               │         (Trace Data)
                               │              │
               ┌───────────────┴──────────────┘
               │
               ▼
            Grafana
```

---

## 📁 Estrutura do Projeto

```text
06-observability/
│
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── apps/
│   └── sample-app/               # Aplicação de exemplo instrumentada
│       ├── app/
│       │   ├── main.py
│       │   └── routes/
│       ├── Dockerfile
│       └── requirements.txt
│
├── metrics/
│   ├── prometheus/
│   │   ├── prometheus.yml        # Configuração de scraping
│   │   └── alert-rules.yml       # Regras de alerta
│   ├── thanos/
│   │   └── thanos-config.yml     # Configuração do Sidecar / Querier / Compactor
│   └── alertmanager/
│       └── alertmanager.yml      # Configuração de receivers e rotas
│
├── logs/
│   ├── filebeat/
│   │   └── filebeat.yml          # Configuração de inputs e output para Logstash
│   └── logstash/
│       └── pipeline/
│           └── logstash.conf     # Pipeline de parse e envio ao OpenSearch
│
├── traces/
│   ├── otel-collector/
│   │   └── otel-collector-config.yaml  # Receivers, processors, exporters
│   └── tempo/
│       └── tempo.yaml            # Configuração de storage e receivers
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasources.yml   # Prometheus, OpenSearch e Tempo
│       └── dashboards/
│           ├── dashboards.yml    # Apontamento dos arquivos JSON
│           ├── metrics.json      # Dashboard de métricas
│           ├── logs.json         # Dashboard de logs
│           └── traces.json       # Dashboard de traces
│
└── scripts/
    ├── validate_observability.py # Validação E2E dos três sinais (Card 16)
    └── simulate_incident.py      # Simulação de incidente (Card 19)
```

---

## ▶️ Como Executar

Pré-requisitos: Docker e Docker Compose.

```bash
cp .env.example .env
docker compose up -d
```

| Serviço | Endereço | Credenciais |
|---|---|---|
| **Grafana** | http://localhost:3000 | admin / admin |
| **Prometheus UI** | http://localhost:9090 | — |
| **Thanos Querier** | http://localhost:10902 | — |
| **Alertmanager** | http://localhost:9093 | — |
| **OpenSearch** | http://localhost:9200 | — |
| **OTel Collector (gRPC)** | localhost:4317 | — |
| **OTel Collector (HTTP)** | localhost:4318 | — |
| **sample-app** | http://localhost:8000 | — |

> **Nota:** OpenSearch roda sem autenticação em ambiente de desenvolvimento. Não expor em ambientes públicos.

> **Plugin do Grafana:** O datasource do OpenSearch não é nativo do Grafana e precisa ser instalado via variável de ambiente no container. Adicionar no `docker-compose.yml` do serviço Grafana:
> ```yaml
> environment:
>   GF_INSTALL_PLUGINS: grafana-opensearch-datasource
> ```
> O container instalará o plugin automaticamente na primeira inicialização.

---

# [*] Epic 1 — Fundação da Plataforma de Observabilidade

### [OK] Card 1 — Criar estrutura inicial do projeto
**Descrição:** Organizar os diretórios base do projeto separando as responsabilidades por pilar de observabilidade: `metrics/`, `logs/`, `traces/`, `grafana/` e `apps/` (aplicação de exemplo para ser instrumentada). Criar o `docker-compose.yml` vazio (sem serviços ainda), `.env.example` com as variáveis de ambiente que serão usadas ao longo do projeto, `.gitignore` e o `README.md`. O objetivo deste card é apenas ter uma base limpa e organizada antes de qualquer serviço ser configurado.

---

### [OK] Card 2 — Subir infraestrutura de Métricas (Prometheus + Thanos)
**Descrição:** Configurar e subir os serviços de métricas no Docker Compose. O **Prometheus** deve ser configurado com um `prometheus.yml` básico, com scraping de si mesmo (`localhost:9090`) como primeira fonte de métricas. O **Thanos Sidecar** deve ser conectado ao Prometheus para expor os blocos de dados. O **Thanos Store Gateway** e o **Thanos Querier** devem ser configurados apontando para o Sidecar, tornando o Thanos Querier a fonte de consulta unificada. Todos os dados devem ser persistidos em Docker Volumes. Ao final, validar que o Prometheus está coletando métricas de si mesmo e que o Thanos Querier está respondendo consultas PromQL corretamente.

---

### [OK] Card 3 — Subir infraestrutura de Logs (Filebeat + Logstash + OpenSearch)
**Descrição:** Configurar e subir a stack de logs no Docker Compose. O **OpenSearch** deve ser iniciado com as configurações básicas de segurança desabilitadas para ambiente de desenvolvimento. O **Logstash** deve ser configurado com um pipeline (`logstash.conf`) que recebe eventos do Filebeat via input `beats`, aplica filtros básicos de parse (ex: `grok` ou `json`) e envia para o OpenSearch via output `elasticsearch`. O **Filebeat** deve ser configurado para monitorar arquivos de log em um diretório compartilhado (`/logs`) com output apontando para o Logstash. Ao final, criar um arquivo de log de teste no diretório monitorado e validar que ele chega ao OpenSearch consultando via API REST (`/_cat/indices`).

---

### [OK] Card 4 — Subir infraestrutura de Traces (OTel Collector + Tempo)
**Descrição:** Configurar e subir os serviços de traces no Docker Compose. O **Grafana Tempo** deve ser configurado com um `tempo.yaml` básico, habilitando o receiver OTLP (gRPC e HTTP) e persistindo dados em Docker Volume. O **OpenTelemetry Collector** deve ser configurado com um `otel-collector-config.yaml` definindo: `receivers` (OTLP gRPC e HTTP), `processors` (batch), `exporters` (Tempo via OTLP gRPC) e o `service pipeline` conectando tudo. Ao final, enviar um trace de teste via `curl` ou script para o OTel Collector e validar que ele aparece no Tempo via API REST (`/api/traces`).

---

### [*] Card 5 — Subir e configurar o Grafana
**Descrição:** Adicionar o Grafana ao Docker Compose e configurar as três fontes de dados via provisioning automático (arquivo YAML em `grafana/provisioning/datasources/`), sem precisar configurar manualmente pela UI: **Thanos Querier** como fonte de métricas, **OpenSearch** como fonte de logs (plugin `grafana-opensearch-datasource`) e **Tempo** como fonte de traces. Ao final, acessar o Grafana em `localhost:3000` e confirmar que as três fontes de dados estão configuradas com status `OK` na página de Data Sources.

---

# [*] Epic 2 — Aplicação de Exemplo Instrumentada

### [*] Card 6 — Criar aplicação de exemplo
**Descrição:** Criar uma pequena aplicação em **Python (FastAPI)** dentro do diretório `apps/sample-app/` que será a cobaia da plataforma. Ela deve expor pelo menos três endpoints: `GET /health`, `GET /orders` (lista simulada de pedidos) e `POST /orders` (cria um pedido simulado com delay aleatório para simular variação de latência). A aplicação deve rodar como container no Docker Compose e escrever logs em arquivo no diretório compartilhado com o Filebeat. O objetivo não é o domínio em si, mas ter algo realista para instrumentar nos próximos cards.

---

### [*] Card 7 — Expor métricas Prometheus na aplicação
**Descrição:** Instrumentar a aplicação de exemplo para expor métricas no formato Prometheus usando `prometheus_client`. Adicionar as seguintes métricas: `http_requests_total` (contador com labels `method`, `endpoint`, `status`), `http_request_duration_seconds` (histogram de latência por endpoint) e `app_orders_created_total` (contador de pedidos criados). Configurar o endpoint `/metrics` na aplicação e adicionar um novo `scrape_config` no `prometheus.yml` apontando para ela. Ao final, validar que as métricas aparecem no Prometheus UI e que o Thanos Querier também as serve.

---

### [*] Card 8 — Instrumentar a aplicação com OpenTelemetry (Traces)
**Descrição:** Adicionar o **OpenTelemetry SDK** à aplicação para gerar traces distribuídos. Configurar o `TracerProvider` com o exportador OTLP apontando para o OTel Collector. Usar `opentelemetry-instrumentation-fastapi` para auto-instrumentação dos endpoints HTTP. Cada requisição deve gerar um trace com: Span raiz do endpoint HTTP (método, rota, status) e Spans filhos para operações internas simuladas (ex: "query_database", "process_order") com atributos relevantes (ex: `order.id`, `order.status`). Ao final, fazer uma requisição e validar que o trace aparece no Tempo com os Spans corretos na visualização em cascata (waterfall).

---

### [*] Card 9 — Padronizar logs estruturados com correlação de traces
**Descrição:** Configurar a aplicação para emitir logs em **JSON estruturado**. Cada linha de log deve conter: `timestamp` (ISO 8601), `level`, `message`, `service`, `trace_id` e `span_id` — estes dois últimos injetados automaticamente pelo OTel SDK quando dentro de um Span ativo. Essa correlação é o que permitirá no Grafana navegar de um trace até seus logs correspondentes. Atualizar o pipeline do Logstash para fazer parse do JSON (`json` filter) sem quebrar a estrutura. Ao final, gerar uma requisição e confirmar no OpenSearch que o log contém `trace_id` e `span_id` preenchidos corretamente.

---

# [*] Epic 3 — Dashboards e Visualização

### [*] Card 10 — Criar dashboard de Métricas no Grafana
**Descrição:** Criar um dashboard de métricas da aplicação provisionado automaticamente via arquivo JSON em `grafana/provisioning/dashboards/` (não criado manualmente pela UI). Deve conter pelo menos: painel de **Taxa de Requisições** (`rate(http_requests_total[1m])` por endpoint), **Latência P50/P95/P99** (`histogram_quantile`), **Taxa de Erros** (requisições 5xx) e **Total de Pedidos Criados**. Ao final, gerar carga na aplicação e observar os painéis atualizando em tempo real.

---

### [*] Card 11 — Criar dashboard de Logs no Grafana
**Descrição:** Criar um dashboard de logs provisionado via arquivo JSON. Deve conter: painel de **Volume de Logs por Nível** (INFO/WARN/ERROR ao longo do tempo), painel de **Logs Recentes** (tabela com `timestamp`, `level`, `message`, `service`, `trace_id`) e um painel com filtro por `level=ERROR` para visualizar erros críticos rapidamente. Gerar manualmente alguns logs de WARN e ERROR na aplicação (ex: endpoint que força um erro) e validar que aparecem no dashboard.

---

### [*] Card 12 — Explorar Traces no Grafana via Tempo
**Descrição:** Configurar a exploração de traces no Grafana usando o **Explore** com a fonte de dados Tempo. Criar um dashboard com: painel de **Service Graph** (mapa de dependências e taxa de requisições entre serviços) e painel de **Trace Search** (últimos traces com duração e status). Explorar o **TraceQL** para buscas como `{.http.route="/orders" && duration > 100ms}`. Ao final, conseguir localizar um trace específico, abrir sua visualização de Spans em cascata e identificar qual Span apresentou maior duração.

---

### [*] Card 13 — Configurar correlação entre os três sinais
**Descrição:** Configurar no Grafana os **data links** que permitem navegar entre os três sinais de forma fluida — este é o coração do projeto. (1) **Metrics → Traces**: no dashboard de métricas, um link que ao clicar em um ponto de latência alta abre o Explore do Tempo filtrado pelo intervalo de tempo e serviço. (2) **Traces → Logs**: na visualização de um trace no Tempo, o link "Related Logs" abre o OpenSearch filtrado pelo `trace_id` daquele trace. (3) **Logs → Traces**: na tabela de logs, o campo `trace_id` é um link clicável que abre o trace correspondente no Tempo. Ao final, simular uma investigação real completa: spike de latência na métrica → trace lento → logs daquele trace.

---

# [*] Epic 4 — Alertas e Qualidade dos Dados

### [*] Card 14 — Configurar alertas no Prometheus (Alertmanager)
**Descrição:** Adicionar o **Alertmanager** ao Docker Compose e configurar regras de alerta no Prometheus via arquivo `alert-rules.yml`. Criar pelo menos três regras: `HighErrorRate` (taxa de erros 5xx acima de 5% nos últimos 5 minutos), `HighLatency` (P95 de latência acima de 500ms) e `ServiceDown` (target de scraping inacessível). Configurar o Alertmanager com um receiver simples (log para console ou webhook local). Ao final, forçar intencionalmente cada condição na aplicação e validar que os alertas disparam na UI do Alertmanager e em `/alerts` do Prometheus.

---

### [*] Card 15 — Configurar retenção e compactação no Thanos
**Descrição:** Explorar as funcionalidades de retenção do Thanos adicionando o **Thanos Compactor** ao Docker Compose. O Compactor é responsável por compactar blocos de métricas antigos e aplicar downsampling progressivo: resolução de 5min para dados com mais de 2h e resolução de 1h para dados com mais de 8h. Definir o período de retenção via flags do Compactor e observar via logs como os blocos são processados. O objetivo é entender na prática como o Thanos gerencia armazenamento de longo prazo — algo que o Prometheus standalone não oferece.

---

### [*] Card 16 — Validar qualidade e completude da observabilidade
**Descrição:** Criar um script `scripts/validate_observability.py` que verifica automaticamente se os três pilares estão funcionando de ponta a ponta. O script deve: (1) fazer uma requisição à aplicação e capturar o `trace_id` retornado no header de resposta; (2) consultar o Prometheus e verificar se `http_requests_total` foi incrementado; (3) consultar o Tempo via API e verificar se o trace com aquele `trace_id` existe com os Spans esperados; (4) consultar o OpenSearch e verificar se existe um log com aquele `trace_id`. Retornar `PASS/FAIL` para cada verificação. Esse card valida que observabilidade está completa e correlacionada de ponta a ponta.

---

# [*] Epic 5 — Integração com Projetos da Trilha

### [*] Card 17 — Documentar como integrar outros projetos
**Descrição:** Criar um arquivo `INTEGRATION.md` descrevendo como qualquer projeto da trilha pode se conectar a esta plataforma. O documento deve ser prático, com instruções para: (1) adicionar a rede Docker da plataforma de observabilidade ao `docker-compose.yml` do projeto externo via `networks: external: name: observability_network`; (2) adicionar um novo `scrape_config` no `prometheus.yml` para o novo serviço; (3) configurar o Filebeat para coletar logs do novo serviço; (4) configurar o OTel SDK no projeto externo apontando para o OTel Collector desta plataforma. Incluir um exemplo concreto de `docker-compose.override.yml` baseado no projeto 05 (Event Streaming Platform).

---

### [*] Card 18 — Integrar com o Projeto 05 (Event Streaming Platform)
**Descrição:** Aplicar na prática o guia do Card 17, conectando o `05-event-streaming-platform` a esta plataforma. Instrumentar o `producer-api` do projeto 05 com o OTel SDK para gerar traces nas rotas de publicação de eventos. Adicionar métricas Prometheus no producer-api: `kafka_events_published_total` (por tópico) e `kafka_publish_duration_seconds`. Configurar o Filebeat para coletar os logs do producer-api. No Grafana, criar um dashboard específico para o projeto 05 com painéis de taxa de publicação de eventos, latência e volume de logs. Ao final, publicar um evento e conseguir visualizar a métrica incrementada, o trace no Tempo e o log no Grafana — todos correlacionados pelo mesmo `trace_id`.

---

# [*] Epic 6 — Consolidação

### [*] Card 19 — Simular cenário de investigação de incidente
**Descrição:** Criar um script `scripts/simulate_incident.py` que reproduz um cenário realista de degradação: durante 2 minutos, injetar 30% das requisições com delay artificial de 2-3 segundos e 10% com erro 500. Acompanhar em tempo real no Grafana como: o painel de latência P99 sobe, o alerta `HighLatency` acende no Alertmanager, os traces lentos aparecem no Tempo com Spans indicando onde o tempo foi gasto, e os logs de ERROR aparecem no OpenSearch com os `trace_ids` correspondentes. Documentar no `README.md` o passo a passo de investigação seguido como "Playbook de Investigação": métrica → trace → log.

---

### [*] Card 20 — Consolidar a plataforma de observabilidade
**Descrição:** Revisar toda a plataforma e garantir que está completa, estável e reutilizável. Verificar: todos os serviços sobem com `docker compose up -d` sem erros; todos os dashboards do Grafana provisionam automaticamente; as três fontes de dados têm status `OK`; o script `validate_observability.py` do Card 16 passa com 100% dos checks; o `INTEGRATION.md` está atualizado e reflete a integração real feita no Card 18. Registrar no final do README, em uma seção "Lições Aprendidas", as principais observações sobre cada pilar: o que funcionou bem, o que foi surpreendente e quais as limitações percebidas ao rodar a stack completa localmente com Docker.
