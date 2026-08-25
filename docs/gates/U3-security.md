# U3 — Segurança e supply chain

Status: **em desenvolvimento**. Gate alvo: `ULTRON_SECURITY_READY`.

## Entregue nesta etapa

- pipeline de validação composto por regras determinísticas;
- verificação SHA-256 antes da admissão;
- exigência de commit completo para fontes Git;
- exigência de digest SHA-256 para imagens OCI;
- detecção de risco subestimado em permissões sensíveis;
- aviso obrigatório para aprovação de capabilities de alto risco;
- status persistido `quarantined` com evento de auditoria;
- resolver e instalador rejeitam versões em quarentena;
- pipeline inspeciona bytes e metadados, mas nunca executa o pacote.
- assinatura Ed25519 vincula publisher, manifest canônico e hash do artefato;
- trust store persiste somente chaves públicas com escrita atômica;
- chaves revogadas falham de forma fechada;
- fontes remotas sem assinatura válida entram em quarentena;
- artefatos locais não assinados preservam compatibilidade com aviso explícito.

## Ainda necessário para o gate

- política de promoção e saída de quarentena;
- sandbox de execução separado do Registry;
- revogação propagada para instalações existentes;
- auditoria encadeada e proteção adicional contra adulteração.

## Evidência desta etapa

- 158 testes automatizados aprovados;
- cobertura total de 91,61%;
- `ruff check`, `ruff format --check`, `mypy` estrito e build aprovados;
- nenhum pacote foi importado ou executado durante a validação.
