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
cp .env.example .env
docker compose up --build
```

Para integrar o backend à plataforma `06-observability`, suba primeiro a plataforma
e depois o chat. A plataforma cria a rede Docker compartilhada `observability_network`;
o backend do chat entra nessa rede e usa `otel-collector:4317` como endpoint OTLP.

```bash
# Em distributed-systems-playground/06-observability
docker compose up -d

# Em distributed-systems-playground/02-realtime-chat
CHAT_BACKEND_PORT=8002 docker compose up --build -d
```

O `CHAT_BACKEND_PORT` evita o conflito com a `sample-app` da plataforma, que
também publica a porta `8000`. Em execução standalone, o padrão continua sendo
`http://localhost:8000`.

Validar a integração de rede:

```bash
docker compose exec backend getent hosts otel-collector
docker compose exec backend sh -c 'echo "$OTEL_SERVICE_NAME -> $OTEL_EXPORTER_OTLP_ENDPOINT"'
```

Os logs do backend são montados em `02-realtime-chat/logs/` e ficam disponíveis
para o Filebeat da plataforma no Card 30. O diretório é ignorado pelo Git.

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

# Ver todas as métricas Prometheus (use 8002 quando a observability estiver ativa)
curl http://localhost:8000/metrics

# Ver logs em tempo real
docker compose logs -f
```

### Métricas do backend

O endpoint `GET /metrics` expõe as métricas no formato Prometheus. Com o chat
integrado à plataforma de observabilidade, consulte `http://localhost:8002/metrics`;
em execução standalone, use `http://localhost:8000/metrics`.

| Métrica | O que mostra |
|---------|--------------|
| `chat_http_requests_total` | Total de requests HTTP por método, rota e status |
| `chat_http_request_duration_seconds` | Latência dos requests HTTP |
| `chat_websocket_connections_total` | WebSockets conectados e desconectados |
| `chat_active_connections` | Conexões WebSocket ativas neste momento |
| `chat_active_rooms` | Salas com pelo menos uma conexão neste momento |
| `chat_rooms_seen_total` | Salas distintas vistas desde o início do backend |
| `chat_messages_total` | Mensagens recebidas, persistidas e publicadas desde o início do backend |
| `chat_heartbeat_timeouts_total` | Conexões removidas por timeout de heartbeat |

Exemplos de consultas no Prometheus (`http://localhost:9090`) ou no Grafana:

```promql
# Quantidade de chats/salas abertos agora
chat_active_rooms

# Usuários conectados agora
chat_active_connections

# Requests por segundo nos últimos 5 minutos
sum(rate(chat_http_requests_total[5m]))

# Latência HTTP P95
histogram_quantile(0.95, sum(rate(chat_http_request_duration_seconds_bucket[5m])) by (le))

# Mensagens recebidas por segundo
rate(chat_messages_total{event="received"}[5m])
```

As métricas `chat_rooms_seen_total` e `chat_messages_total` são contadores do
processo e reiniciam quando o backend reinicia. Elas mostram a atividade da
execução atual; o histórico permanente continua no PostgreSQL.

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

### Epic 10 — Observabilidade do Chat [EM ANDAMENTO]

Objetivo: integrar o backend do chat à plataforma `06-observability`, cobrindo os três pilares de observabilidade — métricas, logs e traces — e permitindo investigar o fluxo completo de uma mensagem: WebSocket → PostgreSQL → Redis Pub/Sub → broadcast WebSocket.

| Card | Descrição | Status |
|------|-----------|--------|
| 26 | Conectar o chat à plataforma de observabilidade | OK |
| 27 | Instrumentar métricas do backend | OK |
| 28 | Integrar métricas ao Prometheus e criar alertas | A FAZER |
| 29 | Implementar logs estruturados em JSON | A FAZER |
| 30 | Integrar logs ao Filebeat, Logstash e OpenSearch | A FAZER |
| 31 | Instrumentar traces distribuídos com OpenTelemetry | A FAZER |
| 32 | Propagar contexto entre HTTP, WebSocket, PostgreSQL e Redis | A FAZER |
| 33 | Criar dashboard unificado do chat no Grafana | A FAZER |
| 34 | Validar correlação entre métricas, logs e traces | A FAZER |

