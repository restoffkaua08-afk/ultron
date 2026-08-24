# ULTRON

> Plataforma independente de capacidades versionadas — agents, skills, workflows e packs.
> Parte do **Projeto Meta**. Independente. Auditável. Fail-safe.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Status: Gate U1](https://img.shields.io/badge/Status-Gate%20U1-brightgreen)]()

---

## O que é

ULTRON é uma **plataforma de capacidades** (não um agente). Ela organiza, valida, versiona e distribui quatro tipos de entidade:

- **Agent** — perfil executável (runtime, modelos, tools, skills, budgets, permissões)
- **Skill** — capacidade reutilizável (instruções + tools + pipeline)
- **Workflow** — grafo de passos, dependências, condições, retries, timeouts, compensações
- **Pack** — unidade distribuível que agrupa as três acima + configurações + assets

ULTRON **não é** o cérebro do Zane, do Jarvis ou de qualquer agente. É um **catálogo e protocolo** de extensão. Se o ULTRON cair, os agentes continuam operando com suas capacidades nativas.

## Instalação para desenvolvimento

```bash
# Requer Python 3.12+ e uv
git clone https://github.com/restoffkaua08-afk/ultron.git
cd ultron
uv sync --extra dev
```

## Início rápido (5 minutos)

```python
import asyncio

from ultron import Registry

# Abre o registry local (SQLite em ~/.ultron/registry.db)
async def main() -> None:
    # Registry.open() é um context manager assíncrono.
    async with Registry.open() as registry:
        # Consulte a referência dos manifests antes de publicar dados reais.
        print(await registry.stats())


asyncio.run(main())
```

## Documentação

A documentação mestra está no repositório
[`Documenta-oMeta/docs/ultron`](https://github.com/restoffkaua08-afk/Documenta-oMeta/tree/main/docs/ultron).
Este repositório mantém somente evidências técnicas locais em [`docs/gates/`](docs/gates/).

## Estado

| Gate | Descrição | Estado |
|---|---|---|
| U0 | Escopo e contratos | ✅ Aprovado |
| **U1** | Registry Ready | ✅ Aprovado e estabilizado |
| U2 | Installation Ready | ⏳ Planejado |
| U3 | Security Ready | ⏳ Planejado |
| U4 | Graph Ready | ⏳ Planejado |
| U5 | Zane Compatibility | ⏳ Planejado |

Detalhes em [`docs/gates/`](docs/gates/).

## Princípios não negociáveis

Estes vêm direto da especificação do Projeto Meta (`docs/especificacao-mestra.md`):

1. **Instalar ≠ ativar. Ativar ≠ executar.** Cada fase exige uma decisão explícita.
2. **Denial-by-default.** Nenhuma capability recebe permissão só por estar instalada.
3. **Hashes imutáveis.** Versão publicada nunca muda silenciosamente — correção gera nova versão.
4. **Namespaces isolam dados.** Um pack não lê dados de outro só por compartilhar registry.
5. **Falha parcial nunca fica em silêncio.** Rollback, quarentena, revogação — sempre disponíveis.
6. **ULTRON offline não derruba o consumidor.** Capacidades nativas permanecem.
7. **Schemas são executáveis.** Specs em prosa só valem se validadas por código.

## Arquitetura

```
Registry API        →  catalog, search, manifests, versions, compatibility
Validation Service  →  schema, deps, policy, security, sandbox
Package Store       →  artefatos imutáveis + SHA-256
Install/Activation  →  install ≠ activate; checkpoint para rollback
Graph/Portal        →  dependências, capabilities, health
```

Detalhes: [arquitetura mestra](https://github.com/restoffkaua08-afk/Documenta-oMeta/tree/main/docs/ultron/arquitetura).

## Desenvolvimento

```bash
# Setup
git clone https://github.com/restoffkaua08-afk/ultron.git
cd ultron
uv sync --extra dev

# Rodar testes
uv run pytest

# Lint + format
uv run ruff check src tests
uv run ruff format src tests

# Type check
uv run mypy src
```

## Licença

MIT — ver [`LICENSE`](LICENSE).

## Veja também

- [Projeto Meta](https://github.com/restoffkaua08-afk/documenta-oMeta) — programa de engenharia que origina o ULTRON
- [agentskills/agentskills](https://github.com/agentskills/agentskills) — formato aberto de Skill (Apache 2.0) que inspirou os schemas do ULTRON
