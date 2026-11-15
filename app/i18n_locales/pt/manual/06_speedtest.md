---
id: speedtest
title: 6. Teste de Velocidade, Diagnóstico e Qualidade de Sinal Wi-Fi
icon: gauge
summary: Medição de largura de banda, histórico de testes, análise de sinal RSSI e cobertura mesh.
---
### Diagnóstico de Desempenho e Cobertura Wi-Fi

* **Teste de Velocidade Manual:** Clique em **"Iniciar Teste de Velocidade"** para realizar uma medição em tempo real de download, upload, ping e jitter.
* **Testes Automáticos Agendados:** O sistema permite programar testes periódicos em segundo plano (por exemplo, a cada 12 horas) para monitorizar a estabilidade da ligação.
* **Gráficos de Histórico e Estatísticas:** Curvas temporais Chart.js de velocidade e latência com médias e avaliação de bufferbloat.
* **Qualidade Wi-Fi e Cobertura Mesh:**
  - **Registo Histórico RSSI em dBm e Conversão Universal:** Amostragem precisa dos níveis de sinal convertidos para o intervalo numérico padrão `[-120, -1] dBm`.
  - **Sinal Médio e Escalas de Qualidade:** Indicador de qualidade global e classificação: *Excelente* (≥ -50 dBm), *Bom* (-51 a -65 dBm), *Razoável* (-66 a -75 dBm), *Crítico* (< -75 dBm).
  - **Atualização em Tempo Real e Lista de Sinal Fraco:** A agregação em direto dos clientes sem fios garante que a lista **Weak Signal Watchlist** (`< -75 dBm`) está sempre preenchida.
  - **Gráfico Interativo por Dispositivo:** Visualização a 24 horas ou 7 dias para qualquer cliente selecionado.
  - **Autorrecuperação SQLite em 3 Etapas:** Mecanismo automático de reparação de índices ou reconstrução de ficheiros após encerramentos repentinos sem perda de dados.