---

### [OK] Card 26 — Conectar o chat à plataforma de observabilidade

**Descrição:** Configurar o `docker-compose.yml` do chat para conectar o backend à rede externa `observability_network`, mantendo também a rede padrão do projeto. Adicionar variáveis de ambiente para o nome do serviço (`chat-backend`), ambiente e endpoint OTLP (`http://otel-collector:4317`). Criar ou montar o diretório de logs do backend em um caminho que possa ser lido pelo Filebeat da plataforma de observabilidade. Documentar a ordem de inicialização: subir primeiro `06-observability` para criar a rede compartilhada e depois subir o chat.

**Critérios de aceite:**

- O backend alcança o `otel-collector` pelo nome do serviço na rede compartilhada.
- O container do backend permanece funcional para PostgreSQL e Redis.
- O projeto documenta como subir as duas stacks em conjunto.
- As credenciais, URLs e endpoints de observabilidade são configuráveis por ambiente.

**Dependências:** nenhuma.

### [OK] Card 27 — Instrumentar métricas do backend

**Descrição:** Adicionar a biblioteca `prometheus-client` ao backend FastAPI e expor `GET /metrics`. Criar métricas com nomes e labels de baixa cardinalidade para acompanhar a saúde do chat, incluindo: conexões WebSocket abertas e encerradas, conexões ativas, mensagens recebidas e publicadas, erros por operação, usuários e salas ativas, latência de persistência no PostgreSQL, latência de publicação/consumo no Redis e falhas de heartbeat. Não usar username, conteúdo da mensagem ou identificadores individuais como labels.

**Critérios de aceite:**

- `GET /metrics` retorna métricas no formato Prometheus.
- O fluxo de entrada, persistência, publicação e broadcast atualiza as métricas correspondentes.
- Latências são registradas em histogramas com buckets apropriados.
- Testes cobrem pelo menos uma métrica de conexão, uma de mensagem e uma de dependência externa.

**Dependências:** Card 26.

### [*] Card 28 — Integrar métricas ao Prometheus e criar alertas

**Descrição:** Adicionar um job `chat-backend` ao `06-observability/metrics/prometheus/prometheus.yml`, apontando para o serviço do backend e o endpoint `/metrics`. Criar regras específicas para indisponibilidade do backend, aumento da taxa de erros, latência elevada de PostgreSQL/Redis, crescimento de conexões encerradas inesperadamente e ausência de mensagens em um cenário de teste ativo. Definir severidade e janela de avaliação para evitar alertas por flutuações momentâneas.

**Critérios de aceite:**

- O target do chat aparece como `UP` no Prometheus.
- As queries das regras retornam dados reais do backend.
- Cada alerta possui expressão, severidade, descrição e ação sugerida.
- Um teste controlado consegue disparar e resolver pelo menos um alerta.

**Dependências:** Card 27.

### [*] Card 29 — Implementar logs estruturados em JSON

**Descrição:** Substituir o logging textual do backend por logs estruturados em JSON, seguindo o padrão da `sample-app` do projeto `06-observability`. Emitir logs em stdout e em arquivo no diretório compartilhado. Padronizar campos como `timestamp`, `level`, `service`, `environment`, `event`, `room`, operação, duração e erro. Sanitizar o username e nunca registrar conteúdo de mensagens, tokens ou dados sensíveis. Incluir `trace_id` e `span_id` quando houver contexto OpenTelemetry.

**Critérios de aceite:**

- Cada evento relevante do ciclo de vida WebSocket gera log estruturado.
- Falhas de PostgreSQL, Redis e validação geram logs com nível e stack trace adequados.
- As linhas do arquivo são JSON válido e podem ser processadas sem parsing específico do chat.
- Logs não expõem conteúdo de mensagem nem credenciais.

**Dependências:** Card 26; o campo de trace será completado no Card 31.

### [*] Card 30 — Integrar logs ao Filebeat, Logstash e OpenSearch

**Descrição:** Adicionar ao `06-observability/logs/filebeat/filebeat.yml` um input para os arquivos do chat e garantir que o volume compartilhado esteja montado no caminho esperado. Ajustar o pipeline do Logstash apenas quando necessário para preservar os campos JSON do chat e normalizar `service.name`, `event.name`, `trace_id` e `span_id`. Criar uma consulta ou view no Grafana/OpenSearch para filtrar rapidamente logs do serviço `chat-backend` por sala, operação, nível e trace.

