# U4 — Data e Graph Ready

Status: **em desenvolvimento**. Gate alvo: `ULTRON_GRAPH_READY`.

## Entregue nesta etapa

- store de dados exige contexto de organização em todas as operações;
- chaves são isoladas pela composição organização, namespace e identificador;
- consultas não possuem modo global que possa vazar dados entre organizações;
- identificadores são validados contra traversal e formatos ambíguos;
- lineage registra relações apenas entre registros existentes no mesmo isolamento;
- payload JSON é persistido de forma canônica e determinística.
- projeção consultável retorna nós e arestas em ordem determinística;
- travessia direcionada aceita raízes e profundidade máxima limitada;
- projeções nunca atravessam organização ou namespace.
- grafo operacional une manifests, dependências declaradas, consumers e instalações;
- arestas distinguem `depends_on`, `installed` e resolução exata `resolved_to`;
- instalações para consumers desconhecidos falham de forma fechada;
- vizinhança e serialização são determinísticas, independentemente da ordem de entrada.
- endpoint `GET /api/v1/graph` publica contrato JSON versionado;
- filtros por tipo de nó e relação mantêm apenas arestas com extremos visíveis;
- portal `/graph` reutiliza a mesma projeção operacional da API.
- busca combina texto, tipo, relação e limite controlado;
- texto pesquisa ID, nome e versão sem diferenciar maiúsculas;
- portal e API compartilham a mesma implementação de filtragem.
- retenção exige expiração explícita por registro e nunca assume prazo global;
- coleta usa plano imutável antes da aplicação e chaves exatas, sem exclusão ampla;
- arestas de lineage associadas são removidas na mesma transação;
- planos não podem ser aplicados por outra organização.

## Ainda necessário para o gate

- testes de escala e integração com o schema cloud.
