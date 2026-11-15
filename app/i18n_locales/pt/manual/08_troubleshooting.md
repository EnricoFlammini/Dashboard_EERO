---
id: troubleshooting
title: 8. Resolução de Problemas, Atualizações e FAQ
icon: wrench
summary: Perguntas frequentes sobre telemetria, atualização automática Docker, segurança, cópias de segurança e manutenção.
---
### Perguntas Frequentes e Resolução de Anomalias

* **Como funciona a atualização automática do contentor Docker a partir da aplicação?**
  - A plataforma verifica periodicamente novas versões no Docker Hub e GitHub Releases.
  - Se o socket do Docker (`/var/run/docker.sock`) estiver mapeado, clicar em **"Atualizar Contentor Agora"** transfere a nova imagem e recria o contentor preservando o volume `./data`.
* **Que informações de dispositivos provêm diretamente da eero?**
  - Estado da ligação, endereço IP local, endereço MAC, nó de ligação, banda de frequência (**2.4 GHz, 5 GHz, 6 GHz ou Cabo**), canal, intensidade de sinal em **dBm** e débito físico de ligação (**PHY Link Rate**).
* **Segurança e Proteção de Dados:**
  - **Proteção CORS e CSRF:** Acesso de origens cruzadas restrito por predefinição e validação de pedidos mutantes.
  - **Ocultação de Palavras-passe:** As palavras-passe de Wi-Fi são eliminadas das respostas públicas da API.
  - **Permissões Rigorosas:** O ficheiro `session.json` é protegido com permissões restritas `0600`.
* **O que fazer se a sessão eero expirar?**
  - Clique em **Terminar Sessão** na barra lateral e repita o processo de autenticação (SMS, e-mail ou Amazon OAuth2).
* **Como fazer uma cópia de segurança das definições locais?**
  - Todas as personalizações (nomes, categorias, notas, históricos) residem em `./data/metrics.db`. Basta efetuar uma cópia da pasta `./data`.
* **Por que motivo a autenticação por SMS/e-mail devolve o erro 401?**
  - Se a sua conta eero foi associada a um perfil Amazon, utilize a opção **"Iniciar sessão com a Amazon (OAuth2 / PKCE)"** no ecrã de início de sessão.
* **Como configurar o Custom e Split DNS?**
  - Defina as variáveis de ambiente `CUSTOM_DNS_SERVERS` e `CUSTOM_DNS_DOMAINS` para resolver domínios locais diretamente através dos seus servidores DNS internos.
* **Como funciona a autorrecuperação SQLite?**
  - Perante falhas de ficheiro decorrentes de cortes repentinos de energia, a rotina de 3 fases (`REINDEX`, reconstrução de tabelas e ficheiros) restaura a base de dados mantendo uma cópia `.corrupt.bak`.
