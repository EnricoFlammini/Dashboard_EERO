---
id: reverse-enrichment
title: 16. Reverse Client Enrichment e Deteção IPv6 ULA
icon: arrows-right-left
summary: Enriquecimento bidirecional através de servidores DNS locais, descoberta de endereços IPv6 ULA e seguimento de novos clientes.
---
### Reverse Client Enrichment e Deteção IPv6 ULA

Em redes Dual-Stack, os equipamentos consultam habitualmente os servidores DNS locais através de endereços **IPv6 ULA** (*Unique Local Address*, prefixos `fc00::/7` e `fd00::/8`). Dado que este tráfego se mantém na Camada 2 local (Layer 2) sem passar pelo router WAN, a cloud eero não dispõe de visibilidade sobre estes endereços.

* **Reverse Client Enrichment via NDP e Ingestão REST:**
  - **Processo Automático de Deteção:** O serviço consulta com regularidade a tabela de vizinhança do sistema (NDP / ARP) e os servidores DNS locais para associar endereços ULA aos respetivos endereços MAC.
  - **API de Ingestão Externa (`POST /api/network/enrichment/neighbors`):** Permite a scripts e contentores adicionais submeter associações IP-MAC em tempo real.
  - **Sincronização Bidirecional:** Os endereços identificados são associados aos registos locais de DNS, permitindo que consultas anónimas passem a mostrar o nome legível do equipamento.
* **Distintivo Visual e Inspeção:**
  - Os clientes enriquecidos exibem o distintivo violeta **`ULA Enriched`** na tabela e na janela de detalhes.
* **Equipamentos Recentes e Distintivo "NEW":**
  - É guardada a data da primeira deteção (`first_seen`) de cada equipamento.
  - Os equipamentos identificados nas últimas 24 a 48 horas são assinalados com o distintivo verde-esmeralda **`NEW`**.
* **Limpeza e Manutenção Automática:**
  - Uma rotina noturna remove automaticamente registos ULA temporários inativos há mais de 30 dias para otimizar a base de dados.
