# Preparação cloud — etapa 1

Status: **preparado, ainda não provisionado**.

O desenvolvimento continuou em [`U6-cloud-foundation.md`](U6-cloud-foundation.md).

## Entregue

- inventário completo de variáveis sem valores sensíveis;
- readiness programático para Supabase, GitHub App e MCP OAuth;
- endpoint que expõe somente flags, nunca credenciais;
- blueprint Postgres multi-tenant;
- RLS em todas as tabelas expostas;
- profiles, organizations, members, consumers, capabilities, versions,
  dependencies, grants, installations e audit events;
- índices para membership, descoberta, resolução, grants e auditoria;
- processo seguro para aplicar e verificar o schema quando conectado.

## Bloqueios intencionais

- o schema não é aplicado sem projeto/branch Supabase;
- frontend Next.js não é publicado sem dependências fixadas e build aprovado;
- API cloud não troca SQLite por Supabase antes do adapter e dos testes;
- nenhuma credencial real pertence ao repositório.
