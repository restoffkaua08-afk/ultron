# Integração universal com consumidores de IA

## Princípio

O ULTRON não terá integração privilegiada com um fornecedor. Claude, Codex,
ChatGPT, Zane e clientes futuros consomem o mesmo protocolo e o mesmo modelo de
permissões.

## Superfícies

### REST versionado

Para SDKs, automações e consumidores que não implementam MCP:

- descobrir capabilities e versões;
- consultar schemas, dependências e compatibilidade;
- gerar plano e lockfile;
- solicitar instalação, ativação ou remoção;
- consultar grants, health e auditoria.

### MCP remoto

Para IAs compatíveis com Model Context Protocol:

- resources: catálogo, manifests, schemas e estado permitido;
- tools: busca, resolução, planejamento e lifecycle com confirmação;
- prompts: somente capacidades explicitamente publicadas como prompt;
- OAuth 2.1 com PKCE, Protected Resource Metadata e audience validation.

O servidor MCP não repassa o token recebido para GitHub, Supabase ou outro
upstream. Cada integração usa credencial própria e escopo mínimo.

### Adapter local

Consumers offline ou embarcados, como o futuro Zane, podem usar o protocolo
Python existente e sincronizar apenas metadados autorizados quando houver rede.

## Compatibilidade do protocolo local

- versão atual: `1.0.0`;
- consumers declaram ID, versão SemVer e ao menos um transporte;
- versões do mesmo major negociam compatibilidade sem depender do fornecedor;
- mudança de major falha com `PROTOCOL_INCOMPATIBLE` e contexto auditável;
- a suíte `verify_consumer` valida catálogo e instalações sem executar mutações;
- referências inválidas, duplicadas ou com kind desconhecido são rejeitadas.

Claude, Codex, Zane e clientes próprios seguem o mesmo handshake. REST e MCP
serão apenas transportes deste contrato, não protocolos de lifecycle paralelos.

## Descoberta e uso

1. consumer autentica;
2. ULTRON identifica tenant e scopes;
3. catálogo retorna somente capabilities visíveis;
4. consumer solicita plano;
5. policy avalia permissões e riscos;
6. usuário aprova ações sensíveis;
7. execução ocorre no runtime do consumer, não no Registry;
8. eventos operacionais são auditados sem expor raciocínio interno da IA.
