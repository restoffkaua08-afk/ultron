# U6 — Fundação cloud real

Status: **em andamento; gate não aprovado**.

## Primeiro incremento

O primeiro incremento revisa o candidato SQL antes de qualquer aplicação:

- privilégios padrão de novos objetos são revogados;
- grants da Data API são mínimos e específicos por tabela;
- RLS permanece habilitado em todas as tabelas expostas;
- consumers usados em auditoria são presos à mesma organização;
- owners de namespace são presos à mesma organização;
- lineage usa chaves estrangeiras compostas por organização e namespace;
- testes contratuais impedem regressão desses invariantes.

## Evidência disponível

- baseline anterior: `a34aeaf`;
- schema candidato: `supabase/schema.sql`;
- extensão de dados/grafo: `supabase/u4-data-graph.sql`;
- testes: `tests/contract/test_supabase_u6_foundation.py`.

## Limites desta entrega

Esta entrega não é uma migration oficial e não aprova U6 porque:

- a CLI Supabase não está disponível neste ambiente;
- o projeto Supabase acessível está inativo e não foi identificado como Ultron;
- não houve aplicação em Postgres real;
- RLS ainda não foi testado com usuários de duas organizações reais;
- Advisors ainda não foram executados após DDL;
- backup e restauração ainda não foram ensaiados.

## Próximo incremento obrigatório

1. criar ou identificar um projeto Supabase de desenvolvimento exclusivo do Ultron;
2. usar a CLI oficial para criar a migration nomeada;
3. aplicar o schema em desenvolvimento;
4. executar testes positivos e negativos de RLS;
5. executar Advisors de segurança e performance;
6. corrigir todos os achados relevantes;
7. provar dump/restore ou backup/restauração conforme o plano escolhido.

O gate `ULTRON_CLOUD_DATA_READY` permanece fechado até todas essas evidências
existirem.

