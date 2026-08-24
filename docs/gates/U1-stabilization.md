# Gate U1 — Estabilização

> Data: 2026-08-24

Esta etapa corrige divergências encontradas após a primeira aprovação do U1 sem
alterar seu escopo arquitetural.

## Correções

- migração idempotente v2 para persistir `published`, `deprecated` e `revoked`;
- filtros `runtime` e `status` efetivamente aplicados no SQLite;
- busca FTS preserva o par exato `id + version`;
- total de busca independente de `limit` e `offset`;
- IDs com `/` e sufixo opcional `@version` aceitos pela API;
- status inválido retorna HTTP 422 em vez de ser ignorado;
- alteração de status auditada sem modificar o payload imutável;
- command palette protegida com `[hidden]` antes do JavaScript carregar;
- código e testes normalizados por `ruff format`.

## Evidências reproduzidas

- 111 testes aprovados;
- 89,18% de cobertura (mínimo obrigatório: 85%);
- `ruff check`: aprovado;
- `ruff format --check`: aprovado;
- `mypy --strict`: aprovado em 14 arquivos;
- wheel e source distribution construídos com `uv build`.

O warning de depreciação emitido pelo `TestClient` pertence à combinação atual
FastAPI/Starlette e não afeta o resultado dos testes. Ele deve ser acompanhado
em atualização futura das dependências.
