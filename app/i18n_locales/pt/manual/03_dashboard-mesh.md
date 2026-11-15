---
id: dashboard-mesh
title: 3. Painel Principal e Topologia Mesh
icon: network
summary: Pontuação de saúde da rede, cartões de estado dos nós e ações rápidas.
---
### Compreender o Painel de Controlo Principal

* **Pontuação de Saúde da Rede (1-100):** Avaliação sintética do estado da rede calculada com base na disponibilidade dos nós, presença do gateway e qualidade de sinal RSSI dos dispositivos clientes.
* **Cartões de Resumo:**
  - *Estado WAN:* IP público, operador, IPv6, barra de saúde e hora da última atualização.
  - *Gateway Principal:* Modelo, IP local, sub-rede, DNS, versão de firmware e nós ativos.
  - *Dispositivos Ligados:* Total e repartição por 6 GHz / 5 GHz / 2.4 GHz / Cabo, conhecidos, convidados e novos.
  - *Último Teste de Velocidade:* Download/upload, ping, classificação bufferbloat e gráfico recente.
* **Topologia dos Nós eero:**
  - *Nó Gateway:* O nó principal ligado diretamente ao modem ou terminal de fibra (ONT).
  - *Extensores Mesh / Beacons:* Nós secundários que expandem a cobertura sem fios.
  - *Tipo de Ligação (Backhaul):* Informa se os nós comunicam por cabo Ethernet ou ligação sem fios dedicada.
* **Ações Rápidas nos Nós:**
  - **Reiniciar Rede:** Envia um comando de reinício coordenado para toda a malha eero.
  - **Reiniciar Nó Individual:** Reinicia exclusivamente a unidade selecionada.
* **Funcionalidades Mesh Avançadas:**
  - **Extensores Amazon Echo "eero Built-in":** Deteção automática de colunas Echo compatíveis que operam como nós de extensão, identificadas pelo distintivo **`eero Built-in`**.
  - **Eleição de Gateway em Modo Bridge:** Identificação rigorosa da verdadeira porta de entrada através do indicador `is_primary_node` e vizinhos LLDP na porta WAN.
  - **Fotografias Oficiais dos Modelos eero:** Cada nó apresenta a imagem oficial do respetivo modelo de equipamento (eero Pro 6E, Max 7, 6+, Beacon, Outdoor 7, Echo Dot, etc.).
  - **Assistente IA e Teste de Posicionamento:** Diagnóstico interativo em tempo real via streaming SSE (`/api/network/assistant`), teste de propagação de sinal RF e estado da Guardian VPN.
