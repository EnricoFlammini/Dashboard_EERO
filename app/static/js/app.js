/**
 * eero Custom Dashboard & Management Suite - Frontend Application Logic
 * Powered by Alpine.js & Chart.js
 */

document.addEventListener('alpine:init', () => {
  Alpine.data('eeroApp', () => ({
    // Navigation State
    currentTab: 'overview',
    
    // Auth & Session State
    isAuthenticated: false,
    isDemoMode: false,
    userAccount: null,
    loginIdentifier: '',
    otpCode: '',
    tempUserToken: null,
    otpSent: false,
    authLoading: false,
    authError: '',

    // Live Dashboard & Network State
    network: {},
    eeros: [],
    devices: [],
    healthScore: 100,
    realtimeMetrics: {
      current_download_mbps: 0,
      current_upload_mbps: 0,
      total_rx_gb: 0,
      total_tx_gb: 0,
      connected_clients_count: 0
    },
    lastPollTime: null,
    pollingTimer: null,

    // Bandwidth Historian State
    selectedWanRange: 24, // 24h, 168 (7d), 720 (30d)
    wanTotalGb: 0,
    wanHistoryData: [],
    wanChartInstance: null,
    
    selectedHogsRange: 24,
    topHogs: [],
    hogsChartInstance: null,

    // Device Management State
    deviceSearchQuery: '',
    selectedBandFilter: 'all',
    selectedNodeFilter: 'all',
    selectedCategoryFilter: 'all',
    showConnectedOnly: false,
    
    selectedDevice: null,
    deviceDetailTab: 'info',
    deviceMetadataForm: {
      custom_name: '',
      custom_icon: 'device',
      category: 'Altro',
      custom_notes: '',
      static_ip: '',
      is_favorite: false,
      is_low_latency_target: false
    },
    deviceTrafficHistory: [],
    deviceForwards: [],
    showDeviceModal: false,

    // Port Forwarding Global State
    allForwards: [],
    newForwardForm: {
      ip: '',
      port_from: '',
      port_to: '',
      protocol: 'tcp',
      description: 'Custom Service'
    },
    showForwardModal: false,

    // Speed Test State
    speedtestRunning: false,
    speedtestProgress: 0,
    speedtestStats: {},
    speedtestHistory: [],
    speedtestChartInstance: null,
    lastSpeedtestResult: null,

    // Controls & Automations State
    guestNetwork: {
      enabled: false,
      name: '',
      password: ''
    },
    guestQrCodeUrl: '',
    focusModeActive: false,
    focusModeTargetCount: 0,
    
    nightMode: {
      enabled: false,
      start_time: '23:00',
      end_time: '07:00'
    },
    
    notificationSettings: {
      telegram_enabled: false,
      telegram_bot_token: '',
      telegram_chat_id: '',
      webhook_enabled: false,
      webhook_url: ''
    },
    alertsList: [],

    // Built-in User Manual State
    manualSections: [],
    manualSearchQuery: '',
    selectedManualSection: null,
    showHelpModal: false,
    helpModalTitle: '',
    helpModalContent: '',

    // Changelog Modal State
    showChangelogModal: false,
    changelogContent: '',
    changelogVersion: '1.00.01',
    changelogLoading: false,

    // Toast Notification System
    toasts: [],

    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    async init() {
      console.log("Initializing eero Custom Dashboard application...");
      await this.checkAuthStatus();
      await this.loadManualSections();

      if (this.isAuthenticated) {
        await this.refreshAllData();
        this.startPolling();
      }

      // Reattività cambio tab con rendering forzato e resize automatico
      this.$watch('currentTab', (tab) => {
        this.setTab(tab);
      });
    },

    async setTab(tab) {
      this.currentTab = tab;
      if (tab === 'metrics') {
        setTimeout(async () => {
          await this.loadWanHistory();
          await this.loadTopHogs();
        }, 50);
      } else if (tab === 'speedtest') {
        setTimeout(async () => {
          await this.loadSpeedtestData();
        }, 50);
      } else if (tab === 'devices') {
        await this.fetchDevices();
      }
    },

    // =========================================================================
    // AUTHENTICATION
    // =========================================================================
    async checkAuthStatus() {
      try {
        const res = await fetch('/api/auth/status');
        const data = await res.json();
        this.isAuthenticated = data.authenticated;
        this.isDemoMode = data.demo_mode;
        this.userAccount = data.account;
      } catch (err) {
        console.error("Auth status check failed:", err);
      }
    },

    async requestOtp() {
      if (!this.loginIdentifier) return;
      this.authLoading = true;
      this.authError = '';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ login: this.loginIdentifier })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Richiesta OTP fallita');
        if (data.user_token) {
          this.tempUserToken = data.user_token;
        }
        this.otpSent = true;
        this.showToast("Codice Inviato", "Inserisci il codice a 6 cifre ricevuto via SMS/Email.", "info");
      } catch (err) {
        this.authError = err.message;
        this.showToast("Errore Login", err.message, "error");
      } finally {
        this.authLoading = false;
      }
    },

    async verifyOtp() {
      if (!this.otpCode) return;
      this.authLoading = true;
      this.authError = '';
      try {
        const res = await fetch('/api/auth/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: this.otpCode, user_token: this.tempUserToken })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Verifica OTP fallita');
        
        this.isAuthenticated = true;
        this.otpSent = false;
        this.otpCode = '';
        this.tempUserToken = null;
        this.showToast("Accesso Riuscito", "Connessione con eero stabilita.", "success");
        await this.refreshAllData();
        this.startPolling();
      } catch (err) {
        this.authError = err.message;
        this.showToast("Errore OTP", err.message, "error");
      } finally {
        this.authLoading = false;
      }
    },

    async startDemoSession() {
      this.authLoading = true;
      this.loginIdentifier = "demo@eero.lan";
      this.otpCode = "123456";
      await this.verifyOtp();
    },

    async logout() {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
        this.isAuthenticated = false;
        this.isDemoMode = false;
        this.userAccount = null;
        if (this.pollingTimer) clearInterval(this.pollingTimer);
        this.showToast("Disconnesso", "Sessione terminata con successo.", "info");
      } catch (err) {
        console.error("Logout error:", err);
      }
    },

    // =========================================================================
    // DATA FETCHING & POLLING
    // =========================================================================
    startPolling() {
      if (this.pollingTimer) clearInterval(this.pollingTimer);
      // Polling rapido metriche live ogni 3s
      let count = 0;
      this.pollingTimer = setInterval(async () => {
        if (this.isAuthenticated) {
          await this.fetchRealtimeMetrics();
          count++;
          if (count % 3 === 0) {
            await this.fetchOverview();
            if (this.currentTab === 'devices') {
              await this.fetchDevices();
            } else if (this.currentTab === 'metrics') {
              await this.loadWanHistory();
              await this.loadTopHogs();
            }
          }
        }
      }, 3000);
    },

    isRefreshing: false,

    async manualRefresh() {
      if (this.isRefreshing) return;
      this.isRefreshing = true;
      try {
        await fetch('/api/network/refresh', { method: 'POST' });
        await this.refreshAllData();
        if (this.currentTab === 'metrics') {
          await this.loadWanHistory();
          await this.loadTopHogs();
        } else if (this.currentTab === 'speedtest') {
          await this.loadSpeedtestData();
        }
        this.showToast("Dati Aggiornati", "Dashboard sincronizzata in tempo reale con la rete eero.", "success");
      } catch (err) {
        this.showToast("Errore Aggiornamento", err.message, "error");
      } finally {
        setTimeout(() => { this.isRefreshing = false; }, 400);
      }
    },

    async refreshAllData() {
      await Promise.all([
        this.fetchOverview(),
        this.fetchRealtimeMetrics(),
        this.fetchDevices(),
        this.fetchGuestNetwork(),
        this.fetchFocusMode(),
        this.fetchNightMode(),
        this.fetchNotificationSettings(),
        this.fetchAlerts(),
      ]);
    },

    async fetchOverview() {
      try {
        const res = await fetch('/api/network/overview');
        const json = await res.json();
        if (json.status === 'success') {
          this.network = json.data.network || {};
          this.eeros = json.data.eeros || [];
          this.healthScore = json.data.health_score || 100;
          this.lastPollTime = json.data.last_poll_time;
        }
      } catch (err) {
        console.error("Fetch overview error:", err);
      }
    },

    async fetchRealtimeMetrics() {
      try {
        const res = await fetch('/api/metrics/realtime');
        const json = await res.json();
        if (json.status === 'success') {
          this.realtimeMetrics = json;
        }
      } catch (err) {
        console.error("Fetch realtime error:", err);
      }
    },

    async fetchDevices() {
      try {
        const res = await fetch('/api/devices');
        const json = await res.json();
        if (json.status === 'success') {
          this.devices = json.devices || [];
        }
      } catch (err) {
        console.error("Fetch devices error:", err);
      }
    },

    // =========================================================================
    // NETWORK & NODES ACTIONS
    // =========================================================================
    async rebootNetwork() {
      if (!confirm("Sei sicuro di voler riavviare l'intera rete mesh eero? La connessione cadrà per 2-3 minuti.")) return;
      try {
        const res = await fetch('/api/network/reboot', { method: 'POST' });
        const data = await res.json();
        this.showToast("Riavvio Rete", data.message || "Comando inviato.", "info");
      } catch (err) {
        this.showToast("Errore Riavvio", err.message, "error");
      }
    },

    async rebootEero(eero) {
      const eid = eero.id || eero.serial;
      if (!confirm(`Riavviare il nodo '${eero.name || eid}'?`)) return;
      try {
        const res = await fetch(`/api/network/eeros/${eid}/reboot`, { method: 'POST' });
        const data = await res.json();
        this.showToast("Riavvio Nodo", data.message || `Riavvio nodo ${eero.name} avviato.`, "info");
      } catch (err) {
        this.showToast("Errore Riavvio", err.message, "error");
      }
    },

    async toggleEeroLed(eero) {
      const eid = eero.id || eero.serial;
      const targetState = !eero.led_on;
      try {
        await fetch(`/api/network/eeros/${eid}/led`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ led_on: targetState })
        });
        eero.led_on = targetState;
        this.showToast("LED Aggiornato", `LED ${eero.name}: ${targetState ? 'Acceso' : 'Spento'}`, "success");
      } catch (err) {
        this.showToast("Errore LED", err.message, "error");
      }
    },

    async toggleAllLeds(ledOn) {
      try {
        await fetch('/api/network/leds', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ led_on: ledOn })
        });
        this.eeros.forEach(e => e.led_on = ledOn);
        this.showToast("Tutti i LED", `Tutti i LED impostati a: ${ledOn ? 'Accesi' : 'Spenti'}`, "success");
      } catch (err) {
        this.showToast("Errore LED", err.message, "error");
      }
    },

    // =========================================================================
    // BANDWIDTH CHARTS & HISTORIAN
    // =========================================================================
    renderWanChart(labels, dlData, ulData) {
      const canvas = document.getElementById('wanTrafficChart');
      if (!canvas) return;
      if (this.wanChartInstance) {
        this.wanChartInstance.destroy();
        this.wanChartInstance = null;
      }

      const p = canvas.parentElement;
      if (p) {
        canvas.width = p.clientWidth || 800;
        canvas.height = p.clientHeight || 320;
      }

      const ctx = canvas.getContext('2d');
      this.wanChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Download (Mbps)',
              data: dlData,
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              borderWidth: 2,
              fill: true,
              tension: 0.35,
              pointRadius: 1,
              pointHoverRadius: 5
            },
            {
              label: 'Upload (Mbps)',
              data: ulData,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.10)',
              borderWidth: 2,
              fill: true,
              tension: 0.35,
              pointRadius: 1,
              pointHoverRadius: 5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          plugins: {
            legend: {
              labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
            },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              titleColor: '#38bdf8',
              bodyColor: '#f8fafc',
              borderColor: 'rgba(255, 255, 255, 0.1)',
              borderWidth: 1,
              padding: 10
            }
          },
          scales: {
            x: {
              ticks: { color: '#64748b', maxTicksLimit: 8 },
              grid: { color: 'rgba(255, 255, 255, 0.05)' }
            },
            y: {
              ticks: { color: '#64748b' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' }
            }
          }
        }
      });
    },

    formatLocalTime(ts) {
      if (!ts) return '';
      let str = String(ts).trim();
      if (!str.endsWith('Z') && !str.includes('+')) {
        str = str.replace(' ', 'T') + 'Z';
      }
      const dt = new Date(str);
      return dt.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', hour12: false });
    },

    formatLocalDateTime(ts) {
      if (!ts) return '';
      let str = String(ts).trim();
      if (!str.endsWith('Z') && !str.includes('+')) {
        str = str.replace(' ', 'T') + 'Z';
      }
      const dt = new Date(str);
      return dt.toLocaleDateString('it-IT', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
    },

    async loadWanHistory(hours = null) {
      if (hours) this.selectedWanRange = hours;
      try {
        const res = await fetch(`/api/metrics/wan?hours=${this.selectedWanRange}`);
        const json = await res.json();
        if (json.status === 'success') {
          this.wanTotalGb = json.total_gb_transferred || 0;
          this.wanHistoryData = json.history || [];

          if (this.wanHistoryData.length > 0) {
            const labels = this.wanHistoryData.map(d => this.formatLocalTime(d.timestamp));
            const dl = this.wanHistoryData.map(d => d.download_speed_mbps);
            const ul = this.wanHistoryData.map(d => d.upload_speed_mbps);
            this.renderWanChart(labels, dl, ul);
          }
        }
      } catch (err) {
        console.error("Load WAN history error:", err);
      }
    },

    renderHogsChart(labels, data, isMb = false) {
      const canvas = document.getElementById('topHogsChart');
      if (!canvas) return;
      if (this.hogsChartInstance) {
        this.hogsChartInstance.destroy();
        this.hogsChartInstance = null;
      }

      const p = canvas.parentElement;
      if (p) {
        canvas.width = p.clientWidth || 400;
        canvas.height = p.clientHeight || 280;
      }

      const unit = isMb ? 'MB' : 'GB';
      const ctx = canvas.getContext('2d');
      this.hogsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: `Consumo Dati (${unit})`,
            data: data,
            backgroundColor: [
              'rgba(56, 189, 248, 0.85)',
              'rgba(99, 102, 241, 0.85)',
              'rgba(16, 185, 129, 0.85)',
              'rgba(245, 158, 11, 0.85)',
              'rgba(244, 63, 94, 0.85)',
              'rgba(168, 85, 247, 0.85)',
              'rgba(14, 165, 233, 0.85)',
              'rgba(99, 102, 241, 0.85)'
            ],
            borderRadius: 6,
            borderSkipped: false
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.95)',
              titleColor: '#38bdf8',
              bodyColor: '#f8fafc',
              callbacks: {
                label: function(context) {
                  return `Consumo: ${context.parsed.x} ${unit}`;
                }
              }
            }
          },
          scales: {
            x: {
              ticks: { color: '#64748b' },
              grid: { color: 'rgba(255, 255, 255, 0.05)' }
            },
            y: {
              ticks: { color: '#e2e8f0', font: { family: 'Inter', size: 12 } },
              grid: { display: false }
            }
          }
        }
      });
    },

    async loadTopHogs(hours = null) {
      if (hours) this.selectedHogsRange = hours;
      try {
        const res = await fetch(`/api/metrics/top-hogs?hours=${this.selectedHogsRange}&limit=8`);
        const json = await res.json();
        if (json.status === 'success') {
          this.topHogs = json.hogs || [];
          if (this.topHogs.length > 0) {
            const maxGb = Math.max(...this.topHogs.map(h => h.total_gb || 0));
            const useMb = maxGb < 0.1;
            const labels = this.topHogs.map(h => h.display_name);
            const data = this.topHogs.map(h => useMb ? (h.total_mb || 0) : (h.total_gb || 0));
            this.renderHogsChart(labels, data, useMb);
          } else if (this.hogsChartInstance) {
            this.hogsChartInstance.destroy();
            this.hogsChartInstance = null;
          }
        }
      } catch (err) {
        console.error("Load Top Hogs error:", err);
      }
    },

    // =========================================================================
    // DEVICE MANAGEMENT & DETAILS
    // =========================================================================
    get filteredDevices() {
      return this.devices.filter(d => {
        // Filtro online
        if (this.showConnectedOnly && !d.connected) return false;
        
        // Filtro banda
        if (this.selectedBandFilter !== 'all') {
          if (this.selectedBandFilter === 'wired') {
            if (d.connection_type !== 'wired') return false;
          } else {
            if (d.wireless_band !== this.selectedBandFilter) return false;
          }
        }

        // Filtro nodo
        if (this.selectedNodeFilter !== 'all') {
          if (d.connected_eero_id !== this.selectedNodeFilter && d.connected_eero_name !== this.selectedNodeFilter) {
            return false;
          }
        }

        // Filtro categoria
        if (this.selectedCategoryFilter !== 'all') {
          if (d.category !== this.selectedCategoryFilter) return false;
        }

        // Ricerca testuale
        if (this.deviceSearchQuery) {
          const q = this.deviceSearchQuery.toLowerCase();
          const name = (d.custom_name || d.nickname || d.hostname || '').toLowerCase();
          const ip = (d.ip || '').toLowerCase();
          const mac = (d.mac || d.mac_address || '').toLowerCase();
          const notes = (d.custom_notes || '').toLowerCase();
          return name.includes(q) || ip.includes(q) || mac.includes(q) || notes.includes(q);
        }

        return true;
      });
    },

    async openDeviceModal(device) {
      this.selectedDevice = device;
      this.deviceDetailTab = 'info';
      const mac = device.mac || device.mac_address;
      
      this.deviceMetadataForm = {
        custom_name: device.custom_name || device.nickname || '',
        custom_icon: device.custom_icon || 'device',
        category: device.category || 'Altro',
        custom_notes: device.custom_notes || '',
        static_ip: device.static_ip || '',
        is_favorite: Boolean(device.is_favorite),
        is_low_latency_target: Boolean(device.is_low_latency_target)
      };

      this.showDeviceModal = true;

      try {
        const res = await fetch(`/api/devices/${mac}`);
        const data = await res.json();
        if (data.status === 'success') {
          this.deviceForwards = data.forwards || [];
          this.deviceTrafficHistory = data.traffic_history || [];
        }
      } catch (err) {
        console.error("Fetch device detail error:", err);
      }
    },

    async saveDeviceMetadata() {
      if (!this.selectedDevice) return;
      const mac = this.selectedDevice.mac || this.selectedDevice.mac_address;
      try {
        const res = await fetch(`/api/devices/${mac}/metadata`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.deviceMetadataForm)
        });
        const data = await res.json();
        
        // Se il nome è cambiato, sincronizza anche il nickname con eero
        if (this.deviceMetadataForm.custom_name && this.deviceMetadataForm.custom_name !== this.selectedDevice.nickname) {
          const devId = this.selectedDevice.id || mac;
          await fetch(`/api/devices/${devId}/rename`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nickname: this.deviceMetadataForm.custom_name })
          });
        }

        this.showToast("Salvato", "Metadati dispositivo aggiornati.", "success");
        await this.fetchDevices();
        this.showDeviceModal = false;
      } catch (err) {
        this.showToast("Errore Salvataggio", err.message, "error");
      }
    },

    async toggleDevicePause(device) {
      const devId = device.id || device.mac;
      const targetState = !device.paused;
      try {
        await fetch(`/api/devices/${devId}/pause`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paused: targetState })
        });
        device.paused = targetState;
        this.showToast(
          targetState ? "Accesso in Pausa" : "Accesso Riabilitato",
          `Dispositivo '${device.custom_name || device.nickname || device.hostname}' ${targetState ? 'messo in pausa' : 'riattivato'}.`,
          targetState ? "warning" : "success"
        );
      } catch (err) {
        this.showToast("Errore Pausa", err.message, "error");
      }
    },

    // =========================================================================
    // SPEED TEST & DIAGNOSTICS
    // =========================================================================
    renderSpeedtestChart(labels, dl, ul, ping) {
      const canvas = document.getElementById('speedtestHistoryChart');
      if (!canvas) return;
      if (this.speedtestChartInstance) {
        this.speedtestChartInstance.destroy();
        this.speedtestChartInstance = null;
      }

      const p = canvas.parentElement;
      if (p) {
        canvas.width = p.clientWidth || 500;
        canvas.height = p.clientHeight || 280;
      }

      const ctx = canvas.getContext('2d');
      this.speedtestChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Download (Mbps)',
              data: dl,
              borderColor: '#38bdf8',
              backgroundColor: 'rgba(56, 189, 248, 0.1)',
              borderWidth: 2,
              tension: 0.3
            },
            {
              label: 'Upload (Mbps)',
              data: ul,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.1)',
              borderWidth: 2,
              tension: 0.3
            },
            {
              label: 'Ping (ms)',
              data: ping,
              borderColor: '#f59e0b',
              borderDash: [5, 5],
              borderWidth: 1.5,
              yAxisID: 'y1',
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          scales: {
            x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
            y: { title: { display: true, text: 'Mbps', color: '#64748b' }, ticks: { color: '#64748b' }, grid: { color: 'rgba(255, 255, 255, 0.05)' } },
            y1: { position: 'right', title: { display: true, text: 'Ping ms', color: '#f59e0b' }, ticks: { color: '#f59e0b' }, grid: { display: false } }
          }
        }
      });
    },

    async loadSpeedtestData() {
      try {
        const [resHist, resStats] = await Promise.all([
          fetch('/api/speedtest/history?limit=25'),
          fetch('/api/speedtest/stats')
        ]);
        const jsonHist = await resHist.json();
        const jsonStats = await resStats.json();

        if (jsonHist.status === 'success') {
          this.speedtestHistory = jsonHist.tests || [];
          if (this.speedtestHistory.length > 0) {
            const rev = [...this.speedtestHistory].reverse();
            const labels = rev.map(t => this.formatLocalDateTime(t.timestamp));
            const dl = rev.map(t => t.download_mbps);
            const ul = rev.map(t => t.upload_mbps);
            const ping = rev.map(t => t.ping_ms);
            this.renderSpeedtestChart(labels, dl, ul, ping);
          }
        }
        if (jsonStats.status === 'success') {
          this.speedtestStats = jsonStats.stats || {};
        }
      } catch (err) {
        console.error("Load speedtest data error:", err);
      }
    },

    async runSpeedtest() {
      if (this.speedtestRunning) return;
      this.speedtestRunning = true;
      this.speedtestProgress = 10;
      
      const interval = setInterval(() => {
        if (this.speedtestProgress < 90) {
          this.speedtestProgress += 15;
        }
      }, 500);

      try {
        const res = await fetch('/api/speedtest/run', { method: 'POST' });
        const json = await res.json();
        clearInterval(interval);
        this.speedtestProgress = 100;
        
        if (json.status === 'success') {
          this.lastSpeedtestResult = json.result;
          this.showToast("Speed Test Completato", `↓ ${json.result.download_mbps} Mbps | ↑ ${json.result.upload_mbps} Mbps`, "success");
          await this.loadSpeedtestData();
        }
      } catch (err) {
        clearInterval(interval);
        this.showToast("Errore Speed Test", err.message, "error");
      } finally {
        setTimeout(() => {
          this.speedtestRunning = false;
          this.speedtestProgress = 0;
        }, 1000);
      }
    },

    // =========================================================================
    // CONTROLS & AUTOMATIONS
    // =========================================================================
    async fetchGuestNetwork() {
      try {
        const res = await fetch('/api/network/guest');
        const json = await res.json();
        if (json.status === 'success') {
          this.guestNetwork = json.guest_network || {};
          this.guestQrCodeUrl = json.qr_code_data_url || '';
        }
      } catch (err) {
        console.error("Fetch guest network error:", err);
      }
    },

    async toggleGuestNetwork() {
      const targetState = !this.guestNetwork.enabled;
      try {
        const res = await fetch('/api/network/guest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            enabled: targetState,
            name: this.guestNetwork.name,
            password: this.guestNetwork.password
          })
        });
        const json = await res.json();
        this.guestNetwork = json.guest_network;
        this.guestQrCodeUrl = json.qr_code_data_url;
        this.showToast("Rete Ospiti", `Rete Ospiti ${targetState ? 'Attivata' : 'Disattivata'}.`, "info");
      } catch (err) {
        this.showToast("Errore Rete Ospiti", err.message, "error");
      }
    },

    async generateGuestPassword() {
      try {
        const res = await fetch('/api/network/guest/generate-password', { method: 'POST' });
        const json = await res.json();
        this.guestNetwork.password = json.password;
        this.showToast("Nuova Password", "Password sicura generata.", "info");
      } catch (err) {
        console.error(err);
      }
    },

    async saveGuestSettings() {
      try {
        const res = await fetch('/api/network/guest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.guestNetwork)
        });
        const json = await res.json();
        this.guestQrCodeUrl = json.qr_code_data_url;
        this.showToast("Rete Ospiti Aggiornata", "Credenziali e QR Code salvati.", "success");
      } catch (err) {
        this.showToast("Errore", err.message, "error");
      }
    },

    async fetchFocusMode() {
      try {
        const res = await fetch('/api/automations/focus-mode');
        const json = await res.json();
        if (json.status === 'success') {
          this.focusModeActive = json.active;
          this.focusModeTargetCount = json.target_devices_count;
        }
      } catch (err) {
        console.error("Fetch focus mode error:", err);
      }
    },

    async toggleFocusMode() {
      const targetState = !this.focusModeActive;
      try {
        const res = await fetch('/api/automations/focus-mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active: targetState })
        });
        const json = await res.json();
        this.focusModeActive = json.active;
        this.showToast(
          targetState ? "Gaming Mode Attiva" : "Gaming Mode Disattivata",
          json.message,
          targetState ? "warning" : "success"
        );
        await this.fetchDevices();
      } catch (err) {
        this.showToast("Errore Focus Mode", err.message, "error");
      }
    },

    async fetchNightMode() {
      try {
        const res = await fetch('/api/automations/night-mode');
        const json = await res.json();
        if (json.status === 'success') {
          this.nightMode = json;
        }
      } catch (err) {
        console.error("Fetch night mode error:", err);
      }
    },

    async saveNightMode() {
      try {
        await fetch('/api/automations/night-mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.nightMode)
        });
        this.showToast("Modalità Notte", "Orari LED salvati correttamente.", "success");
      } catch (err) {
        this.showToast("Errore", err.message, "error");
      }
    },

    async fetchNotificationSettings() {
      try {
        const res = await fetch('/api/automations/notifications');
        const json = await res.json();
        if (json.status === 'success') {
          this.notificationSettings = json;
        }
      } catch (err) {
        console.error("Fetch notifications settings error:", err);
      }
    },

    async saveNotificationSettings() {
      try {
        await fetch('/api/automations/notifications', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.notificationSettings)
        });
        this.showToast("Notifiche Salvate", "Impostazioni canali di allarme aggiornate.", "success");
      } catch (err) {
        this.showToast("Errore", err.message, "error");
      }
    },

    async testNotifications() {
      try {
        const res = await fetch('/api/automations/notifications/test', { method: 'POST' });
        const json = await res.json();
        this.showToast("Test Inviato", `Telegram: ${json.telegram_sent ? 'OK' : 'No'} | Webhook: ${json.webhook_sent ? 'OK' : 'No'}`, "info");
      } catch (err) {
        this.showToast("Errore Test", err.message, "error");
      }
    },

    async fetchAlerts() {
      try {
        const res = await fetch('/api/automations/alerts');
        const json = await res.json();
        if (json.status === 'success') {
          this.alertsList = json.alerts || [];
        }
      } catch (err) {
        console.error("Fetch alerts error:", err);
      }
    },

    async triggerDigest() {
      try {
        await fetch('/api/automations/digest/generate', { method: 'POST' });
        this.showToast("Digest Inviato", "Riepilogo generato e inoltrato sui canali attivi.", "success");
        await this.fetchAlerts();
      } catch (err) {
        this.showToast("Errore Digest", err.message, "error");
      }
    },

    // =========================================================================
    // BUILT-IN USER MANUAL & CONTEXTUAL HELP
    // =========================================================================
    async loadManualSections() {
      try {
        const res = await fetch('/api/manual/sections');
        const json = await res.json();
        if (json.status === 'success') {
          this.manualSections = json.sections || [];
          if (this.manualSections.length > 0) {
            this.selectedManualSection = this.manualSections[0];
          }
        }
      } catch (err) {
        console.error("Load manual error:", err);
      }
    },

    get filteredManualSections() {
      if (!this.manualSearchQuery) return this.manualSections;
      const q = this.manualSearchQuery.toLowerCase();
      return this.manualSections.filter(s => 
        s.title.toLowerCase().includes(q) || 
        s.summary.toLowerCase().includes(q) ||
        s.content.toLowerCase().includes(q)
      );
    },

    async openContextHelp(sectionId) {
      try {
        const res = await fetch(`/api/manual/sections/${sectionId}`);
        const json = await res.json();
        if (json.status === 'success' && json.section) {
          this.helpModalTitle = json.section.title;
          // Simple markdown-to-html converter
          this.helpModalContent = this.renderSimpleMarkdown(json.section.content);
          this.showHelpModal = true;
        }
      } catch (err) {
        console.error("Open context help error:", err);
      }
    },

    async openChangelogModal() {
      this.changelogLoading = true;
      this.showChangelogModal = true;
      try {
        const res = await fetch('/api/manual/changelog');
        const json = await res.json();
        if (json.status === 'success' && json.content) {
          this.changelogVersion = json.version || '1.00.01';
          this.changelogContent = this.renderSimpleMarkdown(json.content);
        }
      } catch (err) {
        console.error("Open changelog error:", err);
        this.changelogContent = '<p class="text-rose-400">Impossibile caricare il changelog.</p>';
      } finally {
        this.changelogLoading = false;
      }
    },

    renderSimpleMarkdown(md) {
      if (!md) return '';
      let html = md
        .replace(/^## (.*?)$/gm, '<h2 class="text-base font-bold text-sky-400 mt-4 mb-2 pb-1 border-b border-slate-800">$1</h2>')
        .replace(/^### (.*?)$/gm, '<h3 class="text-sm font-bold text-white mt-3 mb-1">$1</h3>')
        .replace(/^#### (.*?)$/gm, '<h4 class="text-xs font-bold text-slate-300 mt-2 mb-1">$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="text-sky-300 font-semibold">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="text-slate-300">$1</em>')
        .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-[11px]">$1</code>')
        .replace(/^[\*\-] (.*?)$/gm, '<li class="ml-4 list-disc text-slate-300 my-1 leading-relaxed">$1</li>')
        .replace(/---/g, '<hr class="border-slate-800 my-4"/>')
        .replace(/\n\n/g, '<p class="my-2 leading-relaxed text-slate-300"></p>');
      return html;
    },

    // =========================================================================
    // TOAST NOTIFICATION HELPER
    // =========================================================================
    showToast(title, message, type = 'info') {
      const id = Date.now();
      this.toasts.push({ id, title, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter(t => t.id !== id);
      }, 4000);
    }
  }));
});
