# U2 — Fundação de instalação reproduzível

Status: **em desenvolvimento**. Este documento registra a primeira entrega do U2;
ele não declara o gate completo.

## Entregue nesta etapa

- resolução recursiva e determinística de dependências;
- seleção da maior versão SemVer compatível;
- suporte a ranges exatos, `^`, `~`, curingas e especificadores PEP 440;
- rejeição de ciclos, conflitos e dependências obrigatórias ausentes;
- aviso não bloqueante para dependências opcionais ausentes;
- exclusão de versões revogadas da resolução;
- package store local endereçado por SHA-256;
- escrita atômica, conteúdo somente leitura e validação contra adulteração;
- lockfile canônico, determinístico e validado por schema;
- substituição atômica do lockfile;
- instalação transacional de grafos com versões e hashes exatos;
- preservação do estado anterior em falhas de integridade ou pacote incompleto;
- ativação e desativação explícitas, persistidas e idempotentes;
- reconciliação segura do estado quando o lockfile ou uma versão muda;
- remoção bloqueada para raiz, capability ativa ou dependência ainda utilizada;
- journal imutável de checkpoints e rollback explícito com validação SHA-256;
- substituições bem-sucedidas de instalação preservam o lockfile anterior no journal;
- API pública para resolver, instalar, consultar lockfile e package store.

## Invariantes de segurança

- resolver dependências não instala nem executa artefatos;
- armazenar um pacote nunca executa seu conteúdo;
- um hash informado no manifesto precisa corresponder aos bytes recebidos;
- conteúdo recuperado é novamente validado pelo SHA-256;
- versões revogadas nunca são escolhidas.
- instalar não importa entrypoints, não ativa capabilities e não concede permissões;
- o lockfile só muda depois que todo o grafo é verificado e armazenado.

## Ainda necessário para concluir o U2

- coleta de conteúdo sem referências;
- adaptadores de referência;
- testes end-to-end do ciclo de vida completo.

## Evidência desta etapa

- 140 testes automatizados aprovados;
- cobertura total de 91,39%;
- `ruff check`, `ruff format --check` e `mypy` em modo estrito;
- nenhuma permissão é concedida e nenhum código de pacote é executado.
