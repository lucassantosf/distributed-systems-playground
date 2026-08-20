#!/usr/bin/env python3
"""
validate_observability.py — Validação E2E dos Três Pilares
Implementado no Card 16.

Verifica de ponta a ponta:
  1. Faz uma requisição à sample-app e captura o trace_id do header de resposta.
  2. Consulta o Prometheus e verifica se http_requests_total foi incrementado.
  3. Consulta o Tempo via API e verifica se o trace existe com os Spans esperados.
  4. Consulta o OpenSearch e verifica se existe um log com aquele trace_id.

Retorna PASS/FAIL para cada verificação.
"""

# TODO: implementar no Card 16
