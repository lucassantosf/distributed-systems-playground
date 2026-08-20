#!/usr/bin/env python3
"""
simulate_incident.py — Simulação de Cenário de Degradação
Implementado no Card 19.

Durante 2 minutos:
  - 30% das requisições com delay artificial de 2-3 segundos.
  - 10% das requisições com erro 500.

Permite acompanhar em tempo real no Grafana:
  - Latência P99 subindo.
  - Alerta HighLatency acendendo no Alertmanager.
  - Traces lentos no Tempo com Spans indicando onde o tempo foi gasto.
  - Logs de ERROR no OpenSearch com os trace_ids correspondentes.
"""

# TODO: implementar no Card 19
