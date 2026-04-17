"""Pacote de endpoints de onboarding (APP-11 server side).

Expoe um endpoint leve que registra a conclusao do onboarding do
usuario na outbox `notifications` (ADR-003 — padrao outbox para
entregas multicanal). O consumer SMTP real ainda nao foi entregue;
quando for, a linha `type='first_collection_done'` fica elegivel para
virar email sem mudanca aqui.
"""
