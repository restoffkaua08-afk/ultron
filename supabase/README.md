# Preparação do Supabase

`u4-data-graph.sql` é o candidato revisado de namespaces, lineage e retenção.
Ele agora usa chaves compostas para impedir relações entre organizações ou
namespaces diferentes.

`schema.sql` é um candidato versionado e ainda não foi aplicado. Revoga grants
automáticos, usa privilégios mínimos por tabela e mantém RLS em objetos expostos.
Quando um projeto Supabase exclusivo do Ultron
for conectado, a sequência obrigatória será:

1. criar uma branch de desenvolvimento do Supabase;
2. criar a migration com a CLI oficial e incorporar os candidatos SQL;
3. aplicar a migration no ambiente de desenvolvimento;
4. gerar os tipos TypeScript;
5. testar login, isolamento entre organizações e policies negativas;
6. executar advisors de segurança e performance;
7. corrigir todos os alertas relevantes;
8. ensaiar backup/restauração;
9. somente então promover a migration para produção.

O projeto Supabase atualmente visível na conexão está inativo e não foi
identificado como Ultron. Nenhum SQL será aplicado nele por suposição.

Configuração manual posterior:

- habilitar GitHub em Authentication > Providers;
- cadastrar URLs local, preview e produção;
- criar GitHub App com permissões mínimas;
- criar bucket privado para artefatos;
- preencher variáveis indicadas em `.env.example` na Vercel.

O `service_role`/secret key nunca deve ser colocado em variável `NEXT_PUBLIC_*`.
