---
id: offline-first
title: 15. Arquitetura Offline-First e Recursos Locais
icon: shield-check
summary: Autonomia total com bibliotecas e tipos de letra locais, sem dependências de CDN externas e suporte air-gapped.
---
### Arquitetura Offline-First e Recursos Locais

A aplicação foi concebida sob uma abordagem de autonomia total, assegurando privacidade estrita, carregamentos imediatos e operação contínua mesmo perante cortes na ligação à Internet:

* **Inclusão Local de Todas as Bibliotecas:**
  - Todas as bibliotecas de frontend (Tailwind CSS, Alpine.js, Chart.js, Lucide Icons) são fornecidas a partir de `/app/static/vendor/`.
  - Zero pedidos a CDN externas: sem rastreio de terceiros e imunidade a bloqueadores de anúncios ou filtros de DNS.
* **Tipos de Letra Alojados Localmente:**
  - As fontes de elevada legibilidade **Inter** (interface de utilizador) e **JetBrains Mono** (consola e tabelas) estão incluídas no formato otimizado WOFF2 em `/app/static/fonts/`.
* **Resiliência em Redes Isoladas (Air-Gapped):**
  - O sistema arranca e opera normalmente em redes locais fechadas ou servidores sem qualquer acesso à Internet pública.
* **Progressive Web App (PWA) e Service Worker:**
  - O Service Worker integrado guarda os recursos essenciais em cache, permitindo utilizar a interface mesmo durante quebras temporárias de rede.
