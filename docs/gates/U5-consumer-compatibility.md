# U5 — Consumer e Zane Compatibility

Status: **aprovado**. Gate: `ULTRON_ZANE_COMPATIBLE`.

## Entregue nesta etapa

- descoberta remota atualiza snapshot local atômico e determinístico;
- indisponibilidade de rede usa o último snapshot íntegro;
- snapshot possui SHA-256 e adulteração falha de forma fechada;
- ausência de servidor e cache gera erro tipado, nunca catálogo vazio silencioso;
- contrato é neutro para Claude, Codex, Zane e consumers próprios;
- consumer pode iniciar e usar capacidades nativas sem depender do Ultron.
- decorator `ResilientConsumerAdapter` funciona com qualquer implementação do contrato;
- instalação, ativação, desativação e remoção offline falham com erro tipado;
- leituras locais de instalações/status e capacidades nativas permanecem disponíveis;
- E2E comprova queda do Ultron sem mutação parcial ou perda das ferramentas nativas.
- tabela única vincula cada operação Python a REST e MCP sem divergência;
- todas as mutações exigem confirmação em qualquer transporte;
- `GET /api/v1/protocol` publica versão e bindings para descoberta universal.

## Evidência final

- servidor MCP Streamable HTTP executável e montado em `/mcp/`;
- descoberta MCP prova as oito operações da fonte única;
- catálogo MCP reutiliza o Registry da API;
- mutações MCP falham sem confirmação explícita;
- lifecycle persiste estado por organização e consumer com transações atômicas;
- resolução registra raiz e dependências sem executar código no servidor web;
- ativação é idempotente e remoção protege raiz, ativos e dependências em uso;
- blueprint Supabase vincula consumer à mesma organização por chave composta;
- cliente oficial MCP negocia sessão real com Uvicorn por `/mcp/`;
- E2E HTTP descobre oito tools, instala, ativa e comprova isolamento entre organizações.

O gate é aprovado porque a indisponibilidade do Ultron não impede o consumer de
iniciar, nenhuma mutação offline é simulada e o transporte remoto executável
preserva os mesmos contratos e confirmações do adapter local.
