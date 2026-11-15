---
id: multi-channel-alerts
title: 14. Alertas Multicanal e Notificações de Emergência
icon: bell
summary: Despachador multicanal (Telegram, Discord, Webhook, Pushover, Ntfy) e alertas especializados de rede.
---
### Alertas Multicanal e Notificações de Emergência

O motor de notificações possibilita a distribuição paralela de eventos críticos por múltiplos canais:

* **Canais Suportados:**
  - **Bot do Telegram:** Alertas instantâneos em HTML com detalhes do nó e do equipamento.
  - **Webhook do Discord:** Notificações enriquecidas com cartões visuais e cores por gravidade.
  - **Pushover:** Avisos push prioritários para dispositivos móveis.
  - **Ntfy (sh) Nativo:** Suporte para servidores públicos `ntfy.sh` ou instâncias próprias com autenticação por token.
  - **Webhook Genérico:** Envio de dados em formato JSON para automações externas (Node-RED, n8n, Home Assistant).
* **Painéis de Configuração e Ocultação de Segredos:**
  - Cartões dedicados em *Definições -> Controlos* com botão de **Teste Imediato**.
  - Ocultação de tokens e endereços URL como `••••••••` para evitar divulgação acidental.
* **Alertas Especializados Integrados:**
  - **Degradação de Bufferbloat:** Aviso imediato perante aumentos acentuados de latência sob carga de rede.
  - **Anomalia no Nó Mesh:** Alerta de radar DFS ou enfraquecimento da ligação sem fios entre nós.
  - **Equipamento Desconhecido Ligado:** Notificação no momento em que um novo dispositivo se associa à rede.
  - **Nó Desligado:** Aviso prioritário em caso de perda de comunicação de qualquer ponto eero.
