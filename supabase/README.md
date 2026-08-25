# Preparação do Supabase

`u4-data-graph.sql` é o blueprint revisado de namespaces, lineage e retenção.
Depois de conectar o projeto, converta-o em migration oficial com a CLI e execute
Advisors e testes RLS. Os grants são explícitos devido aos defaults atuais da Data API.

`schema.sql` é um blueprint versionado e ainda não foi aplicado. Quando o projeto
for conectado, a sequência obrigatória será:

1. criar uma branch de desenvolvimento do Supabase;
2. aplicar o schema como migration nomeada;
3. gerar os tipos TypeScript;
4. testar login, isolamento entre organizações e policies negativas;
5. executar advisors de segurança e performance;
6. corrigir todos os alertas relevantes;
7. somente então promover a migration para produção.

Configuração manual posterior:

- habilitar GitHub em Authentication > Providers;
- cadastrar URLs local, preview e produção;
- criar GitHub App com permissões mínimas;
- criar bucket privado para artefatos;
- preencher variáveis indicadas em `.env.example` na Vercel.

O `service_role`/secret key nunca deve ser colocado em variável `NEXT_PUBLIC_*`.
