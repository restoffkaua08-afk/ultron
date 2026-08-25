# Identidade, contas e acesso

## Entrada do usuário

O acesso web exige uma conta ULTRON criada pelo Supabase Auth. A primeira forma
de entrada será **Continuar com GitHub**, usando OAuth com PKCE e sessão em cookie
seguro no servidor.

O login social identifica a pessoa, mas não concede acesso automático a
repositórios, organizações, agents, skills ou secrets.

## Integração com GitHub

Existem duas responsabilidades separadas:

1. **Supabase Auth + GitHub OAuth:** login e identidade básica;
2. **GitHub App do ULTRON:** acesso opcional a repositórios selecionados.

A GitHub App usa permissões mínimas, tokens curtos e instalação por conta ou
organização. Tokens de provider e installation tokens ficam somente no servidor,
criptografados ou em secret storage apropriado, nunca em `user_metadata`.

## Modelo multi-tenant

- `profiles`: dados públicos do usuário;
- `organizations`: tenants pessoais ou de equipe;
- `organization_members`: vínculo e papel;
- `ai_consumers`: Claude, Codex, Zane ou outro cliente conectado;
- `capability_grants`: quais capacidades cada consumer pode descobrir ou usar;
- `installations`: estado instalado/ativo por organização e consumer;
- `audit_events`: eventos append-only relevantes.

Papéis iniciais: `owner`, `admin`, `developer`, `viewer`.

## Regras obrigatórias

- RLS habilitada em toda tabela exposta;
- políticas combinam `TO authenticated` com membership/ownership;
- autorização usa dados do banco ou `app_metadata`, nunca `user_metadata`;
- `service_role` é exclusivamente server-side;
- instalar não significa ativar; ativar não concede permissão;
- grants possuem scopes, expiração, revogação e trilha de auditoria;
- cada token de IA possui audience específica do ULTRON.
