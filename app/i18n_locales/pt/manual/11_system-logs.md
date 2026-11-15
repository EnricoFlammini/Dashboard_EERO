---
id: system-logs
title: 11. Registos do Sistema e Diagnóstico Avançado
icon: terminal
summary: Consola de registos em direto, níveis de detalhe dinâmicos, retenção, exportação e limpeza segura.
---
### Gestão de Registos do Sistema e Diagnóstico Avançado

O painel **Gestão de Registos e Diagnóstico** proporciona supervisão total da atividade da aplicação:

* **Interruptor Principal de Registo:** Ativa ou suspende a gravação de eventos na base de dados SQLite local e no ficheiro de registo no disco (`data/system.log`).
* **Níveis de Detalhe Dinâmicos sem Reinício:**
  - `DEBUG`: Registo pormenorizado de todas as chamadas de API e sincronizações.
  - `INFO`: Acompanhamento normal de eventos operacionais e ligações.
  - `WARNING`: Avisos sobre latência elevada ou degradação de sinal.
  - `ERROR`: Restrito a erros críticos e falhas de comunicação.
* **Período de Retenção Automático:** Escolha o período de conservação: 24h, 7 dias, 15 dias, 1 mês ou personalizado (com limpeza automática em segundo plano).
* **Consola de Registos em Tempo Real:** Terminal monospaçado de elevado contraste com pesquisa de texto, filtros de gravidade e atualização automática a cada 10 segundos.
* **Exportação e Limpeza:** Transferência em formato de texto padrão `.log` ou estruturado `.json`, com eliminação segura protegida por permissões RBAC.
