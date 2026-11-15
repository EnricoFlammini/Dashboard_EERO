---
id: intro
title: 1. Introdução e Arquitetura
icon: book-open
summary: Visão geral da arquitetura auto-hospedada, segurança 2FA/OAuth, tema de 3 estados e 9 idiomas europeus.
---
### O que é o eero Custom Dashboard & Management Suite?
Esta aplicação web é uma plataforma completa e auto-hospedada de gestão e monitorização avançada para a sua rede Wi-Fi mesh **Amazon eero**.

#### Principais Características Arquiteturais:
1. **Auto-hospedado e Privacidade Total:** Executa num contentor Docker isolado no seu servidor local ou NAS (HomeLab). Imagem oficial multi-arquitetura no Docker Hub para `linux/amd64` e `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Autenticação Flexível (2FA OTP e Amazon OAuth2):** A ligação inicial à cloud eero utiliza o mecanismo oficial de dois fatores (palavra-passe única por SMS ou e-mail) ou o fluxo federado nativo **Amazon OAuth2 / PKCE** para contas associadas à Amazon.
3. **Persistência e Isolamento:** O token de sessão (`session.json`) e a base de dados SQLite (`metrics.db`) residem exclusivamente no volume persistente `./data:/app/data`.
4. **Poller em Memória de Latência Zero:** Um processo assíncrono em segundo plano consulta periodicamente a rede e mantém uma cache em memória RAM, garantindo navegação instantânea sem risco de limites de pedidos (rate limiting).
5. **Design Windows 11 Fluent, Tema de 3 Estados e Atalho `Ctrl+K`:** Interface moderna com suporte para modos Claro, Escuro e Sistema (deteção automática do SO via `prefers-color-scheme`), barra de pesquisa rápida global `Ctrl+K` / `Cmd+K` e barra lateral rebatível.
6. **Suporte Multilingue Europeu Completo (9 Idiomas):** Paridade total de catálogos no frontend e backend para inglês, italiano, francês, espanhol, alemão, neerlandês, português, polaco e grego.
