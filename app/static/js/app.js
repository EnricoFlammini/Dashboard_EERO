/**
 * eero Custom Dashboard & Management Suite - Frontend Application Logic
 * Powered by Alpine.js & Chart.js
 */

document.addEventListener('alpine:init', () => {
  Alpine.data('eeroApp', () => ({
    // App Version
    appVersion: '1.03.00',

    // i18n Multi-Language State
    currentLanguage: localStorage.getItem('eero_lang') || 'en',
    translations: {},
    translationsLoaded: false,

    // Navigation State
    currentTab: 'overview',
    
    // Auth & Session State
    isAuthenticated: false,
    isDemoMode: false,
    showLogoutModal: false,
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

    deviceSearchQuery: '',
    selectedBandFilter: 'all',
    selectedNodeFilter: 'all',
    selectedCategoryFilter: 'all',
    selectedProfileFilter: 'all',
    selectedIpTypeFilter: 'all',
    showConnectedOnly: false,
    deviceSortField: 'name',
    deviceSortDirection: 'asc',

    // Profiles & Cloud Users State
    profiles: [],
    showCreateProfileModal: false,
    newProfileForm: {
      name: '',
      selectedDeviceIds: []
    },
    deviceSelectedProfileId: '',
    profileAssigningLoading: false,
    
    selectedDevice: null,
    deviceDetailTab: 'general',
    deviceMetadataForm: {
      custom_name: '',
      custom_icon: 'device',
      category: 'Altro',
      custom_notes: '',
      is_favorite: false,
      is_low_latency_target: false
    },
    deviceReservation: null,
    deviceForwards: [],
    allReservations: [],
    deviceStaticIpInput: '',
    deviceRulesLoading: false,
    newPortForward: {
      port_from: '',
      port_to: '',
      protocol: 'tcp',
      description: ''
    },
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

    digestSettings: {
      enabled: true
    },
    
    // AdGuard Home DNS Integration State
    adguardSettings: {
      enabled: false,
      url: '',
      username: '',
      password: '',
      has_password: false,
      last_sync_time: '',
      last_sync_count: 0,
      last_sync_status: ''
    },
    adguardTesting: false,
    adguardSyncing: false,
    
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
    changelogVersion: '1.03.00',
    changelogLoading: false,

    // About Modal State
    showAboutModal: false,

    // Toast Notification System
    toasts: [],

    // =========================================================================
    // INITIALIZATION & I18N
    // =========================================================================
    async init() {
      console.log("Initializing eero Custom Dashboard application...");
      await this.setLanguage(this.currentLanguage);
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

    async setLanguage(lang) {
      this.currentLanguage = lang || 'en';
      localStorage.setItem('eero_lang', this.currentLanguage);
      try {
        const res = await fetch(`/static/locales/${this.currentLanguage}.json`);
        if (res.ok) {
          this.translations = await res.json();
          this.translationsLoaded = true;
        }
      } catch (e) {
        console.warn("Could not load translations for", this.currentLanguage, e);
      }
      await this.loadManualSections();
      if (this.showChangelogModal) {
        await this.openChangelogModal();
      }
    },

    formatBackhaul(eero) {
      if (!eero) return '';
      const bh = String(eero.backhaul_type || '').trim();
      const isWired = Boolean(eero.is_wired || eero.wired || bh.toLowerCase().includes('cablato') || bh.toLowerCase().includes('ethernet') || bh.toLowerCase().includes('wired'));
      if (isWired) {
        if (bh.includes('2.5')) return 'Ethernet (2.5 Gbps)';
        if (bh.includes('1.0') || bh.includes('1 Gbps')) return 'Ethernet (1.0 Gbps)';
        return this.t('dashboard.backhaul_wired') || (this.currentLanguage === 'it' ? 'Ethernet (Cablato)' : 'Ethernet (Wired)');
      }
      if (bh.includes('dBm') || (bh.includes('GHz') && bh.includes('/'))) {
        return bh;
      }
      return this.t('dashboard.backhaul_wireless') || 'Wireless Mesh (5/6 GHz)';
    },

    formatNodeStatus(eero) {
      if (!eero) return '';
      const statusLabel = ['online', 'green'].includes(eero.status) ? this.t('devices.status_online') : this.t('devices.status_offline');
      let temp = eero.temperature;
      if (!temp || temp === 'Normale' || temp === 'Normal' || temp === 'Ottimale' || temp === 'Optimal') {
        temp = this.t('dashboard.status_normal') || (this.currentLanguage === 'it' ? 'Normale' : 'Normal');
      }
      return `${statusLabel} • ${temp}`;
    },

    t(path, params = {}) {
      if (!path) return '';
      const keys = path.split('.');
      let val = this.translations;
      for (const k of keys) {
        if (val && typeof val === 'object' && k in val) {
          val = val[k];
        } else {
          val = null;
          break;
        }
      }
      if (typeof val !== 'string') {
        return path;
      }
      let res = val;
      for (const [k, v] of Object.entries(params)) {
        res = res.replaceAll(`{${k}}`, v);
      }
      return res;
    },

    async setTab(tab) {
      this.currentTab = tab;
      if (tab === 'speedtest') {
        setTimeout(async () => {
          await this.loadSpeedtestData();
        }, 50);
      } else if (tab === 'devices') {
        await this.fetchDevices();
      } else if (tab === 'controls') {
        await this.fetchNightMode();
        await this.fetchNotificationSettings();
        await this.fetchDigestSettings();
        await this.fetchAdGuardSettings();
        await this.fetchAlerts();
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
        const title = this.currentLanguage === 'it' ? "Codice Inviato" : "Code Sent";
        const msg = this.currentLanguage === 'it' ? "Inserisci il codice a 6 cifre ricevuto via SMS/Email." : "Enter the 6-digit verification code received via SMS/Email.";
        this.showToast(title, msg, "info");
      } catch (err) {
        this.authError = err.message;
        const title = this.currentLanguage === 'it' ? "Errore Login" : "Login Error";
        this.showToast(title, err.message, "error");
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
        if (!res.ok) throw new Error(data.detail || (this.currentLanguage === 'it' ? 'Verifica OTP fallita' : 'OTP verification failed'));
        
        this.isAuthenticated = true;
        this.otpSent = false;
        this.otpCode = '';
        this.tempUserToken = null;
        const title = this.currentLanguage === 'it' ? "Accesso Riuscito" : "Login Successful";
        const msg = this.currentLanguage === 'it' ? "Connessione con eero stabilita." : "Connected to eero mesh network.";
        this.showToast(title, msg, "success");
        await this.refreshAllData();
        this.startPolling();
      } catch (err) {
        this.authError = err.message;
        const title = this.currentLanguage === 'it' ? "Errore OTP" : "OTP Error";
        this.showToast(title, err.message, "error");
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
        const title = this.currentLanguage === 'it' ? "Disconnesso" : "Logged Out";
        const msg = this.currentLanguage === 'it' ? "Sessione terminata con successo." : "Session closed successfully.";
        this.showToast(title, msg, "info");
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
        if (this.currentTab === 'speedtest') {
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
        this.fetchProfiles(),
        this.fetchGuestNetwork(),
        this.fetchFocusMode(),
        this.fetchNightMode(),
        this.fetchNotificationSettings(),
        this.fetchDigestSettings(),
        this.fetchAdGuardSettings(),
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

    async fetchProfiles() {
      try {
        const res = await fetch('/api/profiles');
        const json = await res.json();
        if (json.status === 'success') {
          this.profiles = json.profiles || [];
        }
      } catch (err) {
        console.error("Fetch profiles error:", err);
      }
    },

    // =========================================================================
    // NETWORK & NODES ACTIONS
    // =========================================================================
    async rebootNetwork() {
      const confirmMsg = this.currentLanguage === 'it'
        ? "Sei sicuro di voler riavviare l'intera rete mesh eero? La connessione cadrà per 2-3 minuti."
        : "Are you sure you want to reboot the entire eero mesh network? Internet connectivity will drop for 2-3 minutes.";
      if (!confirm(confirmMsg)) return;

      try {
        const res = await fetch('/api/network/reboot', { method: 'POST' });
        const data = await res.json();
        const title = this.currentLanguage === 'it' ? "Riavvio Rete" : "Network Reboot";
        this.showToast(title, data.message || (this.currentLanguage === 'it' ? "Comando inviato." : "Reboot command sent."), "info");
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Riavvio" : "Reboot Error";
        this.showToast(title, err.message, "error");
      }
    },

    async rebootEero(eero) {
      const eid = eero.id || eero.serial;
      const confirmMsg = this.currentLanguage === 'it'
        ? `Riavviare il nodo '${eero.name || eid}'?`
        : `Reboot node '${eero.name || eid}'?`;
      if (!confirm(confirmMsg)) return;

      try {
        const res = await fetch(`/api/network/eeros/${eid}/reboot`, { method: 'POST' });
        const data = await res.json();
        const title = this.currentLanguage === 'it' ? "Riavvio Nodo" : "Node Reboot";
        this.showToast(title, data.message || (this.currentLanguage === 'it' ? `Riavvio nodo ${eero.name} avviato.` : `Rebooting node ${eero.name}.`), "info");
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Riavvio" : "Reboot Error";
        this.showToast(title, err.message, "error");
      }
    },

    async toggleEeroLed(eero) {
      const eid = eero.id || eero.serial;
      const targetState = !eero.led_on;
      try {
        const res = await fetch(`/api/network/eeros/${eid}/led`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ led_on: targetState })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.message || data.detail || (this.currentLanguage === 'it' ? 'Impossibile modificare il LED via API eero' : 'Failed to update LED via eero API'));
        }
        eero.led_on = targetState;
        const title = this.currentLanguage === 'it' ? "LED Aggiornato" : "LED Updated";
        const msg = this.currentLanguage === 'it' 
          ? `LED ${eero.name}: ${targetState ? 'Acceso' : 'Spento'}` 
          : `LED ${eero.name}: ${targetState ? 'ON' : 'OFF'}`;
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore LED" : "LED Error";
        this.showToast(title, err.message, "error");
      }
    },

    async toggleAllLeds(ledOn) {
      try {
        const res = await fetch('/api/network/leds', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ led_on: ledOn })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.message || data.detail || (this.currentLanguage === 'it' ? 'Impossibile modificare tutti i LED' : 'Failed to update all LEDs'));
        }
        this.eeros.forEach(e => e.led_on = ledOn);
        const title = this.currentLanguage === 'it' ? "Tutti i LED" : "All LEDs";
        const msg = this.currentLanguage === 'it' 
          ? `Tutti i LED impostati a: ${ledOn ? 'Accesi' : 'Spenti'}` 
          : `All LEDs set to: ${ledOn ? 'ON' : 'OFF'}`;
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore LED" : "LED Error";
        this.showToast(title, err.message, "error");
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

    toggleDeviceSort(field) {
      if (this.deviceSortField === field) {
        this.deviceSortDirection = this.deviceSortDirection === 'asc' ? 'desc' : 'asc';
      } else {
        this.deviceSortField = field;
        this.deviceSortDirection = (field === 'signal' || field === 'status') ? 'desc' : 'asc';
      }
    },

    get filteredDevices() {
      const list = this.devices.filter(d => {
        // Filtro online
        if (this.showConnectedOnly && !d.connected) return false;
        
        // Filtro banda
        if (this.selectedBandFilter !== 'all') {
          if (this.selectedBandFilter === 'wired') {
            if (d.connection_type !== 'wired' && d.wireless && d.frequency_band !== 'Cablato') return false;
          } else {
            const b = this.selectedBandFilter;
            const match = (d.wireless_band === b) ||
                          (d.frequency_band && d.frequency_band.replace(' ', '') === b) ||
                          (b === '6GHz' && (d.frequency_band === '6 GHz' || d.wireless_band === '6GHz')) ||
                          (b === '5GHz' && (d.frequency_band === '5 GHz' || d.wireless_band === '5GHz' || (d.channel >= 32 && d.channel <= 177))) ||
                          (b === '2.4GHz' && (d.frequency_band === '2.4 GHz' || d.wireless_band === '2.4GHz' || (d.channel >= 1 && d.channel <= 14)));
            if (!match) return false;
          }
        }

        // Filtro nodo
        if (this.selectedNodeFilter !== 'all') {
          if (d.connected_eero_id !== this.selectedNodeFilter && d.connected_eero_name !== this.selectedNodeFilter) {
            return false;
          }
        }

        // Filtro categoria / preferiti
        if (this.selectedCategoryFilter !== 'all') {
          if (this.selectedCategoryFilter === 'favorites') {
            if (!d.is_favorite) return false;
          } else if (d.category !== this.selectedCategoryFilter) {
            return false;
          }
        }

        // Filtro tipo IP (Statico / DHCP)
        if (this.selectedIpTypeFilter === 'static' && !d.is_static) return false;
        if (this.selectedIpTypeFilter === 'dhcp' && d.is_static) return false;

        // Filtro profilo utente
        if (this.selectedProfileFilter !== 'all') {
          if (this.selectedProfileFilter === 'unassigned') {
            if (d.profile_id) return false;
          } else {
            if (d.profile_id !== this.selectedProfileFilter && d.profile_name !== this.selectedProfileFilter) {
              return false;
            }
          }
        }

        // Ricerca testuale
        if (this.deviceSearchQuery) {
          const q = this.deviceSearchQuery.toLowerCase();
          const name = (d.custom_name || d.nickname || d.hostname || '').toLowerCase();
          const ip = (d.ip || '').toLowerCase();
          const mac = (d.mac || d.mac_address || '').toLowerCase();
          const notes = (d.custom_notes || '').toLowerCase();
          const cat = (d.category || '').toLowerCase();
          const prof = (d.profile_name || '').toLowerCase();
          return name.includes(q) || ip.includes(q) || mac.includes(q) || notes.includes(q) || cat.includes(q) || prof.includes(q);
        }

        return true;
      });

      // Ordinamento dinamico dei dispositivi
      const field = this.deviceSortField || 'name';
      const isAsc = this.deviceSortDirection === 'asc';

      const ipToInt = (ip) => {
        if (!ip) return 0;
        const parts = ip.split('.').map(Number);
        if (parts.length !== 4 || parts.some(isNaN)) return 0;
        return ((parts[0] << 24) >>> 0) + (parts[1] << 16) + (parts[2] << 8) + parts[3];
      };

      list.sort((a, b) => {
        let res = 0;
        switch (field) {
          case 'name': {
            const nameA = (a.custom_name || a.nickname || a.hostname || '').toLowerCase();
            const nameB = (b.custom_name || b.nickname || b.hostname || '').toLowerCase();
            res = nameA.localeCompare(nameB);
            break;
          }
          case 'ip': {
            const numA = ipToInt(a.ip);
            const numB = ipToInt(b.ip);
            res = numA - numB;
            if (res === 0) {
              res = (a.mac || '').localeCompare(b.mac || '');
            }
            break;
          }
          case 'profile': {
            const profA = (a.profile_name || '').toLowerCase();
            const profB = (b.profile_name || '').toLowerCase();
            res = profA.localeCompare(profB);
            break;
          }
          case 'node': {
            const nodeA = (a.connected_eero_name || 'Gateway').toLowerCase();
            const nodeB = (b.connected_eero_name || 'Gateway').toLowerCase();
            res = nodeA.localeCompare(nodeB);
            break;
          }
          case 'band': {
            const getBandRank = (d) => {
              if (d.connection_type === 'wired' || !d.wireless || d.frequency_band === 'Cablato') return '1_Ethernet';
              if (d.wireless_band === '6GHz' || d.frequency_band === '6 GHz') return '2_6GHz';
              if (d.wireless_band === '5GHz' || d.frequency_band === '5 GHz') return '3_5GHz';
              return '4_2.4GHz';
            };
            res = getBandRank(a).localeCompare(getBandRank(b));
            break;
          }
          case 'signal': {
            const sigA = (a.signal_rssi !== undefined && a.signal_rssi !== null) ? Number(a.signal_rssi) : -999;
            const sigB = (b.signal_rssi !== undefined && b.signal_rssi !== null) ? Number(b.signal_rssi) : -999;
            res = sigA - sigB;
            break;
          }
          case 'status': {
            const getStatusScore = (d) => {
              if (d.paused) return 1;
              if (d.connected) return 3;
              return 2; // offline
            };
            res = getStatusScore(a) - getStatusScore(b);
            break;
          }
          default:
            res = 0;
        }

        return isAsc ? res : -res;
      });

      return list;
    },

    get ipConflictInfo() {
      if (!this.deviceStaticIpInput || !this.selectedDevice) return null;
      const targetIp = this.deviceStaticIpInput.trim();
      const currentMac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      
      // Controllo formato IPv4 base
      const ipParts = targetIp.split('.');
      if (ipParts.length !== 4 || ipParts.some(p => isNaN(p) || p === '' || Number(p) < 0 || Number(p) > 255)) {
        return { hasConflict: true, isReassign: false, message: "Formato indirizzo IPv4 non valido (es. 192.168.4.50)." };
      }

      // 1. Conflitto Bloccante: Gateway o nodi mesh
      if (this.network && this.network.gateway_ip === targetIp) {
        return { hasConflict: true, isReassign: false, message: `L'IP ${targetIp} è l'indirizzo del Gateway eero.` };
      }
      for (const node of (this.eeros || [])) {
        if (node.ip === targetIp) {
          return { hasConflict: true, isReassign: false, message: `L'IP ${targetIp} appartiene al nodo mesh '${node.name}'.` };
        }
      }

      // 2. Se questo stesso dispositivo sta già usando questo IP (lease dinamico o statico)
      if (this.selectedDevice.ip === targetIp) {
        return { 
          hasConflict: false, 
          isReassign: false, 
          message: `Questo dispositivo sta già usando l'IP ${targetIp}. Clicca 'Riserva' per confermarlo fisso e permanente su eero.` 
        };
      }

      // 3. Riassegnazione da una prenotazione esistente (es. altra scheda di rete dello stesso PC o vecchio dispositivo)
      for (const res of (this.allReservations || [])) {
        if (res.ip === targetIp && (res.mac || '').toLowerCase() !== currentMac) {
          return { 
            hasConflict: false, 
            isReassign: true, 
            message: `L'IP ${targetIp} è attualmente prenotato per '${res.description || res.mac}'. Cliccando 'Riserva', la prenotazione verrà riassegnata a questo dispositivo.` 
          };
        }
      }

      // 4. Riassegnazione da un altro dispositivo con lease attivo
      for (const dev of (this.devices || [])) {
        const dMac = (dev.mac || dev.mac_address || '').toLowerCase();
        if (dev.ip === targetIp && dMac !== currentMac) {
          return { 
            hasConflict: false, 
            isReassign: true, 
            message: `L'IP ${targetIp} è attualmente assegnato a '${dev.custom_name || dev.nickname || dev.hostname || dMac}'. Cliccando 'Riserva', verrà riservato per questo dispositivo.` 
          };
        }
      }

      return { hasConflict: false, isReassign: false, message: "Indirizzo IP disponibile e pronto per la prenotazione." };
    },

    get latestSpeedtest() {
      if (this.lastSpeedtestResult && this.lastSpeedtestResult.download_mbps) {
        return this.lastSpeedtestResult;
      }
      if (this.speedtestHistory && this.speedtestHistory.length > 0) {
        return this.speedtestHistory[0];
      }
      if (this.network && this.network.speedtest && this.network.speedtest.download_mbps) {
        return this.network.speedtest;
      }
      return { download_mbps: 0, upload_mbps: 0, ping_ms: 0 };
    },

    async openDeviceModal(device) {
      this.selectedDevice = device;
      this.deviceDetailTab = 'general';
      const mac = (device.mac || device.mac_address || '').toLowerCase();
      
      this.deviceMetadataForm = {
        custom_name: device.custom_name || device.nickname || device.hostname || '',
        custom_icon: device.custom_icon || 'device',
        category: device.category || 'Altro',
        custom_notes: device.custom_notes || '',
        is_favorite: Boolean(device.is_favorite),
        is_low_latency_target: Boolean(device.is_low_latency_target)
      };

      this.deviceSelectedProfileId = device.profile_id || '';
      this.deviceStaticIpInput = device.static_ip || device.ip || '';
      this.newPortForward = { port_from: '', port_to: '', protocol: 'tcp', description: '' };
      this.showDeviceModal = true;
      
      await this.loadDeviceRules(mac);
    },

    async loadDeviceRules(mac) {
      if (!mac) return;
      this.deviceRulesLoading = true;
      try {
        const res = await fetch(`/api/devices/${mac}/rules`);
        const data = await res.json();
        if (data.status === 'success') {
          this.deviceReservation = data.reservation || null;
          this.deviceForwards = data.forwards || [];
          this.allReservations = data.all_reservations || [];
          
          if (this.deviceReservation) {
            this.deviceStaticIpInput = this.deviceReservation.ip;
          } else if (this.selectedDevice && this.selectedDevice.ip) {
            this.deviceStaticIpInput = this.selectedDevice.ip;
          }
        }
      } catch (err) {
        console.error("Load device rules error:", err);
      } finally {
        this.deviceRulesLoading = false;
      }
    },

    async saveDeviceReservation() {
      if (!this.selectedDevice || !this.deviceStaticIpInput) return;
      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      try {
        const desc = this.deviceMetadataForm.custom_name || this.selectedDevice.nickname || this.selectedDevice.hostname || 'Device';
        const res = await fetch(`/api/devices/${mac}/reservation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ip: this.deviceStaticIpInput.trim(),
            description: desc
          })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || 'Errore durante la prenotazione DHCP');
        }

        const title = this.currentLanguage === 'it' ? "IP Statico Riservato" : "Static IP Reserved";
        const msg = this.currentLanguage === 'it' 
          ? `Indirizzo ${this.deviceStaticIpInput} prenotato con successo su eero.`
          : `IP address ${this.deviceStaticIpInput} successfully reserved on eero.`;
        this.showToast(title, msg, "success");
        await this.loadDeviceRules(mac);
        await this.fetchDevices();
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Prenotazione IP" : "IP Reservation Error";
        this.showToast(title, err.message, "error");
      }
    },

    async removeDeviceReservation() {
      if (!this.selectedDevice) return;
      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      try {
        const res = await fetch(`/api/devices/${mac}/reservation`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.currentLanguage === 'it' ? 'Errore durante la rimozione della prenotazione' : 'Error removing IP reservation'));
        }

        const title = this.currentLanguage === 'it' ? "Prenotazione Rimossa" : "Reservation Removed";
        const msg = this.currentLanguage === 'it' 
          ? "IP Statico rimosso. Il dispositivo utilizzerà DHCP dinamico." 
          : "Static IP reservation removed. Device will use dynamic DHCP.";
        this.showToast(title, msg, "info");
        await this.loadDeviceRules(mac);
        await this.fetchDevices();
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Rimozione" : "Removal Error";
        this.showToast(title, err.message, "error");
      }
    },

    async addDevicePortForward() {
      if (!this.selectedDevice) return;
      const targetIp = (this.deviceReservation ? this.deviceReservation.ip : (this.selectedDevice.ip || '')).trim();
      if (!targetIp) {
        const title = this.currentLanguage === 'it' ? "IP Mancante" : "Missing IP";
        const msg = this.currentLanguage === 'it' ? "Il dispositivo deve avere un indirizzo IP valido per aprire porte." : "Device must have a valid IP address for port forwarding.";
        this.showToast(title, msg, "warning");
        return;
      }
      const pFrom = parseInt(this.newPortForward.port_from);
      const pTo = parseInt(this.newPortForward.port_to);
      if (isNaN(pFrom) || isNaN(pTo) || pFrom < 1 || pFrom > 65535 || pTo < 1 || pTo > 65535) {
        const title = this.currentLanguage === 'it' ? "Porta non valida" : "Invalid Port";
        const msg = this.currentLanguage === 'it' ? "Inserisci numeri di porta validi compresi tra 1 e 65535." : "Please enter valid port numbers between 1 and 65535.";
        this.showToast(title, msg, "warning");
        return;
      }

      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      try {
        const res = await fetch(`/api/devices/${mac}/forwards`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ip: targetIp,
            port_from: pFrom,
            port_to: pTo,
            protocol: this.newPortForward.protocol || 'tcp',
            description: this.newPortForward.description || 'Custom Forward'
          })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.currentLanguage === 'it' ? 'Errore durante la creazione del port forward' : 'Error creating port forward'));
        }

        const title = this.currentLanguage === 'it' ? "Porta Inoltrata" : "Port Forwarded";
        const msg = this.currentLanguage === 'it' ? `Regola per porta ${pFrom} creata con successo su eero.` : `Rule for port ${pFrom} created on eero.`;
        this.showToast(title, msg, "success");
        this.newPortForward = { port_from: '', port_to: '', protocol: 'tcp', description: '' };
        await this.loadDeviceRules(mac);
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Port Forwarding" : "Port Forward Error";
        this.showToast(title, err.message, "error");
      }
    },

    async deleteDevicePortForward(forwardId) {
      if (!this.selectedDevice || !forwardId) return;
      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      try {
        const res = await fetch(`/api/devices/${mac}/forwards/${forwardId}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.currentLanguage === 'it' ? 'Errore durante la cancellazione della regola' : 'Error deleting forwarding rule'));
        }

        const title = this.currentLanguage === 'it' ? "Regola Eliminata" : "Rule Deleted";
        const msg = this.currentLanguage === 'it' ? "Port forwarding rimosso da eero." : "Port forwarding rule deleted from eero.";
        this.showToast(title, msg, "info");
        await this.loadDeviceRules(mac);
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Cancellazione" : "Deletion Error";
        this.showToast(title, err.message, "error");
      }
    },

    async saveDeviceMetadata() {
      if (!this.selectedDevice) return;
      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
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
          try {
            await fetch(`/api/devices/${devId}/rename`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ nickname: this.deviceMetadataForm.custom_name })
            });
          } catch (e) {
            console.warn("Rename sync warning:", e);
          }
        }

        // Aggiorna immediatamente lo stato reattivo in memoria
        Object.assign(this.selectedDevice, {
          custom_name: this.deviceMetadataForm.custom_name,
          category: this.deviceMetadataForm.category,
          custom_notes: this.deviceMetadataForm.custom_notes,
          is_favorite: Boolean(this.deviceMetadataForm.is_favorite),
          is_low_latency_target: Boolean(this.deviceMetadataForm.is_low_latency_target)
        });

        const title = this.currentLanguage === 'it' ? "Salvato" : "Saved";
        const msg = this.currentLanguage === 'it' ? "Metadati e categoria dispositivo salvati con successo." : "Device metadata and category saved successfully.";
        this.showToast(title, msg, "success");
        this.showDeviceModal = false;
        await this.fetchDevices();
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Salvataggio" : "Save Error";
        this.showToast(title, err.message, "error");
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
        const title = targetState 
          ? (this.currentLanguage === 'it' ? "Accesso in Pausa" : "Internet Paused") 
          : (this.currentLanguage === 'it' ? "Accesso Riabilitato" : "Internet Restored");
        const devName = device.custom_name || device.nickname || device.hostname;
        const msg = this.currentLanguage === 'it'
          ? `Dispositivo '${devName}' ${targetState ? 'messo in pausa' : 'riattivato'}.`
          : `Device '${devName}' ${targetState ? 'paused' : 'restored'}.`;
        this.showToast(title, msg, targetState ? "warning" : "success");
      } catch (err) {
        const title = this.currentLanguage === 'it' ? "Errore Pausa" : "Pause Error";
        this.showToast(title, err.message, "error");
      }
    },

    // =========================================================================
    // CLOUD PROFILES & USERS MANAGEMENT ACTIONS
    // =========================================================================
    get unassignedDevices() {
      return this.devices.filter(d => !d.profile_id);
    },

    openCreateProfileModal() {
      this.newProfileForm = {
        name: '',
        selectedDeviceIds: []
      };
      this.showCreateProfileModal = true;
    },

    toggleNewProfileDeviceSelection(device) {
      const devKey = device.id || device.mac;
      const idx = this.newProfileForm.selectedDeviceIds.indexOf(devKey);
      if (idx >= 0) {
        this.newProfileForm.selectedDeviceIds.splice(idx, 1);
      } else {
        this.newProfileForm.selectedDeviceIds.push(devKey);
      }
    },

    async createProfile() {
      if (!this.newProfileForm.name || !this.newProfileForm.name.trim()) {
        this.showToast("Nome Richiesto", "Inserisci il nome del profilo o dell'utente.", "warning");
        return;
      }

      this.profileAssigningLoading = true;
      try {
        const res = await fetch('/api/profiles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: this.newProfileForm.name.trim(),
            device_ids: this.newProfileForm.selectedDeviceIds
          })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || 'Impossibile creare il profilo');
        }

        this.showToast("Profilo Creato", `Profilo '${this.newProfileForm.name}' creato con successo su eero.`, "success");
        this.showCreateProfileModal = false;
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        this.showToast("Errore Creazione Profilo", err.message, "error");
      } finally {
        this.profileAssigningLoading = false;
      }
    },

    async deleteProfile(profile) {
      const pName = profile.name || 'questo profilo';
      const promptMsg = (this.translations.profiles && this.translations.profiles.delete_profile_confirm)
        ? this.translations.profiles.delete_profile_confirm.replace('{name}', pName)
        : `Sei sicuro di voler eliminare il profilo '${pName}'?`;

      if (!confirm(promptMsg)) return;

      try {
        const res = await fetch(`/api/profiles/${profile.id}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || 'Impossibile eliminare il profilo');
        }

        this.showToast("Profilo Eliminato", `Profilo '${pName}' rimosso da eero.`, "info");
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        this.showToast("Errore Eliminazione", err.message, "error");
      }
    },

    async toggleProfilePause(profile) {
      const targetState = !profile.paused;
      try {
        const res = await fetch(`/api/profiles/${profile.id}/pause`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paused: targetState })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || 'Impossibile modificare la pausa del profilo');
        }

        profile.paused = targetState;
        this.showToast(
          targetState ? "Profilo in Pausa" : "Profilo Riattivato",
          `Accesso Internet per il profilo '${profile.name}' ${targetState ? 'sospeso' : 'ripristinato'}.`,
          targetState ? "warning" : "success"
        );
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        this.showToast("Errore Pausa Profilo", err.message, "error");
      }
    },

    async assignDeviceToProfile(deviceMacOrId, profileId) {
      if (!deviceMacOrId) return;
      const isRemoving = !profileId;
      try {
        const res = await fetch(`/api/devices/${deviceMacOrId}/profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile_id: profileId ? profileId : null })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || 'Impossibile aggiornare l\'associazione al profilo');
        }

        this.showToast(
          isRemoving ? "Assegnazione Rimossa" : "Assegnazione Salvata",
          isRemoving ? "Dispositivo disassociato dal profilo con successo." : "Dispositivo associato al profilo con successo.",
          "success"
        );
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        this.showToast("Errore Assegnazione", err.message, "error");
      }
    },

    async removeDeviceFromProfile(deviceMacOrId) {
      await this.assignDeviceToProfile(deviceMacOrId, null);
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
          fetch('/api/speedtest/history?limit=30'),
          fetch('/api/speedtest/stats')
        ]);
        const jsonHist = await resHist.json();
        const jsonStats = await resStats.json();

        if (jsonHist.status === 'success') {
          this.speedtestHistory = jsonHist.tests || [];
          if (this.speedtestHistory.length > 0) {
            this.lastSpeedtestResult = this.speedtestHistory[0];
            const rev = [...this.speedtestHistory].reverse();
            const labels = rev.map(t => this.formatLocalDateTime(t.timestamp));
            const dl = rev.map(t => t.download_mbps);
            const ul = rev.map(t => t.upload_mbps);
            const ping = rev.map(t => t.ping_ms);
            this.renderSpeedtestChart(labels, dl, ul, ping);
          } else if (this.network && this.network.speedtest) {
            this.lastSpeedtestResult = this.network.speedtest;
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

    // =========================================================================
    // ADGUARD HOME DNS & DHCP CLIENT SYNC
    // =========================================================================
    async fetchAdGuardSettings() {
      try {
        const res = await fetch('/api/automations/adguard');
        const json = await res.json();
        if (json.status === 'success') {
          this.adguardSettings = {
            enabled: Boolean(json.enabled),
            url: json.url || '',
            username: json.username || '',
            password: '',
            has_password: Boolean(json.has_password),
            last_sync_time: json.last_sync_time || '',
            last_sync_count: json.last_sync_count || 0,
            last_sync_status: json.last_sync_status || ''
          };
        }
      } catch (err) {
        console.error("Fetch AdGuard settings error:", err);
      }
    },

    async saveAdGuardSettings() {
      try {
        let cleanUrl = (this.adguardSettings.url || '').trim();
        if (cleanUrl.includes('#')) cleanUrl = cleanUrl.split('#')[0];
        cleanUrl = cleanUrl.replace(/\/+$/, '');
        if (cleanUrl && !cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
          cleanUrl = 'http://' + cleanUrl;
        }
        this.adguardSettings.url = cleanUrl;

        const payload = {
          enabled: Boolean(this.adguardSettings.enabled),
          url: cleanUrl,
          username: this.adguardSettings.username || '',
          password: this.adguardSettings.password || undefined
        };
        const res = await fetch('/api/automations/adguard', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (res.ok) {
          this.showToast("AdGuard Home", json.message || "Impostazioni salvate con successo.", "success");
          await this.fetchAdGuardSettings();
        } else {
          this.showToast("Errore AdGuard", json.detail || "Impossibile salvare le impostazioni.", "error");
        }
      } catch (err) {
        this.showToast("Errore AdGuard", err.message, "error");
      }
    },

    async testAdGuardConnection() {
      this.adguardTesting = true;
      try {
        let cleanUrl = (this.adguardSettings.url || '').trim();
        if (cleanUrl.includes('#')) cleanUrl = cleanUrl.split('#')[0];
        cleanUrl = cleanUrl.replace(/\/+$/, '');
        if (cleanUrl && !cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
          cleanUrl = 'http://' + cleanUrl;
        }
        this.adguardSettings.url = cleanUrl;

        const payload = {
          url: cleanUrl,
          username: this.adguardSettings.username,
          password: this.adguardSettings.password || undefined
        };
        const res = await fetch('/api/automations/adguard/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.success) {
          if (json.normalized_url) {
            this.adguardSettings.url = json.normalized_url;
          }
          this.showToast("Test Connessione Riuscito", json.message, "success");
        } else {
          this.showToast("Test Fallito", json.message || "Impossibile connettersi ad AdGuard Home", "error");
        }
      } catch (err) {
        this.showToast("Errore Test", err.message, "error");
      } finally {
        this.adguardTesting = false;
      }
    },

    async syncAdGuardNow() {
      this.adguardSyncing = true;
      try {
        const res = await fetch('/api/automations/adguard/sync', { method: 'POST' });
        const json = await res.json();
        if (res.ok && json.status === 'success') {
          this.showToast("Sincronizzazione Completata", json.message, "success");
          await this.fetchAdGuardSettings();
        } else {
          this.showToast("Errore Sincronizzazione", json.detail || json.message || "Sincronizzazione non riuscita.", "error");
        }
      } catch (err) {
        this.showToast("Errore Sincronizzazione", err.message, "error");
      } finally {
        this.adguardSyncing = false;
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

    async fetchDigestSettings() {
      try {
        const res = await fetch('/api/automations/digest');
        const json = await res.json();
        if (json.status === 'success') {
          this.digestSettings.enabled = Boolean(json.enabled);
        }
      } catch (err) {
        console.error("Fetch digest settings error:", err);
      }
    },

    async saveDigestSettings() {
      try {
        const res = await fetch('/api/automations/digest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: Boolean(this.digestSettings.enabled) })
        });
        const json = await res.json();
        if (res.ok) {
          this.showToast(
            this.digestSettings.enabled ? "Digest Programmato Attivo" : "Digest Programmato Disattivato",
            this.digestSettings.enabled ? "Il report automatico delle 21:00 è abilitato." : "L'invio automatico delle 21:00 è stato sospeso.",
            "info"
          );
        } else {
          this.showToast("Errore", json.detail || "Impossibile salvare l'impostazione.", "error");
        }
      } catch (err) {
        this.showToast("Errore", err.message, "error");
      }
    },

    async triggerDigest() {
      try {
        const res = await fetch('/api/automations/digest/generate', { method: 'POST' });
        const json = await res.json();
        if (res.ok && json.status === 'success') {
          this.showToast("Digest Inviato", json.message || "Riepilogo generato e inoltrato sui canali attivi.", "success");
          await this.fetchAlerts();
        } else {
          this.showToast("Errore Invio Digest", json.detail || json.message || "Impossibile inviare il digest.", "error");
        }
      } catch (err) {
        this.showToast("Errore Digest", err.message, "error");
      }
    },

    // =========================================================================
    // BUILT-IN USER MANUAL & CONTEXTUAL HELP
    // =========================================================================
    async loadManualSections() {
      try {
        const currentId = this.selectedManualSection ? this.selectedManualSection.id : null;
        const res = await fetch(`/api/manual/sections?lang=${this.currentLanguage || 'en'}`);
        const json = await res.json();
        if (json.status === 'success') {
          this.manualSections = json.sections || [];
          if (this.manualSections.length > 0) {
            this.selectedManualSection = this.manualSections.find(s => s.id === currentId) || this.manualSections[0];
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
        const res = await fetch(`/api/manual/sections/${sectionId}?lang=${this.currentLanguage || 'en'}`);
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
        const res = await fetch(`/api/manual/changelog?lang=${this.currentLanguage || 'en'}`);
        const json = await res.json();
        if (json.status === 'success' && json.content) {
          this.changelogVersion = json.version || '1.03.00';
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
      // Escape raw HTML entities to prevent XSS
      let text = String(md)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

      // Inline styles first: links, bold, italic, code, horizontal rules
      text = text
        .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 underline font-medium">$1</a>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="text-sky-300 font-semibold">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="text-slate-300">$1</em>')
        .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-[11px]">$1</code>')
        .replace(/---/g, '<hr class="border-slate-800 my-4"/>');

      const lines = text.split('\n');
      let out = [];
      let inUl = false;
      let inOl = false;
      let inSubUl = false;

      for (let i = 0; i < lines.length; i++) {
        let line = lines[i];
        let trimmed = line.trim();

        if (!trimmed) {
          if (inSubUl) { out.push('</ul>'); inSubUl = false; }
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          continue;
        }

        // Headings
        if (/^## (.*?)$/.test(trimmed)) {
          if (inSubUl) { out.push('</ul>'); inSubUl = false; }
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          out.push(`<h2 class="text-base font-bold text-sky-400 mt-5 mb-2 pb-1 border-b border-slate-800">${trimmed.slice(3)}</h2>`);
          continue;
        }
        if (/^### (.*?)$/.test(trimmed)) {
          if (inSubUl) { out.push('</ul>'); inSubUl = false; }
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          out.push(`<h3 class="text-sm font-bold text-white mt-4 mb-2">${trimmed.slice(4)}</h3>`);
          continue;
        }
        if (/^#### (.*?)$/.test(trimmed)) {
          if (inSubUl) { out.push('</ul>'); inSubUl = false; }
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (inOl) { out.push('</ol>'); inOl = false; }
          out.push(`<h4 class="text-xs font-bold text-slate-300 mt-3 mb-1.5">${trimmed.slice(5)}</h4>`);
          continue;
        }

        // Nested sub-bullet (2+ spaces indentation)
        let subBulletMatch = line.match(/^(\s{2,}|\t+)[\*\-]\s+(.*)$/);
        if (subBulletMatch) {
          if (!inSubUl) {
            out.push('<ul class="pl-6 space-y-1.5 my-1.5 list-disc text-slate-300">');
            inSubUl = true;
          }
          out.push(`<li class="leading-relaxed">${subBulletMatch[2]}</li>`);
          continue;
        } else if (inSubUl) {
          out.push('</ul>');
          inSubUl = false;
        }

        // Main Bullet list (* or -)
        let bulletMatch = trimmed.match(/^[\*\-]\s+(.*)$/);
        if (bulletMatch) {
          if (inOl) { out.push('</ol>'); inOl = false; }
          if (!inUl) {
            out.push('<ul class="pl-5 space-y-2 my-2 list-disc text-slate-300">');
            inUl = true;
          }
          out.push(`<li class="leading-relaxed">${bulletMatch[1]}</li>`);
          continue;
        }

        // Numbered list (1. 2. etc)
        let numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
        if (numberedMatch) {
          if (inUl) { out.push('</ul>'); inUl = false; }
          if (!inOl) {
            out.push('<ol class="pl-5 space-y-2.5 my-2 list-decimal text-slate-300">');
            inOl = true;
          }
          out.push(`<li class="leading-relaxed pl-1">${numberedMatch[2]}</li>`);
          continue;
        }

        // Regular paragraph or plain line
        if (inUl) { out.push('</ul>'); inUl = false; }
        if (inOl) { out.push('</ol>'); inOl = false; }
        out.push(`<p class="my-2 leading-relaxed text-slate-300">${trimmed}</p>`);
      }

      if (inSubUl) out.push('</ul>');
      if (inUl) out.push('</ul>');
      if (inOl) out.push('</ol>');

      return out.join('\n');
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
