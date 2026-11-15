---
id: auth-flow
title: 2. Autenticação e Gestão de Acessos (RBAC / 2FA)
icon: key
summary: Configuração inicial do administrador (Zero-Default), funções locais RBAC e procedimento de início de sessão 2FA da eero.
---
### Gestão de Acessos, Configuração Inicial e Autenticação

#### 1. Configuração Inicial do Administrador (Segurança Zero-Default)
No primeiro arranque, o sistema aplica uma política de segurança estrita sem palavras-passe predefinidas:
- **Assistente de Configuração:** Se ainda não existirem utilizadores na base de dados, é apresentado automaticamente um ecrã completo para definição do nome de utilizador e de uma palavra-passe segura.
- **Configuração Automatizada (Headless Docker):** Em implementações automáticas, é possível predefinir as variáveis de ambiente `ADMIN_USER` e `ADMIN_PASSWORD` no ficheiro `.env` ou `docker-compose.yml`. A conta de administrador será criada dispensando o assistente.
- **Funções e Permissões Granulares (RBAC):** Na secção *Definições -> Utilizadores e Permissões*, o administrador pode criar contas adicionais com funções específicas (`Admin`, `Operator`, `Viewer`) e ajustar direitos operacionais.

#### 2. Autenticação com a Cloud eero (2FA OTP)
Após a conclusão do acesso local (ou se a autenticação local não for exigida):
1. **Pedido do Código OTP:** Introduza o e-mail ou número de telefone associado à sua conta eero e clique em **"Enviar Código OTP"**.
2. **Verificação do Código:** Introduza o código de 6 dígitos recebido por SMS ou e-mail e confirme.
3. **Guardar Sessão:** O token verificado é armazenado em `/app/data/session.json` com permissões estritas `0600`, mantendo-se ativo após reinícios do contentor.
4. **Modo Demo e Alternador Rápido:** Explore as funcionalidades sem credenciais reais através do botão **"✨ Modo Demo"** ou definindo `DEMO_MODE=true`.

#### 3. Início de Sessão Nativo Amazon OAuth2 / PKCE
Para contas eero associadas a um perfil Amazon, o painel disponibiliza o fluxo oficial **Amazon OAuth2 com PKCE S256 (RFC 7636)**:
1. **Início de Sessão Amazon:** Clique em **"🛒 Iniciar sessão com a Amazon"** no diálogo de acesso para iniciar o processo seguro PKCE.
2. **Autorização no Navegador:** Inicie sessão na Amazon e conceda permissão; será então redirecionado para o endereço `/ap/maplanding`.
3. **Associação Imediata:** Copie o URL de redirecionamento ou o parâmetro `code`, cole-o no campo indicado e confirme em **"Associar conta eero"**.

#### 4. Segurança Global e Aplicação de `REQUIRE_LOCAL_AUTH`
Em ambientes de rede partilhados, a ativação de `REQUIRE_LOCAL_AUTH=true` no ficheiro `.env` garante:
- Proteção de todos os pontos de extremidade da API (`/api/*`) e métricas do Prometheus (`/metrics`) exigindo uma sessão autenticada.
- Apenas as rotas essenciais de verificação de estado e autenticação (`/api/health`, `/api/auth/local/*`, `/api/system/language`) permanecem públicas.
