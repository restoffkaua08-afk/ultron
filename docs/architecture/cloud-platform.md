# Arquitetura cloud do ULTRON

Status: **decisão arquitetural aprovada para implementação incremental**.

## Objetivo

Hospedar o ULTRON sem perder seu modo local, permitir contas e organizações e
expor o mesmo catálogo de capacidades para interfaces humanas e consumidores de IA.

## Componentes

| Componente | Tecnologia | Responsabilidade |
|---|---|---|
| Web | Next.js App Router na Vercel | autenticação, gestão e grafo visual |
| API | FastAPI em Vercel Functions | contratos REST versionados e núcleo Python |
| Banco | Supabase Postgres | tenants, catálogo, grants, instalações e auditoria |
| Identidade | Supabase Auth | sessão web e entrada social pelo GitHub |
| Artefatos | Supabase Storage | pacotes imutáveis, assinaturas e assets |
| Eventos | Supabase Realtime | estados e telemetria operacional do grafo |
| Busca | Postgres FTS; depois pgvector | busca textual e semântica por capacidade |
| IA | REST + MCP remoto | integração neutra com Claude, Codex, Zane e outros |

## Modos de operação

- **local:** SQLite + package store local; funciona sem cloud;
- **cloud:** Supabase + Vercel; multiusuário e acessível remotamente;
- **híbrido:** catálogo cloud com cache e instalações locais por consumer.

O backend usa portas de persistência. SQLite e Supabase são adapters; regras de
manifest, integridade, resolução, lockfile e lifecycle permanecem no núcleo.

## Limites operacionais

- tarefas HTTP curtas podem rodar em Vercel Functions;
- análise pesada, sandbox e execução de artefatos não devem ocorrer na função web;
- trabalhos longos usarão workers/workflows duráveis em etapa posterior;
- nenhum token de provedor ou `service_role` chega ao navegador;
- todas as tabelas expostas usam RLS e ownership por organização.

## Sequência de entrega

1. contratos cloud e schema multi-tenant;
2. Next.js shell + GitHub sign-in;
3. adapter Supabase do Registry;
4. API REST autenticada;
5. servidor MCP remoto OAuth 2.1;
6. grafo funcional e Realtime;
7. deploy e observabilidade.
