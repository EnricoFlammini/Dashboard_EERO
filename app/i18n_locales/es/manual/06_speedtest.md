---
id: speedtest
title: 6. Test de Velocidad, Diagnóstico y Calidad de Señal Wi-Fi
icon: gauge
summary: Medición de ancho de banda, histórico de pruebas, análisis de señal RSSI y cobertura mesh.
---
### Diagnóstico de Velocidad y Cobertura Wi-Fi

* **Test de Velocidad Manual:** Pulse en **"Iniciar Speed Test"** para ejecutar una prueba en tiempo real de bajada, subida, latencia (ping) y jitter.
* **Pruebas Automáticas Programadas:** Posibilidad de programar mediciones periódicas en segundo plano (por ejemplo cada 12 horas) para evaluar la estabilidad de la conexión.
* **Gráficos Históricos y Estadísticas:** Evolución temporal de velocidad y ping con promedios, picos máximos y análisis de bufferbloat.
* **Calidad Wi-Fi y Cobertura Mesh:**
  - **Registro Histórico RSSI en dBm y Análisis Universal:** Muestreo preciso de los niveles de señal inalámbrica normalizados en el rango `[-120, -1] dBm`.
  - **Señal Promedio y Niveles de Calidad:** Indicador general y clasificación: *Excelente* (≥ -50 dBm), *Bueno* (-51 a -65 dBm), *Aceptable* (-66 a -75 dBm), *Crítico* (< -75 dBm).
  - **Actualización en Vivo y Lista de Señal Débil:** Incorporación en tiempo real de los clientes inalámbricos activos para asegurar que la lista de vigilancia **Weak Signal Watchlist** (`< -75 dBm`) esté siempre disponible.
  - **Gráfico Temporal Interactivo:** Visualización Chart.js a 24 horas o 7 días para cualquier cliente con vinculación dinámica del selector.
  - **Autorreparación SQLite en 3 Fases:** Recuperación automática de índices o reconstrucción de la base de datos tras reinicios imprevistos sin pérdida de configuración.