**Critérios de aceite:**

- Um log gerado pelo backend é indexado no OpenSearch.
- É possível filtrar pelo serviço e pelo nível sem consultar o arquivo bruto.
- `trace_id` e `span_id` ficam disponíveis como campos pesquisáveis.
- O pipeline não quebra a ingestão dos logs existentes da plataforma.

**Dependências:** Cards 26 e 29.

### [*] Card 31 — Instrumentar traces distribuídos com OpenTelemetry

**Descrição:** Adicionar as dependências OpenTelemetry ao backend e configurar um `TracerProvider` com exportação OTLP via gRPC para `otel-collector:4317`, usando `service.name=chat-backend`. Instrumentar automaticamente as rotas HTTP e criar spans manuais para conexão/desconexão WebSocket, carregamento de histórico, persistência no PostgreSQL, publicação/consumo no Redis e broadcast para a sala. Registrar atributos técnicos úteis, sem incluir conteúdo da mensagem ou dados sensíveis.

**Critérios de aceite:**

- Um request HTTP e uma sessão WebSocket produzem traces no Tempo.
- Um trace de envio de mensagem mostra as etapas de persistência, Redis e broadcast.
- Exceções são registradas nos spans com status de erro.
- O backend continua funcionando quando o Collector está indisponível, sem bloquear o fluxo do chat.

**Dependências:** Card 26.

### [*] Card 32 — Propagar contexto entre HTTP, WebSocket, PostgreSQL e Redis

**Descrição:** Definir como o contexto de tracing será mantido durante o ciclo de vida de uma conexão WebSocket e entre tarefas assíncronas. Garantir que spans de banco e Redis sejam filhos do span da operação da mensagem, e que logs emitidos dentro dessas operações recebam os mesmos `trace_id` e `span_id`. Validar especialmente o caminho assíncrono do subscriber Redis até o broadcast WebSocket.

**Critérios de aceite:**

- Os spans do fluxo de uma mensagem aparecem no mesmo trace quando tecnicamente possível.
- Logs da mesma operação podem ser encontrados pelo `trace_id` do Tempo.
- Não há contexto compartilhado indevidamente entre salas ou mensagens concorrentes.
- Existe um teste ou cenário reproduzível para verificar a correlação.

**Dependências:** Cards 29 e 31.

### [*] Card 33 — Criar dashboard unificado do chat no Grafana

**Descrição:** Provisionar um dashboard específico para `chat-backend`, reutilizando o modelo de dashboards do `06-observability`. Exibir disponibilidade, conexões ativas, usuários e salas, taxa de mensagens, erros, latência de PostgreSQL/Redis, conexões encerradas e atividade de heartbeat. Adicionar links de dados para navegar de métricas para traces e de traces para logs no OpenSearch.

**Critérios de aceite:**

- O dashboard é carregado automaticamente ao iniciar o Grafana.
- Os painéis usam o datasource Thanos/Prometheus e filtram `service`/`job` do chat.
- Há painéis suficientes para diagnosticar disponibilidade, capacidade e latência.
- Os data links abrem o trace e os logs correspondentes quando os IDs existem.

**Dependências:** Cards 28, 30 e 32.

### [*] Card 34 — Validar correlação entre métricas, logs e traces

**Descrição:** Criar um roteiro ou script de validação ponta a ponta que suba as duas plataformas, abra pelo menos duas conexões na mesma sala, envie mensagens, provoque uma falha controlada de dependência e verifique os três sinais. Documentar consultas PromQL, filtros do OpenSearch e busca de traces no Tempo para investigar um incidente real do chat.

**Critérios de aceite:**

- O cenário de teste gera métricas, logs e traces do `chat-backend`.
- Uma mensagem pode ser rastreada da métrica até o trace e os logs relacionados.
- A falha controlada aparece com erro nos logs, nos spans e nas métricas apropriadas.
- O README documenta comandos de validação e problemas conhecidos da integração.

**Dependências:** Cards 28, 30, 32 e 33.
