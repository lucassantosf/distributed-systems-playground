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

### [OK] Card 5 — Subir e configurar o Grafana
**Descrição:** Adicionar o Grafana ao Docker Compose e configurar as três fontes de dados via provisioning automático (arquivo YAML em `grafana/provisioning/datasources/`), sem precisar configurar manualmente pela UI: **Thanos Querier** como fonte de métricas, **OpenSearch** como fonte de logs (plugin `grafana-opensearch-datasource`) e **Tempo** como fonte de traces. Ao final, acessar o Grafana em `localhost:3000` e confirmar que as três fontes de dados estão configuradas com status `OK` na página de Data Sources.

---

# [*] Epic 2 — Aplicação de Exemplo Instrumentada

### [OK] Card 6 — Criar aplicação de exemplo
**Descrição:** Criar uma pequena aplicação em **Python (FastAPI)** dentro do diretório `apps/sample-app/` que será a cobaia da plataforma. Ela deve expor pelo menos três endpoints: `GET /health`, `GET /orders` (lista simulada de pedidos) e `POST /orders` (cria um pedido simulado com delay aleatório para simular variação de latência). A aplicação deve rodar como container no Docker Compose e escrever logs em arquivo no diretório compartilhado com o Filebeat. O objetivo não é o domínio em si, mas ter algo realista para instrumentar nos próximos cards.

---

### [OK] Card 7 — Expor métricas Prometheus na aplicação
**Descrição:** Instrumentar a aplicação de exemplo para expor métricas no formato Prometheus usando `prometheus_client`. Adicionar as seguintes métricas: `http_requests_total` (contador com labels `method`, `endpoint`, `status`), `http_request_duration_seconds` (histogram de latência por endpoint) e `app_orders_created_total` (contador de pedidos criados). Configurar o endpoint `/metrics` na aplicação e adicionar um novo `scrape_config` no `prometheus.yml` apontando para ela. Ao final, validar que as métricas aparecem no Prometheus UI e que o Thanos Querier também as serve.

---

### [OK] Card 8 — Instrumentar a aplicação com OpenTelemetry (Traces)
**Descrição:** Adicionar o **OpenTelemetry SDK** à aplicação para gerar traces distribuídos. Configurar o `TracerProvider` com o exportador OTLP apontando para o OTel Collector. Usar `opentelemetry-instrumentation-fastapi` para auto-instrumentação dos endpoints HTTP. Cada requisição deve gerar um trace com: Span raiz do endpoint HTTP (método, rota, status) e Spans filhos para operações internas simuladas (ex: "query_database", "process_order") com atributos relevantes (ex: `order.id`, `order.status`). Ao final, fazer uma requisição e validar que o trace aparece no Tempo com os Spans corretos na visualização em cascata (waterfall).

---

### [OK] Card 9 — Padronizar logs estruturados com correlação de traces
**Descrição:** Configurar a aplicação para emitir logs em **JSON estruturado**. Cada linha de log deve conter: `timestamp` (ISO 8601), `level`, `message`, `service`, `trace_id` e `span_id` — estes dois últimos injetados automaticamente pelo OTel SDK quando dentro de um Span ativo. Essa correlação é o que permitirá no Grafana navegar de um trace até seus logs correspondentes. Atualizar o pipeline do Logstash para fazer parse do JSON (`json` filter) sem quebrar a estrutura. Ao final, gerar uma requisição e confirmar no OpenSearch que o log contém `trace_id` e `span_id` preenchidos corretamente.

---

# [*] Epic 3 — Dashboards e Visualização

### [OK] Card 10 — Criar dashboard de Métricas no Grafana
**Descrição:** Criar um dashboard de métricas da aplicação provisionado automaticamente via arquivo JSON em `grafana/provisioning/dashboards/` (não criado manualmente pela UI). Deve conter pelo menos: painel de **Taxa de Requisições** (`rate(http_requests_total[1m])` por endpoint), **Latência P50/P95/P99** (`histogram_quantile`), **Taxa de Erros** (requisições 5xx) e **Total de Pedidos Criados**. Ao final, gerar carga na aplicação e observar os painéis atualizando em tempo real.

