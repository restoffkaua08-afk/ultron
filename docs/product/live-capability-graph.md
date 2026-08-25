# Grafo vivo de capacidades

Esta especificação transforma a visão visual anexada em requisitos verificáveis.
O grafo é uma projeção do estado operacional real, não uma animação decorativa.

## Entidades visuais

- IAs/consumers: hubs maiores;
- agents: hubs médios;
- skills: nós menores;
- tools, MCPs e integrações: formas ou anéis distintos;
- workflows e packs: agrupadores navegáveis;
- conexões: dependência, uso, grant, compatibilidade ou evento.

## Interações

- pan, zoom progressivo e centralização;
- hover com nome, tipo, status e conexões;
- seleção com redução de ruído e painel lateral;
- arrastar/fixar/liberar nós e reorganizar clusters;
- filtros, busca textual e futura busca semântica;
- modo de fluxo para telemetria de ferramentas, autorizações e resultados.

O modo de fluxo mostra eventos operacionais, nunca raciocínio interno do modelo.

## Física e desempenho

- atração por relação e cluster;
- repulsão contra sobreposição;
- massa por importância/conectividade;
- conexões elásticas, inércia e movimento espontâneo sutil;
- simulação em worker e renderização Canvas/WebGL para redes grandes;
- níveis de detalhe: clusters distantes, nomes no zoom médio, nós no zoom alto;
- limite adaptativo de partículas e efeitos conforme GPU e preferência do usuário;
- suporte a `prefers-reduced-motion` e modo estático acessível.

## Direção visual

- fundo quase preto;
- vidro fosco limpo em painéis, sem excesso de blur;
- profundidade 2.5D e partículas discretas;
- linhas finas e pulsos luminosos apenas em conexões ativas;
- animações suaves, interrompíveis e baseadas em transformação/opacidade;
- contraste, foco por teclado e informação não dependente apenas de cor.

## Regra de consistência

Instalação cria nó; dependência cria aresta; grant cria relação; indisponibilidade
muda estado; remoção retira a projeção. Toda mudança vem da API e pode chegar por
Realtime. Posições fixadas pelo usuário são preferências separadas do grafo lógico.

## Escala de implementação

1. grafo 2D funcional e acessível;
2. clusters, física e painel de inspeção;
3. Realtime e telemetria visual;
4. busca semântica;
5. otimização WebGL e profundidade 2.5D.
