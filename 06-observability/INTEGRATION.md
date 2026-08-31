# Guia de Integração — Conectando Projetos Externos à Plataforma de Observabilidade

Este documento descreve como conectar qualquer serviço ou projeto externo da trilha (como o **Projeto 05 — Event Streaming Platform**) a esta plataforma de observabilidade unificada.

---

## 1. Conectar a Rede Docker (`observability_network`)

Para que seu serviço consiga se comunicar com a plataforma de observabilidade, ele deve se conectar à rede Docker compartilhada `observability_network`.

No `docker-compose.yml` do seu projeto externo (ou via `docker-compose.override.yml`), adicione:

```yaml
version: '3.8'

services:
  seu-servico:
    networks:
      - default
      - observability_network

networks:
  observability_network:
    external: true
    name: observability_network
```

---

## 2. Métricas — Prometheus (`prometheus.yml`)

Para que o Prometheus colete métricas do seu novo serviço, adicione um novo `job` em `metrics/prometheus/prometheus.yml` na plataforma de observabilidade:

```yaml
scrape_configs:
  - job_name: "meu-servico"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["meu-servico:8000"]
```

Reinicie o Prometheus para aplicar:
```bash
docker compose restart prometheus
```

---

## 3. Logs Estruturados — Filebeat (`filebeat.yml`)

1. Garanta que a sua aplicação grava logs em arquivo JSON no formato:
   ```json
   {"timestamp": "2026-08-31T20:00:00Z", "level": "INFO", "service": "meu-servico", "trace_id": "...", "message": "Log mensagem"}
   ```
2. Mapeie o diretório de logs do seu container para um volume compartilhado ou subpasta lida pelo Filebeat em `logs/filebeat/filebeat.yml`.

Exemplo de entrada no `filebeat.yml`:
```yaml
filebeat.inputs:
  - type: filestream
    id: meu-servico-logs
    enabled: true
    paths:
      - /logs/meu-servico/*.log
```

---

## 4. Traces Distribuídos — OpenTelemetry SDK (OTel)

Configure a sua aplicação para enviar traces OTel via gRPC (porta `4317`) ou HTTP (porta `4318`) para o **OTel Collector** da plataforma (`otel-collector:4317`).

Exemplo em Python:
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "meu-servico"})
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
```

---

## Exemplo Prático: `docker-compose.override.yml` para o Projeto 05

```yaml
version: '3.8'

services:
  producer-api:
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_SERVICE_NAME=producer-api
    networks:
      - default
      - observability_network

networks:
  observability_network:
    external: true
    name: observability_network
```