---

### [OK] Card 11 — Criar dashboard de Logs no Grafana
**Descrição:** Criar um dashboard de logs provisionado via arquivo JSON. Deve conter: painel de **Volume de Logs por Nível** (INFO/WARN/ERROR ao longo do tempo), painel de **Logs Recentes** (tabela com `timestamp`, `level`, `message`, `service`, `trace_id`) e um painel com filtro por `level=ERROR` para visualizar erros críticos rapidamente. Gerar manualmente alguns logs de WARN e ERROR na aplicação (ex: endpoint que força um erro) e validar que aparecem no dashboard.

---

### [OK] Card 12 — Explorar Traces no Grafana via Tempo
**Descrição:** Configurar a exploração de traces no Grafana usando o **Explore** com a fonte de dados Tempo. Criar um dashboard com: painel de **Service Graph** (mapa de dependências e taxa de requisições entre serviços) e painel de **Trace Search** (últimos traces com duração e status). Explorar o **TraceQL** para buscas como `{.http.route="/orders" && duration > 100ms}`. Ao final, conseguir localizar um trace específico, abrir sua visualização de Spans em cascata e identificar qual Span apresentou maior duração.

---

### [OK] Card 13 — Configurar correlação entre os três sinais
**Descrição:** Configurar no Grafana os **data links** que permitem navegar entre os três sinais de forma fluida — este é o coração do projeto. (1) **Metrics → Traces**: no dashboard de métricas, um link que ao clicar em um ponto de latência alta abre o Explore do Tempo filtrado pelo intervalo de tempo e serviço. (2) **Traces → Logs**: na visualização de um trace no Tempo, o link "Related Logs" abre o OpenSearch filtrado pelo `trace_id` daquele trace. (3) **Logs → Traces**: na tabela de logs, o campo `trace_id` é um link clicável que abre o trace correspondente no Tempo. Ao final, simular uma investigação real completa: spike de latência na métrica → trace lento → logs daquele trace.

---

# [*] Epic 4 — Alertas e Qualidade dos Dados

### [OK] Card 14 — Configurar alertas no Prometheus (Alertmanager)
**Descrição:** Adicionar o **Alertmanager** ao Docker Compose e configurar regras de alerta no Prometheus via arquivo `alert-rules.yml`. Criar pelo menos três regras: `HighErrorRate` (taxa de erros 5xx acima de 5% nos últimos 5 minutos), `HighLatency` (P95 de latência acima de 500ms) e `ServiceDown` (target de scraping inacessível). Configurar o Alertmanager com um receiver simples (log para console ou webhook local). Ao final, forçar intencionalmente cada condição na aplicação e validar que os alertas disparam na UI do Alertmanager e em `/alerts` do Prometheus.

---

### [OK] Card 15 — Configurar retenção e compactação no Thanos
**Descrição:** Explorar as funcionalidades de retenção do Thanos adicionando o **Thanos Compactor** ao Docker Compose. O Compactor é responsável por compactar blocos de métricas antigos e aplicar downsampling progressivo: resolução de 5min para dados com mais de 2h me resolução de 1h para dados com mais de 8h. Definir o período de retenção via flags do Compactor e observar via logs como os blocos são processados. O objetivo é entender na prática como o Thanos gerencia armazenamento de longo prazo — algo que o Prometheus standalone não oferece.

---

### [OK] Card 16 — Validar qualidade e completude da observabilidade
**Descrição:** Criar um script `scripts/validate_observability.py` que verifica automaticamente se os três pilares estão funcionando de ponta a ponta. O script deve: (1) fazer uma requisição à aplicação e capturar o `trace_id` retornado no header de resposta; (2) consultar o Prometheus e verificar se `http_requests_total` foi incrementado; (3) consultar o Tempo via API e verificar se o trace com aquele `trace_id` existe com os Spans esperados; (4) consultar o OpenSearch e verificar se existe um log com aquele `trace_id`. Retornar `PASS/FAIL` para cada verificação. Esse card valida que observabilidade está completa e correlacionada de ponta a ponta.

