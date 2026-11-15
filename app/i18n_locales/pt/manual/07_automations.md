---
id: automations
title: 7. Automações, QR Convidados, AdGuard Home, Telegram e Notificações
icon: zap
summary: Wi-Fi de convidados dinâmico com QR, sincronização DNS AdGuard Home, alertas Telegram/Webhook e resumo diário.
---
### Central de Automações e Funcionalidades Avançadas

O separador **Controlos e QR Convidados** reúne as ferramentas de gestão em painéis modulares:

1. **Smart Wi-Fi de Convidados com Código QR Dinâmico:**
   - Gera instantaneamente um código QR imprimível que se adapta ao tema ativo (fundo claro no modo diurno, ardósia escura no modo noturno).
   - Interruptor de 1 clique para ativar/desativar a rede de convidados com gerador de palavras-passe seguras.
2. **Sincronizador DNS para Múltiplos Motores:**
   - **Suporte para Várias Instâncias Heterogéneas:** Gestão simultânea de AdGuard Home, Pi-hole (v5 e v6) e Technitium DNS.
   - **Sincronização Contínua Automática:** Mantém nomes de anfitrião e reservas de IP alinhados com os novos dispositivos detetados.
   - **Limpeza Inteligente de Endereços e DNS Personalizado:** Resolução de conflitos de concessões reatribuídas, conformidade com RFC 1123 e suporte para **Custom e Split DNS** (`CUSTOM_DNS_SERVERS`, `CUSTOM_DNS_DOMAINS`) com prioridade IPv4 (`AF_INET`).
   - **Exclusão Individual:** Opção *"Excluir da sincronização DNS"* na ficha de cada equipamento.
3. **Notificações Telegram e Webhook:**
   - **Registo Persistente e Proteção Contra Inundações:** Isolamento de endereços MAC de teste para evitar falsos alarmes no arranque inicial.
   - **Novo Dispositivo Detetado:** Alerta imediato assim que um equipamento desconhecido acede à rede.
   - **Nó Mesh Desligado:** Notificação prioritária se um ponto de acesso eero perder a conectividade.
4. **Resumo Diário (Daily Digest):**
   - Envio automático a uma hora configurável (por omissão 21:00) com índice de saúde, clientes ligados e último teste de velocidade.
5. **Modo Gaming e Foco (Baixa Latência):**
   - Pausa com um único clique o tráfego de dispositivos secundários para eliminar oscilações de latência em jogos online ou videochamadas.
6. **Regras de Firewall IPv6 Pinhole:**
   - Gestão visual para abrir ou fechar portas TCP/UDP em equipamentos IPv6 específicos.
