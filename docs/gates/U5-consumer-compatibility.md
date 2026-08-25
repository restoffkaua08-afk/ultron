# U5 — Consumer e Zane Compatibility

Status: **em desenvolvimento**. Gate alvo: `ULTRON_ZANE_COMPATIBLE`.

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

## Ainda necessário

- contrato MCP/REST equivalente e prova final do gate.