---

# [*] Epic 5 — Integração com Projetos da Trilha

### [OK] Card 17 — Documentar como integrar outros projetos
**Descrição:** Criar um arquivo `INTEGRATION.md` descrevendo como qualquer projeto da trilha pode se conectar a esta plataforma. O documento deve ser prático, com instruções para: (1) adicionar a rede Docker da plataforma de observabilidade ao `docker-compose.yml` do projeto externo via `networks: external: name: observability_network`; (2) adicionar um novo `scrape_config` no `prometheus.yml` para o novo serviço; (3) configurar o Filebeat para coletar logs do novo serviço; (4) configurar o OTel SDK no projeto externo apontando para o OTel Collector desta plataforma. Incluir um exemplo concreto de `docker-compose.override.yml` baseado no projeto 05 (Event Streaming Platform).

---

### [OK] Card 18 — Integrar com o Projeto 05 (Event Streaming Platform)
**Objetivo:** Aplicar na prática o guia do Card 17, conectando o `05-event-streaming-platform` a esta plataforma de observabilidade. Ao final, publicar um evento e visualizar a métrica, o trace e o log correlacionados pelo mesmo `trace_id` no Grafana.

---

#### [OK] Card 18.1 — Conectar a rede Docker e configurar o OTel SDK no producer-api
**Descrição:** Adicionar a `observability_network` ao `docker-compose.yml` do Projeto 05 via `docker-compose.override.yml`. Instalar as bibliotecas OTel no `producer-api` (`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`). Criar um arquivo `telemetry.py` no producer-api que inicializa o `TracerProvider` com o exporter apontando para `otel-collector:4317` e instrumenta automaticamente o FastAPI. Ao final, verificar no Grafana Tempo que traces do `producer-api` já aparecem.

---

#### [OK] Card 18.2 — Adicionar logging estruturado JSON com trace_id no producer-api
**Descrição:** Criar um `logging_config.py` no producer-api análogo ao da `sample-app`: logs em formato JSON com campos `timestamp`, `level`, `service`, `trace_id` e `message`. O `trace_id` deve ser extraído do span ativo via `trace.get_current_span()`. Configurar o Filebeat para coletar os logs do producer-api adicionando um novo input em `logs/filebeat/filebeat.yml`. Ao final, verificar no dashboard de Logs do Grafana que os logs do `producer-api` aparecem com o campo `trace_id` preenchido.

---

#### [OK] Card 18.3 — Adicionar métricas Prometheus no producer-api
**Descrição:** Instalar `prometheus-client` no producer-api. Criar um arquivo `metrics.py` com os contadores: `kafka_events_published_total` (por tópico e status) e o histogram `kafka_publish_duration_seconds`. Instrumentar o endpoint de publicação de eventos para incrementar as métricas. Adicionar o middleware de métricas HTTP (análogo ao da `sample-app`) e expor o endpoint `/metrics`. Adicionar o job `producer-api` no `prometheus.yml` da plataforma e reiniciar o Prometheus. Ao final, verificar na UI do Prometheus que o target está `UP` e as métricas aparecem.

---

#### [OK] Card 18.4 — Criar dashboard no Grafana para o Projeto 05
**Descrição:** O arquivo `grafana/provisioning/dashboards/event-streaming-dashboard.json` já existe como placeholder com painéis de `kafka_events_published_total` e `kafka_publish_duration_seconds`. Validar e completar o dashboard adicionando: painel de **taxa de requisições HTTP** do producer-api, painel de **latência P95** de publicação, painel de **logs recentes** do producer-api e um painel de **taxa de erros**. Provisionar via arquivo e verificar que o dashboard aparece no Grafana após `docker compose restart grafana`.

