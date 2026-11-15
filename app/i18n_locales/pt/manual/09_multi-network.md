---
id: multi-network
title: 9. Gestão Multi-Rede e Comutação Rápida
icon: globe
summary: Suporte para contas eero com múltiplas localizações, alternância instantânea e persistência da rede escolhida.
---
### Gestão Multi-Rede e Comutação Rápida

* **Seletor Dinâmico no Cabeçalho (Windows 11 Fluent):** Caso a sua conta eero administre várias redes (ex.: Casa, Escritório, Segunda Habitação), um menu pendente exibe a contagem de nós e dispositivos ativos em cada localização.
* **Comutação Instantânea em Memória:** A seleção de outra rede alterna imediatamente a visualização sem necessidade de reiniciar o contentor nem reintroduzir credenciais. A cache RAM é renovada em tempo real.
* **Persistência da Rede Selecionada:** A localização ativa é guardada no ficheiro `session.json` e na base de dados SQLite local, mantendo-se após reinícios.
* **Suporte no Modo Demo:** Inclui duas localizações simuladas (*Casa Rossi Mesh 6E* e *Escritório Pro Mesh*) para demonstrar a gestão de várias redes.
* **Arquitetura da Rede Ativa e Simultaneidade:** A mudança aplica-se globalmente à instância do servidor. Para monitorizar em permanência várias redes lado a lado, podem ser executados dois contentores Docker independentes em portas distintas.