---

#### [OK] Card 18.5 — Validação E2E: publicar evento e correlacionar os três sinais
**Descrição:** Com todos os sub-cards anteriores concluídos, realizar a validação final. Subir o Projeto 05 com `docker compose up -d` (usando o override da rede). Publicar um evento via `POST /orders` no producer-api. Verificar no Grafana: (1) o contador `kafka_events_published_total` foi incrementado no dashboard do Projeto 05; (2) o trace da requisição aparece no Tempo com os Spans do FastAPI e da publicação Kafka; (3) o log estruturado com o mesmo `trace_id` aparece no OpenSearch.

**Validação Realizada com Sucesso:**
- **Order ID:** `f511c0a1-c887-40fb-a7ea-85b5e5b4cb0d`
- **Trace ID Correlacionado:** `c69b8d4b3dbb3885a767cbece44a1169`
- **Métrica:** `kafka_events_published_total{job="producer-api", status="success", topic="orders.created"}` registrada no Prometheus/Thanos.
- **Trace:** Localizado no Grafana Tempo com ID `c69b8d4b3dbb3885a767cbece44a1169`.
- **Logs:** 2 entradas de log indexadas no OpenSearch com o campo `trace_id: "c69b8d4b3dbb3885a767cbece44a1169"`.

---

# [*] Epic 6 — Consolidação

### [OK] Card 19 — Simular cenário de investigação de incidente
**Descrição:** Criar um script `scripts/simulate_incident.py` que reproduz um cenário realista de degradação: durante 2 minutos, injetar 30% das requisições com delay artificial de 2-3 segundos e 10% com erro 500. Acompanhar em tempo real no Grafana como: o painel de latência P99 sobe, o alerta `HighLatency` acende no Alertmanager, os traces lentos aparecem no Tempo com Spans indicando onde o tempo foi gasto, e os logs de ERROR aparecem no OpenSearch com os `trace_ids` correspondentes.

---

### 📖 Playbook de Investigação de Incidente (Métrica → Trace → Log)

#### **Passo 1: Executar a Simulação de Incidente**
Rode o script de carga degradada para disparar alertas e métricas de anomalia:
```bash
python3 scripts/simulate_incident.py --duration 120
```

#### **Passo 2: Diagnóstico Inicial por Métricas (Prometheus / Grafana)**
1. Acesse o Dashboard **Overview / Metrics** (`http://localhost:3000/d/sample-app-metrics`).
2. Observe os painéis de **Taxa de Erros HTTP (5xx)** subindo acima de 5% e o gráfico de **Latência P95 / P99** subindo acima de 2.0s.
3. No **Alertmanager** (`http://localhost:9093`) ou Grafana Alerts, observe os alertas em estado `FIRING`:
   - `HighErrorRate` (taxa de erros 5xx > 5%)
   - `HighLatency` (latência P95 > 500ms)

#### **Passo 3: Isolamento e Análise de Causa Raiz por Traces (Grafana Tempo)**
1. Acesse o **Grafana Explore** → Seletor de DataSource **Tempo** (`http://localhost:3000/explore`).
2. Filtre por `Service Name: sample-app` ou `minDuration: 2s` e execute a busca.
3. Clique em uma das requisições lentas (`GET /debug/slow`).
4. Inspecione a árvore de Spans: veja exatamente qual Span consumiu os 2.5s (ex: `asyncio.sleep` / handler HTTP).
5. Copie o `trace_id` da requisição (ex: `6bc04560f3b31540d0cb764cfcfcc616`).

#### **Passo 4: Investigação de Detalhes e Exceções por Logs (OpenSearch)**
1. Mude o DataSource no Grafana Explore para **OpenSearch** (ou acesse a aba Logs).
2. Execute a busca usando Lucene com o `trace_id` obtido no passo anterior:
   ```lucene
   trace_id:6bc04560f3b31540d0cb764cfcfcc616
   ```
3. Ou filtre por erros:
   ```lucene
   service:sample-app AND level:ERROR
   ```
4. Inspecione o payload JSON do log contendo a mensagem de erro original e o stacktrace da exceção.

---

### [OK] Card 20 — Consolidar a plataforma de observabilidade
**Descrição:** Revisar toda a plataforma e garantir que está completa, estável e reutilizável. Todos os serviços sobem com `docker compose up -d` sem erros; todos os dashboards do Grafana provisionam automaticamente; as três fontes de dados têm status `OK`; o script `validate_observability.py` do Card 16 passa com 100% dos checks; o `INTEGRATION.md` está atualizado e reflete a integração real do `producer-api` (Card 18).

---

## 🧠 Lições Aprendidas e Conclusões da Plataforma

Ao longo do desenvolvimento e integração desta plataforma de observabilidade completa, consolidamos valiosas lições sobre arquitetura, ferramentas e operação dos três pilares da observabilidade em ambiente de microsserviços.

### 1. Pilar de Métricas (Prometheus + Thanos)
- **O que funcionou bem:** O modelo *pull* do Prometheus combinado com a sintaxe PromQL permitiu calcular taxas por segundo (`rate`), percentis P95/P99 (`histogram_quantile`) e percentual de erros em tempo real.
- **Surpreendente:** O **Thanos** integra perfeitamente com o Prometheus via Thanos Sidecar, permitindo unificar métricas históricas de múltiplas réplicas e prover alta disponibilidade transparente para o Grafana.
- **Limitações:** O intervalo de scraping (`scrape_interval: 15s`) gera um pequeno atraso visual (15-30s) na atualização dos painéis e requer um volume mínimo de pontos amostrados para calcular o `rate` com precisão.

### 2. Pilar de Traces Distribuídos (OpenTelemetry + Grafana Tempo)
- **O que funcionou bem:** A padronização com **W3C Trace Context** permite propagar o `traceparent` via cabeçalhos HTTP transparente entre serviços. O OTel Collector atua como gateway universal eficiente para gRPC/OTLP.
- **Surpreendente:** Em ambiente de desenvolvimento/local, utilizar `SimpleSpanProcessor` (envio imediato por span) facilitou imensamente a validação em relação ao `BatchSpanProcessor`. Além disso, a implementação de um middleware ASGI customizado evitou incompatibilidades com pacotes de instrumentação no Python 3.12-slim.
- **Limitações:** Traces detalhados com muitos atributos geram alto consumo de rede gRPC e exigem políticas de amostragem (*sampling*) em ambientes de produção com altíssimo tráfego.

### 3. Pilar de Logs Estruturados (Filebeat + Logstash + OpenSearch)
- **O que funcionou bem:** O formato JSON estruturado com o campo de contexto `trace_id` injetado pelo `OtelTraceFilter` transforma o arquivo de log bruto em um sinal correlacionado de alta utilidade.
- **Surpreendente:** A capacidade de pesquisar diretamente no OpenSearch via Lucene no Grafana usando o `trace_id` de um span do Tempo elimina 90% do tempo gasto em investigações de incidentes (*Métrica → Trace → Log*).
- **Limitações:** O pipeline Filebeat → Logstash adiciona um pequeno delay (10-15s) de processamento e indexação. Adicionalmente, a JVM do Logstash e do OpenSearch juntas demandam a maior parcela da memória RAM da infraestrutura local.

### 4. Arquitetura Geral & Execução em Docker
- **O que funcionou bem:** A criação da rede Docker compartilhada `observability_network` e a estratégia de `docker-compose.override.yml` tornaram a plataforma Plug-and-Play para conectar qualquer projeto externo (como o `05-event-streaming-platform`).
- **Resumo do Consumo:** A stack completa executa 16 containers simultâneos com estabilidade total e 100% dos checks automatizados validados.