/**
 * eero Custom Dashboard & Management Suite - Diagnostics & Analytics Module
 * Handles speed tests, bandwidth historian, signal quality / sticky client advisor,
 * system logging viewer, top hogs analysis, ISP SLA tracking, and user manual.
 */
function createDiagnosticsModule() {
  return {
healthScore: 100,
    healthDetails: null,
    showHealthModal: false,

realtimeMetrics: {
      current_download_mbps: 0,
      current_upload_mbps: 0,
      total_rx_gb: 0,
      total_tx_gb: 0,
      connected_clients_count: 0
    },
    lastPollTime: null,
    pollingTimer: null,

    // Multi-Network Fleet Management State (v1.5.0 - Issue #22, Issue #69),

deviceUsagePeriod: 'daily', // 'daily' | 'weekly' | 'monthly'
    deviceUsageResolution: 15, // 10 | 15 | 20 | 30 min (for daily)
    deviceUsageLoading: false,
    deviceUsageData: null,
    deviceUsageChart: null,

    // Top Bandwidth Hogs State (v1.5.0)
    topHogsList: [],
    topHogsPeriod: 'daily',
    topHogsLoading: false,

    // Statistics & Analytics State (v1.5.0)
    analyticsLoading: false,

analyticsDistribution: {
      total_devices: 0,
      active_devices: 0,
      frequencies: [],
      node_load: [],
      categories: [],
      vendors: []
    },
    analyticsSla: {
      total_tests: 0,
      period_days: 30,
      avg_download_mbps: 0,
      max_download_mbps: 0,
      min_download_mbps: 0,
      avg_upload_mbps: 0,
      max_upload_mbps: 0,
      min_upload_mbps: 0,
      avg_ping_ms: 0,
      min_ping_ms: 0,
      max_ping_ms: 0,
      avg_jitter_ms: 0,
      max_jitter_ms: 0,
      reliability_score: 100,
      history_points: []
    },
    analyticsSlaDays: 30,
    analyticsChartInstances: {},
    exportLoading: false,

    // Bandwidth Historian State
    selectedWanRange: 24, // 24h, 168 (7d), 720 (30d)
    wanTotalGb: 0,
    wanHistoryData: [],
    wanChartInstance: null,
    
    selectedHogsRange: 24,
    topHogs: [],
    hogsChartInstance: null,

// eeroOS Release Notes & Community Updates State (v1.6.0)
    eeroNewsLoading: false,
    eeroNewsError: null,
    eeroNewsData: null,
    eeroNewsSearchQuery: '',
    eeroNewsFilter: 'all', // 'all', 'security', 'wifi7', 'stability'
    eeroNewsExpandedVersions: {},
    eeroNewsShowAllReleases: false,
    eeroNewsDefaultLimit: 5,

// Speed Test State
    speedtestRunning: false,
    speedtestProgress: 0,
    speedtestStats: {},
    speedtestHistory: [],
    speedtestChartInstance: null,
    lastSpeedtestResult: null,

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
    changelogVersion: '1.7.0',
    changelogLoading: false,

    // About Modal State
    showAboutModal: false,

    // Estimated Data Usage Info Modal State
    showUsageInfoModal: false,

    // Where this instance runs (local / Docker / Kubernetes) and its source branch
    runtimeInfo: null,

    // Auto-Update State (v1.7.0)
    updateInfo: {
      update_available: false,
      current_version: '1.7.0',
      latest_version: '1.7.0',
      latest_build_number: '1',
      latest_full_version: '1.7.0 build 1',
      release_title: '',
      release_notes: '',
      condensed_changelog: [],
      docker_socket_available: false,
      watchtower_configured: false,
      can_auto_install: false,
      cli_command: 'docker compose pull && docker compose up -d'
    },
    isCheckingUpdate: false,
    isTriggeringUpdate: false,
    showUpdateModal: false,
    showUpdatePrompt: false,
    showFullReleaseNotes: false,
    updateProgressMsg: '',
    copiedCliCommand: false,

// Signal Quality & Coverage State (v1.04.00)
    signalOverview: {
      total_wireless_devices: 0,
      average_rssi: 0,
      excellent_count: 0,
      good_count: 0,
      fair_count: 0,
      weak_count: 0,
      excellent_pct: 0,
      good_pct: 0,
      fair_pct: 0,
      weak_pct: 0,
      weak_devices: [],
      devices: []
    },
    selectedSignalDeviceMac: '',
    signalHistoryHours: 24,
    signalChartInstance: null,
    signalLoading: false,

// =========================================================================
    // MODULE 3: BANDWIDTH HOGS MULTI-FILTERS & RESILIENCE
    // =========================================================================
    hogsCategoryFilter: 'all',
    hogsBandFilter: 'all',
    hogsNodeFilter: 'all',
    telemetryStale: false,
    telemetryAuthExpired: false,

    // Toast Notification System
    toasts: [],

    // Maintenance overlay (Issue #117): { stage, since } while the server reports maintenance
    maintenance: null,
    maintenanceElapsed: 0,
    maintenancePollTimer: null,

newsTagKey(tag) {
      const norm = String(tag || '').toLowerCase().trim();
      for (const [key, aliases] of Object.entries(this.newsTagAliases)) {
        if (aliases.includes(norm)) return key;
      }
      return norm;
    },
    newsTagIs(tag, key) {
      return this.newsTagKey(tag) === key;
    },
    newsTagLabel(tag) {
      const label = this.t('eero_news.tag_' + this.newsTagKey(tag));
      return label !== '' ? label : String(tag || '');
    },

    // Header toggle: steps through supportedLanguages in order.,

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

      const colors = this.getChartThemeColors();
      const ctx = canvas.getContext('2d');
      this.wanChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: this.t('charts.download_mbps'),
              data: dlData,
              borderColor: colors.isDark ? '#38bdf8' : '#0067c0',
              backgroundColor: colors.isDark ? 'rgba(56, 189, 248, 0.15)' : 'rgba(0, 103, 192, 0.12)',
              borderWidth: 2,
              fill: true,
              tension: 0.35,
              pointRadius: 1,
              pointHoverRadius: 5
            },
            {
              label: this.t('charts.upload_mbps'),
              data: ulData,
              borderColor: colors.isDark ? '#10b981' : '#0f7b0f',
              backgroundColor: colors.isDark ? 'rgba(16, 185, 129, 0.10)' : 'rgba(15, 123, 15, 0.10)',
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
              labels: { color: colors.ticksColor, font: { family: colors.fontFamily, size: 12 } }
            },
            tooltip: {
              backgroundColor: colors.tooltipBg,
              titleColor: colors.tooltipTitle,
              bodyColor: colors.tooltipBody,
              borderColor: colors.tooltipBorder,
              borderWidth: 1,
              padding: 10
            }
          },
          scales: {
            x: {
              ticks: { color: colors.ticksColor, maxTicksLimit: 8, font: { family: colors.fontFamily } },
              grid: { color: colors.gridColor }
            },
            y: {
              ticks: { color: colors.ticksColor, font: { family: colors.fontFamily } },
              grid: { color: colors.gridColor }
            }
          }
        }
      });
    },

    // BCP 47 locale for dates and numbers: the browser's own regional variant
    // when it matches the dashboard language (e.g. en-US vs en-GB), otherwise
    // the dashboard language's default region.
    dateLocale() {
      const nav = (typeof navigator !== 'undefined' && navigator.language) ? navigator.language : '';
      if (nav.toLowerCase().startsWith(this.currentLanguage)) return nav;
      return this.dateLocales[this.currentLanguage] || this.currentLanguage || 'en';
    },

    formatLocalTime(ts) {
      if (!ts) return '';
      const d = new Date(ts.replace(' ', 'T'));
      return d.toLocaleTimeString(this.dateLocale(), { hour: '2-digit', minute: '2-digit' });
    },

    formatFirstSeenRelative(ts) {
      if (!ts) return '';
      let str = String(ts).trim();
      if (!str.endsWith('Z') && !str.includes('+')) {
        str = str.replace(' ', 'T') + 'Z';
      }
      const d = new Date(str);
      if (isNaN(d.getTime())) return String(ts);
      const now = new Date();
      const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
      if (diffSec < 0) return this.t('js.format_first_seen_relative.just_now');
      if (diffSec < 60) return this.t('js.format_first_seen_relative.just_now');
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return this.t('js.format_first_seen_relative.m_ago', { diffMin: diffMin });
      const diffHours = Math.floor(diffMin / 60);
      if (diffHours < 24) return this.t('js.format_first_seen_relative.h_ago', { diffHours: diffHours });
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays === 1) return this.t('js.format_first_seen_relative.yesterday');
      if (diffDays < 7) return this.t('js.format_first_seen_relative.d_ago', { diffDays: diffDays });
      if (diffDays < 30) {
        const diffWeeks = Math.floor(diffDays / 7);
        return this.t('js.format_first_seen_relative.w_ago', { diffWeeks: diffWeeks });
      }
      return d.toLocaleDateString(this.dateLocale(), { month: 'short', day: 'numeric' });
    },

    deviceVendorLabel(dev) {
      if (!dev) return '';
      const parts = [dev.manufacturer, dev.model_name].filter(Boolean);
      return parts.filter((p, i) => parts.findIndex(x => String(x).toLowerCase() === String(p).toLowerCase()) === i).join(' ');
    },

    formatFirstSeenFull(ts) {
      if (!ts) return '';
      let str = String(ts).trim();
      if (!str.endsWith('Z') && !str.includes('+')) {
        str = str.replace(' ', 'T') + 'Z';
      }
      const d = new Date(str);
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleString(this.dateLocale(), {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
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
      const colors = this.getChartThemeColors();
      const ctx = canvas.getContext('2d');
      this.hogsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: this.t('charts.data_usage_label', { unit: unit }),
            data: data,
            backgroundColor: [
              'rgba(0, 103, 192, 0.85)',
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
              backgroundColor: colors.tooltipBg,
              titleColor: colors.tooltipTitle,
              bodyColor: colors.tooltipBody,
              borderColor: colors.tooltipBorder,
              borderWidth: 1,
              callbacks: {
                label: (context) => {
                  return this.t('charts.data_usage_tooltip', { value: context.parsed.x, unit: unit });
                }
              }
            }
          },
          scales: {
            x: {
              ticks: { color: colors.ticksColor, font: { family: colors.fontFamily } },
              grid: { color: colors.gridColor }
            },
            y: {
              ticks: { color: colors.isDark ? '#e2e8f0' : '#1c1c1c', font: { family: colors.fontFamily, size: 12 } },
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
        this.deviceSortDirection = (field === 'signal' || field === 'status' || field === 'download' || field === 'upload' || field === 'first_seen') ? 'desc' : 'asc';
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

      const colors = this.getChartThemeColors();
      const ctx = canvas.getContext('2d');
      this.speedtestChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: this.t('charts.download_mbps'),
              data: dl,
              borderColor: colors.isDark ? '#38bdf8' : '#0067c0',
              backgroundColor: colors.isDark ? 'rgba(56, 189, 248, 0.1)' : 'rgba(0, 103, 192, 0.1)',
              borderWidth: 2,
              tension: 0.3
            },
            {
              label: this.t('charts.upload_mbps'),
              data: ul,
              borderColor: colors.isDark ? '#10b981' : '#0f7b0f',
              backgroundColor: colors.isDark ? 'rgba(16, 185, 129, 0.1)' : 'rgba(15, 123, 15, 0.1)',
              borderWidth: 2,
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          plugins: {
            tooltip: {
              backgroundColor: colors.tooltipBg,
              titleColor: colors.tooltipTitle,
              bodyColor: colors.tooltipBody,
              borderColor: colors.tooltipBorder,
              borderWidth: 1
            },
            legend: {
              labels: { color: colors.ticksColor, font: { family: colors.fontFamily, size: 12 } }
            }
          },
          scales: {
            x: { ticks: { color: colors.ticksColor, font: { family: colors.fontFamily } }, grid: { color: colors.gridColor } },
            y: { title: { display: true, text: 'Mbps', color: colors.titleColor, font: { family: colors.fontFamily } }, ticks: { color: colors.ticksColor, font: { family: colors.fontFamily } }, grid: { color: colors.gridColor } }
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
        await this.loadSignalOverview();
      } catch (err) {
        console.error("Load speedtest data error:", err);
      }
    },

// =========================================================================
    // AUTO-UPDATE ENGINE (v1.04.00)
    // =========================================================================
    async checkForUpdates(force = false) {
      this.isCheckingUpdate = true;
      try {
        const res = await fetch(`/api/system/update/check?force=${force}`);
        if (res.ok) {
          const data = await res.json();
          this.updateInfo = data;
          if (data && data.update_available) {
            const versionId = data.latest_full_version || data.latest_version || 'new';
            const dismissed = sessionStorage.getItem('dismissed_update_' + versionId);
            this.showUpdatePrompt = !dismissed;
          } else {
            this.showUpdatePrompt = false;
          }
        }
      } catch (err) {
        console.warn("Update check failed:", err);
      } finally {
        this.isCheckingUpdate = false;
      }
    },

    dismissUpdatePrompt(temporary = true) {
      this.showUpdatePrompt = false;
      if (temporary && this.updateInfo) {
        const versionId = this.updateInfo.latest_full_version || this.updateInfo.latest_version || 'new';
        try {
          sessionStorage.setItem('dismissed_update_' + versionId, 'true');
        } catch (e) {}
      }
    },

    proceedUpdateFromPrompt() {
      this.openUpdateModal(false, false);
    },

    toggleFullReleaseNotes() {
      this.showFullReleaseNotes = !this.showFullReleaseNotes;
    },

    async fetchRuntimeInfo() {
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/runtime', { headers });
        this.runtimeInfo = res.ok ? await res.json() : null;
      } catch (err) {
        console.warn("Runtime info fetch failed:", err);
        this.runtimeInfo = null;
      }
    },

    runtimeEnvironmentLabel() {
      const env = this.runtimeInfo && this.runtimeInfo.environment;
      return env ? this.t(`settings_updates.env_${env}`) : '';
    },

    openUpdateModal(force = false, showFull = false) {
      this.showUpdateModal = true;
      this.copiedCliCommand = false;
      if (showFull !== undefined) {
        this.showFullReleaseNotes = !!showFull;
      }
      if (force || !this.updateInfo.latest_version) {
        this.checkForUpdates(true);
      }
    },

    async triggerAutoUpdate() {
      this.isTriggeringUpdate = true;
      this.updateProgressMsg = this.t('js.trigger_auto_update.pulling_new_docker_image');
      try {
        const res = await fetch('/api/system/update/trigger', { method: 'POST' });
        const data = await res.json();
        if (!data.success && data.method === 'manual') {
          this.isTriggeringUpdate = false;
          return;
        }
        
        this.updateProgressMsg = this.t('js.trigger_auto_update.restarting_container_auto_reconnecting');
        
        this.pollForHealthAndReload();
      } catch (err) {
        console.error("Auto-update trigger error:", err);
        this.pollForHealthAndReload();
      }
    },

// =========================================================================
    // SIGNAL QUALITY & MESH COVERAGE (v1.04.00)
    // =========================================================================
    buildLiveSignalOverviewFromDevices() {
      const parseRssi = (val) => {
        if (val === null || val === undefined || typeof val === 'boolean') return null;
        if (typeof val === 'number') {
          const iv = Math.round(val);
          return iv >= -120 && iv < 0 ? iv : null;
        }
        if (typeof val === 'object') {
          for (const k of ['rx_rssi', 'rssi', 'signal_dbm', 'signal_avg', 'signal', 'signal_strength']) {
            const p = parseRssi(val[k]);
            if (p !== null) return p;
          }
          return null;
        }
        const s = String(val).replace(/[\u2212\u2013\u2014]/g, '-');
        const m = s.match(/-\s*(\d+(?:\.\d+)?)/);
        if (!m) return null;
        const iv = -Math.round(parseFloat(m[1]));
        return iv >= -120 && iv < 0 ? iv : null;
      };

      const rawDevs = Array.isArray(this.devices) ? this.devices : [];
      const wirelessDevs = [];
      for (const d of rawDevs) {
        if (d.wireless === false || String(d.connection_type || '').toLowerCase() === 'wired') continue;
        const rssi = parseRssi(d.signal_rssi ?? d.rssi ?? d.signal ?? d.signal_avg ?? (d.connectivity && (d.connectivity.signal ?? d.connectivity.signal_avg ?? d.connectivity.rx_rssi)));
        const mac = String(d.mac || d.mac_address || '').toLowerCase().trim();
        if (!mac || rssi === null) continue;
        wirelessDevs.push({
          mac_address: mac,
          hostname: d.custom_name || d.nickname || d.hostname || mac,
          signal_rssi: rssi,
          frequency_band: d.frequency_band || d.wireless_band || 'Wi-Fi',
          channel: d.channel || null,
          connected_eero_name: d.connected_eero_name || d.eero_name || '',
          connected: Boolean(d.connected),
        });
      }
      if (wirelessDevs.length === 0) return null;
      const active = wirelessDevs.filter(d => d.connected);
      const target = active.length > 0 ? active : wirelessDevs;
      const total = target.length;
      const avg = Math.round((target.reduce((acc, d) => acc + d.signal_rssi, 0) / total) * 10) / 10;
      const exc = target.filter(d => d.signal_rssi >= -50);
      const good = target.filter(d => d.signal_rssi >= -65 && d.signal_rssi < -50);
      const fair = target.filter(d => d.signal_rssi >= -75 && d.signal_rssi < -65);
      const weak = target.filter(d => d.signal_rssi < -75);
      return {
        total_wireless_devices: total,
        average_rssi: avg,
        excellent_count: exc.length,
        good_count: good.length,
        fair_count: fair.length,
        weak_count: weak.length,
        excellent_pct: Math.round((exc.length / total) * 1000) / 10,
        good_pct: Math.round((good.length / total) * 1000) / 10,
        fair_pct: Math.round((fair.length / total) * 1000) / 10,
        weak_pct: Math.round((weak.length / total) * 1000) / 10,
        weak_devices: weak,
        devices: wirelessDevs,
      };
    },

    async loadSignalOverview() {
      try {
        const res = await fetch('/api/metrics/signal/overview', {
          headers: this.getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success' && data.overview) {
            let ov = data.overview;
            if ((!ov.total_wireless_devices || ov.total_wireless_devices === 0) && Array.isArray(this.devices) && this.devices.length > 0) {
              const fallbackOv = this.buildLiveSignalOverviewFromDevices();
              if (fallbackOv) ov = fallbackOv;
            }
            this.signalOverview = ov;
            if (!this.selectedSignalDeviceMac && this.signalOverview.devices && this.signalOverview.devices.length > 0) {
              this.selectedSignalDeviceMac = this.signalOverview.devices[0].mac_address;
              await this.loadDeviceSignalHistory();
            }
            return;
          }
        }
        const fallbackOv = this.buildLiveSignalOverviewFromDevices();
        if (fallbackOv) {
          this.signalOverview = fallbackOv;
          if (!this.selectedSignalDeviceMac && this.signalOverview.devices && this.signalOverview.devices.length > 0) {
            this.selectedSignalDeviceMac = this.signalOverview.devices[0].mac_address;
            await this.loadDeviceSignalHistory();
          }
        }
      } catch (err) {
        console.error("Load signal overview error:", err);
      }
    },

    async loadDeviceSignalHistory() {
      if (!this.selectedSignalDeviceMac) return;
      this.signalLoading = true;
      try {
        const res = await fetch(`/api/metrics/signal/history?mac=${encodeURIComponent(this.selectedSignalDeviceMac)}&hours=${this.signalHistoryHours}`, {
          headers: this.getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success' && Array.isArray(data.history) && data.history.length > 0) {
            this.renderSignalChart(data.history);
            return;
          }
        }
        const liveDev = (this.signalOverview && Array.isArray(this.signalOverview.devices))
          ? this.signalOverview.devices.find(d => String(d.mac_address || '').toLowerCase() === String(this.selectedSignalDeviceMac || '').toLowerCase())
          : null;
        if (liveDev && typeof liveDev.signal_rssi === 'number') {
          this.renderSignalChart([{
            timestamp: new Date().toISOString(),
            mac_address: liveDev.mac_address,
            hostname: liveDev.hostname,
            signal_rssi: liveDev.signal_rssi,
            frequency_band: liveDev.frequency_band,
            channel: liveDev.channel,
            connected_eero_name: liveDev.connected_eero_name
          }]);
        }
      } catch (err) {
        console.error("Load device signal history error:", err);
      } finally {
        this.signalLoading = false;
      }
    },

    formatLocalDateTime(isoStr, includeDate = false) {
      if (!isoStr) return '--';
      let clean = String(isoStr).trim();
      if (clean && !clean.endsWith('Z') && !clean.includes('+')) {
        clean = clean.replace(' ', 'T') + 'Z';
      }
      try {
        const d = new Date(clean);
        if (isNaN(d.getTime())) return isoStr;
        if (includeDate) {
          return d.toLocaleDateString(this.dateLocale(), { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString(this.dateLocale(), { hour: '2-digit', minute: '2-digit' });
        }
        return d.toLocaleTimeString(this.dateLocale(), { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return isoStr;
      }
    },

    renderSignalChart(history) {
      const canvas = document.getElementById('deviceSignalChart');
      if (!canvas) return;
      if (this.signalChartInstance) {
        this.signalChartInstance.destroy();
        this.signalChartInstance = null;
      }

      const p = canvas.parentElement;
      if (p) {
        canvas.width = p.clientWidth || 500;
        canvas.height = p.clientHeight || 260;
      }

      const labels = (history || []).map(pt => this.formatLocalDateTime(pt.timestamp, false));
      const rssiValues = (history || []).map(pt => pt.signal_rssi);

      const colors = this.getChartThemeColors();
      const ctx = canvas.getContext('2d');
      this.signalChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels.length > 0 ? labels : ['--'],
          datasets: [
            {
              label: this.t('charts.rssi_dbm'),
              data: rssiValues.length > 0 ? rssiValues : [null],
              borderColor: colors.isDark ? '#38bdf8' : '#0067c0',
              backgroundColor: colors.isDark ? 'rgba(56, 189, 248, 0.12)' : 'rgba(0, 103, 192, 0.10)',
              borderWidth: 2.5,
              tension: 0.3,
              fill: true,
              pointRadius: labels.length > 30 ? 1 : 3,
              pointHoverRadius: 5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: false,
          scales: {
            y: {
              min: -90,
              max: -30,
              grid: { color: colors.gridColor },
              ticks: {
                color: colors.ticksColor,
                font: { family: colors.fontFamily },
                callback: (v) => `${v} dBm`
              }
            },
            x: {
              grid: { color: colors.gridColor },
              ticks: { color: colors.ticksColor, font: { family: colors.fontFamily }, maxTicksLimit: 10 }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: colors.tooltipBg,
              titleColor: colors.tooltipTitle,
              bodyColor: colors.tooltipBody,
              borderColor: colors.tooltipBorder,
              borderWidth: 1,
              callbacks: {
                title: (items) => {
                  if (!items || items.length === 0) return '';
                  const pt = (history || [])[items[0].dataIndex];
                  return pt ? this.formatLocalDateTime(pt.timestamp, true) : '';
                },
                label: (ctx) => this.t('charts.rssi_tooltip', { value: ctx.parsed.y })
              }
            }
          }
        }
      });
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
          this.showToast(this.t('toasts.speedtest_completed'), `↓ ${json.result.download_mbps} Mbps | ↑ ${json.result.upload_mbps} Mbps`, "success");
          await this.loadSpeedtestData();
        }
      } catch (err) {
        clearInterval(interval);
        this.showToast(this.t('toasts.speedtest_error'), err.message, "error");
      } finally {
        setTimeout(() => {
          this.speedtestRunning = false;
          this.speedtestProgress = 0;
        }, 1000);
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
            const found = currentId ? this.manualSections.find(s => s.id === currentId) : null;
            this.selectManualSection(found || this.manualSections[0]);
          }
        }
      } catch (err) {
        console.error("Load manual error:", err);
      }
    },

    selectManualSection(section) {
      if (!section) return;
      this.selectedManualSection = section;
      this.helpModalTitle = section.title || '';
      this.helpModalContent = this.renderSimpleMarkdown(section.content || '');
    },

    selectManualSectionById(sectionId) {
      if (!this.manualSections || !this.manualSections.length) return;
      const found = this.manualSections.find(s => s.id === sectionId);
      if (found) {
        this.selectManualSection(found);
      }
    },

    get currentManualSectionIndex() {
      if (!this.selectedManualSection || !this.manualSections || !this.manualSections.length) return 0;
      const idx = this.manualSections.findIndex(s => s.id === this.selectedManualSection.id);
      return idx >= 0 ? idx : 0;
    },

    prevManualSection() {
      const idx = this.currentManualSectionIndex;
      if (idx > 0 && this.manualSections && this.manualSections[idx - 1]) {
        this.selectManualSection(this.manualSections[idx - 1]);
      }
    },

    nextManualSection() {
      const idx = this.currentManualSectionIndex;
      if (this.manualSections && idx < this.manualSections.length - 1 && this.manualSections[idx + 1]) {
        this.selectManualSection(this.manualSections[idx + 1]);
      }
    },

    get filteredManualSections() {
      if (!this.manualSections) return [];
      if (!this.manualSearchQuery) return this.manualSections;
      const q = this.manualSearchQuery.toLowerCase().trim();
      return this.manualSections.filter(s => 
        (s.title && s.title.toLowerCase().includes(q)) || 
        (s.summary && s.summary.toLowerCase().includes(q)) ||
        (s.content && s.content.toLowerCase().includes(q))
      );
    },

    async openContextHelp(sectionId = null) {
      try {
        if (!this.manualSections || this.manualSections.length === 0) {
          await this.loadManualSections();
        }
        if (sectionId && this.manualSections && this.manualSections.length > 0) {
          const found = this.manualSections.find(s => s.id === sectionId);
          if (found) {
            this.selectManualSection(found);
          } else {
            this.selectManualSection(this.manualSections[0]);
          }
        } else if (this.manualSections && this.manualSections.length > 0 && !this.selectedManualSection) {
          this.selectManualSection(this.manualSections[0]);
        }
        this.manualSearchQuery = '';
        this.showHelpModal = true;
      } catch (err) {
        console.error("Open context help error:", err);
      }
    },

// =========================================================================
    // eeroOS RELEASE NOTES & COMMUNITY UPDATES (v1.6.0)
    // =========================================================================
    async fetchEeroNews(force = false) {
      this.eeroNewsLoading = true;
      this.eeroNewsError = null;
      try {
        const url = force ? '/api/system/eero-news/refresh' : '/api/system/eero-news';
        const method = force ? 'POST' : 'GET';
        const res = await fetch(url, { method });
        if (res.ok) {
          const data = await res.json();
          this.eeroNewsData = data;
          if (data.releases && data.releases.length > 0 && Object.keys(this.eeroNewsExpandedVersions).length === 0) {
            this.eeroNewsExpandedVersions[data.releases[0].version] = true;
          }
        } else {
          this.eeroNewsError = this.t('eero_news.load_error');
        }
      } catch (err) {
        console.error("fetchEeroNews error:", err);
        this.eeroNewsError = err.message || this.t('eero_news.connection_error');
      } finally {
        this.eeroNewsLoading = false;
      }
    },

    setEeroNewsFilter(filterName) {
      this.eeroNewsFilter = filterName;
      this.eeroNewsShowAllReleases = false;
    },

    toggleShowAllReleases() {
      this.eeroNewsShowAllReleases = !this.eeroNewsShowAllReleases;
    },

    toggleReleaseAccordion(version) {
      this.eeroNewsExpandedVersions[version] = !this.eeroNewsExpandedVersions[version];
    },

    expandAllReleases() {
      if (this.eeroNewsData && this.eeroNewsData.releases) {
        const expanded = {};
        this.eeroNewsData.releases.forEach(r => {
          expanded[r.version] = true;
        });
        this.eeroNewsExpandedVersions = expanded;
        this.eeroNewsShowAllReleases = true;
      }
    },

    collapseAllReleases() {
      this.eeroNewsExpandedVersions = {};
    },

    get filteredEeroReleases() {
      if (!this.eeroNewsData || !this.eeroNewsData.releases) return [];
      let list = this.eeroNewsData.releases;
      const q = (this.eeroNewsSearchQuery || '').toLowerCase().trim();
      if (q) {
        list = list.filter(r => {
          const verMatch = (r.version || '').toLowerCase().includes(q);
          const dateMatch = (r.release_date || '').toLowerCase().includes(q);
          const summaryMatch = (r.summary || '').toLowerCase().includes(q) || (this.localized(r, 'summary') || '').toLowerCase().includes(q);
          const contentMatch = (r.content || []).some(c => c.toLowerCase().includes(q));
          return verMatch || dateMatch || summaryMatch || contentMatch;
        });
      }
      if (this.eeroNewsFilter === 'security') {
        list = list.filter(r => r.is_security_patch || (r.tags || []).some(tg => this.newsTagIs(tg, 'security')));
      } else if (this.eeroNewsFilter === 'wifi7') {
        list = list.filter(r => (r.tags || []).some(tg => this.newsTagIs(tg, 'wifi7_6ghz')));
      } else if (this.eeroNewsFilter === 'stability') {
        list = list.filter(r => (r.tags || []).some(tg => this.newsTagIs(tg, 'stability')));
      }
      return list;
    },

    get visibleEeroReleases() {
      const list = this.filteredEeroReleases;
      if (this.eeroNewsShowAllReleases) {
        return list;
      }
      return list.slice(0, this.eeroNewsDefaultLimit);
    },

    get remainingEeroReleasesCount() {
      const total = this.filteredEeroReleases.length;
      return Math.max(0, total - this.eeroNewsDefaultLimit);
    },

    async openChangelogModal() {
      this.changelogLoading = true;
      this.showChangelogModal = true;
      try {
        const lang = this.currentLanguage || 'en';
        const res = await fetch(`/api/manual/changelog?lang=${lang}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (json.status === 'success' && json.content) {
          this.changelogVersion = json.version || '1.6.0';
          this.changelogContent = this.renderSimpleMarkdown(json.content);
        } else {
          throw new Error(json.message || "Failed to load");
        }
      } catch (err) {
        console.error("Open changelog error:", err);
        const errMsg = this.t('changelog_modal.error_loading');
        this.changelogContent = `<p class="text-rose-400 font-medium py-4">${errMsg}</p>`;
      } finally {
        this.changelogLoading = false;
      }
    },

    openHealthModal() {
      if (!this.healthDetails && this.fetchOverview) {
        this.fetchOverview();
      }
      this.showHealthModal = true;
    },

    async refreshHealthDiagnostics() {
      await this.manualRefresh();
    },

    getHealthPillarSummary(pillarKey) {
      const pillar = this.healthDetails?.pillars?.[pillarKey];
      if (!pillar) return '';
      const lang = this.currentLanguage || 'en';
      return pillar.summary_i18n?.[lang] || pillar.summary || '';
    },

    getHealthPenaltyTitle(p) {
      if (!p) return '';
      const lang = this.currentLanguage || 'en';
      return p.title_i18n?.[lang] || p.title || '';
    },

    getHealthPenaltyDesc(p) {
      if (!p) return '';
      const lang = this.currentLanguage || 'en';
      return p.description_i18n?.[lang] || p.description || '';
    },

    getHealthRecommendationText(rec, idx) {
      const lang = this.currentLanguage || 'en';
      const recsI18n = this.healthDetails?.recommendations_i18n;
      if (recsI18n && recsI18n[idx] && recsI18n[idx][lang]) {
        return recsI18n[idx][lang];
      }
      if (typeof rec === 'object' && rec !== null && rec[lang]) {
        return rec[lang];
      }
      return rec || '';
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
        .replace(/\[(.*?)\]\((.*?)\)/g, (match, label, href) => {
          const cleanHref = (href || '').trim();
          if (/^(?:https?:\/\/|mailto:|\/(?!\/)|#)/i.test(cleanHref)) {
            return `<a href="${cleanHref}" target="_blank" rel="noopener noreferrer" class="text-sky-400 hover:text-sky-300 underline font-medium">${label}</a>`;
          }
          return `<span class="text-sky-400 font-medium">${label}</span>`;
        })
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
    // DEVICE DATA USAGE INSIGHTS SUITE & TOP HOGS (v1.5.0)
    // =========================================================================
    async fetchTopHogs(period = null) {
      if (period) {
        this.topHogsPeriod = period;
      }
      const activePeriod = this.topHogsPeriod || 'daily';
      this.topHogsLoading = true;
      try {
        const res = await fetch(`/api/network/top-hogs?period=${activePeriod}&limit=30`);
        const data = await res.json();
        if (data.status === 'success') {
          this.topHogsList = data.top_hogs || [];
        }
      } catch (err) {
        console.error('Fetch top hogs error:', err);
      } finally {
        this.topHogsLoading = false;
      }
    },

    async loadDeviceUsage(mac = null, period = null, resolution = null) {
      const targetMac = mac || (this.selectedDevice ? (this.selectedDevice.mac || this.selectedDevice.mac_address) : '');
      if (!targetMac) return;
      if (period) {
        this.deviceUsagePeriod = period;
      }
      if (resolution) {
        this.deviceUsageResolution = resolution;
      }
      const activePeriod = this.deviceUsagePeriod || 'daily';
      const activeRes = this.deviceUsageResolution || 15;
      this.deviceUsageLoading = true;
      try {
        const res = await fetch(`/api/devices/${encodeURIComponent(targetMac)}/usage?period=${activePeriod}&resolution=${activeRes}`);
        const data = await res.json();
        if (data.status === 'success') {
          this.deviceUsageData = data.data;
          this.$nextTick(() => {
            this.renderDeviceUsageChart(data.data);
          });
        }
      } catch (err) {
        console.error('Load device usage error:', err);
      } finally {
        this.deviceUsageLoading = false;
      }
    },

    openDeviceDetailByMac(mac) {
      if (!mac) return;
      const dev = (this.devices || []).find(d => ((d.mac || d.mac_address || '').toLowerCase() === mac.toLowerCase()));
      if (dev) {
        this.openDeviceModal(dev);
        this.deviceDetailTab = 'usage';
        this.loadDeviceUsage(mac, this.deviceUsagePeriod || 'daily');
      }
    },

    renderDeviceUsageChart(usageData) {
      const canvas = document.getElementById('deviceUsageChartCanvas');
      if (!canvas) return;
      if (this.deviceUsageChart) {
        this.deviceUsageChart.destroy();
        this.deviceUsageChart = null;
      }
      if (!usageData || !usageData.data_points || usageData.data_points.length === 0) return;

      const isDark = document.documentElement.classList.contains('dark');
      const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)';
      const textColor = isDark ? '#94a3b8' : '#64748b';

      const labels = usageData.data_points.map(p => {
        const d = new Date(p.timestamp);
        return usageData.period === 'daily' 
          ? d.toLocaleTimeString(this.dateLocale(), { hour: '2-digit', minute: '2-digit' })
          : d.toLocaleDateString(this.dateLocale(), { day: '2-digit', month: '2-digit' });
      });

      const downRates = usageData.data_points.map(p => Number(p.download_mbps !== undefined ? p.download_mbps : (p.download_rate_mbps || 0)));
      const upRates = usageData.data_points.map(p => Number(p.upload_mbps !== undefined ? p.upload_mbps : (p.upload_rate_mbps || 0)));

      this.deviceUsageChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: this.t('charts.download_mbps'),
              data: downRates,
              borderColor: '#0067c0',
              backgroundColor: isDark ? 'rgba(0, 103, 192, 0.25)' : 'rgba(0, 103, 192, 0.15)',
              fill: true,
              tension: 0.35,
              pointRadius: 2,
              pointHoverRadius: 5,
              borderWidth: 2
            },
            {
              label: this.t('charts.upload_mbps'),
              data: upRates,
              borderColor: '#10b981',
              backgroundColor: isDark ? 'rgba(16, 185, 129, 0.25)' : 'rgba(16, 185, 129, 0.15)',
              fill: true,
              tension: 0.35,
              pointRadius: 2,
              pointHoverRadius: 5,
              borderWidth: 2
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              display: true,
              position: 'top',
              labels: { color: textColor, boxWidth: 12, font: { size: 11 } }
            },
            tooltip: {
              backgroundColor: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(255, 255, 255, 0.95)',
              titleColor: isDark ? '#f8fafc' : '#0f172a',
              bodyColor: isDark ? '#cbd5e1' : '#334155',
              borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
              borderWidth: 1,
              padding: 10
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { size: 10 } }
            },
            y: {
              min: 0,
              beginAtZero: true,
              grid: { color: gridColor },
              ticks: { color: textColor, font: { size: 10 } },
              title: { display: true, text: 'Mbps', color: textColor, font: { size: 10 } }
            }
          }
        }
      });
    },

// =========================================================================
    // ANALYTICS, DISTRIBUTION & ISP SLA (v1.5.0)
    // =========================================================================
    async loadAnalyticsData(force = false) {
      if (this.analyticsLoading && !force) return;
      this.analyticsLoading = true;
      try {
        await Promise.all([
          this.fetchAnalyticsDistribution(),
          this.fetchAnalyticsSla(this.analyticsSlaDays, false)
        ]);
        if (this.$nextTick) {
          this.$nextTick(() => {
            setTimeout(() => {
              this.renderAnalyticsCharts();
            }, 80);
          });
        } else {
          setTimeout(() => {
            this.renderAnalyticsCharts();
          }, 80);
        }
      } catch (err) {
        console.error("Load analytics data error:", err);
      } finally {
        this.analyticsLoading = false;
      }
    },

    async fetchAnalyticsDistribution() {
      try {
        const res = await fetch('/api/analytics/distribution');
        const data = await res.json();
        if (data.status === 'success') {
          this.analyticsDistribution = data;
        }
      } catch (err) {
        console.error("Fetch distribution error:", err);
      }
    },

    async fetchAnalyticsSla(days = 30, renderImmediately = true) {
      this.analyticsSlaDays = days;
      try {
        const res = await fetch(`/api/analytics/isp-sla?days=${days}`);
        const data = await res.json();
        if (data.status === 'success' && data.sla) {
          this.analyticsSla = data.sla;
          if (renderImmediately) {
            if (this.$nextTick) {
              this.$nextTick(() => {
                setTimeout(() => {
                  this.renderSlaChart();
                }, 50);
              });
            } else {
              setTimeout(() => {
                this.renderSlaChart();
              }, 50);
            }
          }
        }
      } catch (err) {
        console.error("Fetch SLA error:", err);
      }
    },

    renderAnalyticsCharts() {
      this.renderFrequenciesChart();
      this.renderNodeLoadChart();
      this.renderCategoriesChart();
      this.renderVendorsChart();
      this.renderSlaChart();
    },

    formatDevicesTooltipAfterBody(devicesList) {
      if (!devicesList || devicesList.length === 0) return [];
      const header = (this.t('js.format_devices_tooltip_after_body.devices')) + devicesList.length + '):';
      const lines = ['', header];
      const maxShow = 15;
      devicesList.slice(0, maxShow).forEach(d => lines.push(`  • ${d}`));
      if (devicesList.length > maxShow) {
        lines.push(this.t('js.format_devices_tooltip_after_body.and_more', { length: devicesList.length - maxShow }));
      }
      return lines;
    },

    formatCategoryName(category) {
      if (!category) return this.t('devices.cat_other');
      const cat = String(category).trim();
      
      if (cat === 'Altro' || cat.toLowerCase() === 'other') {
        return this.t('devices.cat_other');
      }
      if (cat === 'Computer') {
        return this.t('devices.cat_computer');
      }
      if (cat === 'Mobile') {
        return this.t('devices.cat_mobile');
      }
      if (cat === 'Smart Home') {
        return this.t('devices.cat_smarthome');
      }
      if (cat === 'Intrattenimento' || cat.toLowerCase() === 'entertainment') {
        return this.t('devices.cat_entertainment');
      }
      if (cat === 'Gaming') {
        return this.t('devices.cat_gaming');
      }
      if (cat === 'Server/Rete' || cat === 'Server/NAS' || cat.toLowerCase() === 'server') {
        return this.t('devices.cat_server');
      }
      return cat;
    },

    formatVendorName(vendor) {
      if (!vendor) return this.t('devices.cat_other');
      const v = String(vendor).trim();
      if (v === 'Altro' || v.toLowerCase() === 'other') {
        return this.t('devices.cat_other');
      }
      return v;
    },

    renderFrequenciesChart() {
      try {
        const canvas = document.getElementById('analyticsFrequenciesChart');
        if (!canvas) return;
        if (typeof Chart !== 'undefined' && Chart.getChart(canvas)) {
          Chart.getChart(canvas).destroy();
        }
        if (this.analyticsChartInstances && this.analyticsChartInstances['frequencies']) {
          try { this.analyticsChartInstances['frequencies'].destroy(); } catch (e) {}
          delete this.analyticsChartInstances['frequencies'];
        }

        const freqs = (this.analyticsDistribution && this.analyticsDistribution.frequencies) ? this.analyticsDistribution.frequencies : [];
        if (freqs.length === 0) return;

        const labels = freqs.map(f => f.band);
        const data = freqs.map(f => f.count);
        const colors = this.getChartThemeColors();

        this.analyticsChartInstances['frequencies'] = new Chart(canvas, {
          type: 'doughnut',
          data: {
            labels: labels,
            datasets: [{
              data: data,
              backgroundColor: [
                '#38bdf8', // 6 GHz
                '#0067c0', // 5 GHz
                '#818cf8', // 2.4 GHz
                '#10b981'  // Ethernet
              ],
              borderColor: colors.isDark ? '#262626' : '#ffffff',
              borderWidth: 2
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: {
                  color: colors.isDark ? '#cbd5e1' : '#334155',
                  font: { family: colors.fontFamily, size: 11 },
                  boxWidth: 12,
                  padding: 12
                }
              },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                titleColor: '#ffffff',
                titleFont: { family: colors.fontFamily, weight: 'bold', size: 13 },
                bodyColor: '#e2e8f0',
                bodyFont: { family: colors.fontFamily, size: 12 },
                borderColor: 'rgba(255, 255, 255, 0.15)',
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                cornerRadius: 8,
                _customDark: true,
                callbacks: {
                  label: (ctx) => {
                    const count = ctx.raw || 0;
                    const pct = freqs[ctx.dataIndex]?.percentage || 0;
                    return (this.t('js.render_frequencies_chart.connected_clients')) + `${count} (${pct}%)`;
                  },
                  afterBody: (items) => {
                    if (!items || items.length === 0) return [];
                    const item = freqs[items[0].dataIndex];
                    return this.formatDevicesTooltipAfterBody(item ? item.devices : []);
                  }
                }
              }
            },
            cutout: '65%'
          }
        });
      } catch (e) {
        console.error("Error rendering frequencies chart:", e);
      }
    },

    renderNodeLoadChart() {
      try {
        const canvas = document.getElementById('analyticsNodeLoadChart');
        if (!canvas) return;
        if (typeof Chart !== 'undefined' && Chart.getChart(canvas)) {
          Chart.getChart(canvas).destroy();
        }
        if (this.analyticsChartInstances && this.analyticsChartInstances['nodeLoad']) {
          try { this.analyticsChartInstances['nodeLoad'].destroy(); } catch (e) {}
          delete this.analyticsChartInstances['nodeLoad'];
        }

        const nodes = (this.analyticsDistribution && this.analyticsDistribution.node_load) ? this.analyticsDistribution.node_load : [];
        if (nodes.length === 0) return;

        const labels = nodes.map(n => n.name);
        const data = nodes.map(n => n.client_count);
        const colors = this.getChartThemeColors();

        this.analyticsChartInstances['nodeLoad'] = new Chart(canvas, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: this.t('dashboard.connected_devices'),
              data: data,
              backgroundColor: 'rgba(0, 103, 192, 0.8)',
              borderColor: '#0067c0',
              borderWidth: 1,
              borderRadius: 6
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
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                titleColor: '#ffffff',
                titleFont: { family: colors.fontFamily, weight: 'bold', size: 13 },
                bodyColor: '#e2e8f0',
                bodyFont: { family: colors.fontFamily, size: 12 },
                borderColor: 'rgba(255, 255, 255, 0.15)',
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                cornerRadius: 8,
                _customDark: true,
                callbacks: {
                  label: (ctx) => {
                    const val = ctx.parsed.x !== undefined ? ctx.parsed.x : ctx.raw;
                    return (this.t('js.render_node_load_chart.connected_clients')) + val;
                  },
                  afterBody: (items) => {
                    if (!items || items.length === 0) return [];
                    const node = nodes[items[0].dataIndex];
                    return this.formatDevicesTooltipAfterBody(node ? node.devices : []);
                  }
                }
              }
            },
            scales: {
              x: {
                beginAtZero: true,
                ticks: { color: colors.ticksColor, precision: 0 },
                grid: { color: colors.gridColor }
              },
              y: {
                ticks: { color: colors.isDark ? '#cbd5e1' : '#334155', font: { family: colors.fontFamily, size: 11 } },
                grid: { display: false }
              }
            }
          }
        });
      } catch (e) {
        console.error("Error rendering node load chart:", e);
      }
    },

    renderCategoriesChart() {
      try {
        const canvas = document.getElementById('analyticsCategoriesChart');
        if (!canvas) return;
        if (typeof Chart !== 'undefined' && Chart.getChart(canvas)) {
          Chart.getChart(canvas).destroy();
        }
        if (this.analyticsChartInstances && this.analyticsChartInstances['categories']) {
          try { this.analyticsChartInstances['categories'].destroy(); } catch (e) {}
          delete this.analyticsChartInstances['categories'];
        }

        const cats = (this.analyticsDistribution && this.analyticsDistribution.categories) ? this.analyticsDistribution.categories : [];
        if (cats.length === 0) return;

        const labels = cats.map(c => this.formatCategoryName(c.category));
        const data = cats.map(c => c.count);
        const colors = this.getChartThemeColors();

        this.analyticsChartInstances['categories'] = new Chart(canvas, {
          type: 'doughnut',
          data: {
            labels: labels,
            datasets: [{
              data: data,
              backgroundColor: [
                '#0067c0', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#64748b'
              ],
              borderColor: colors.isDark ? '#262626' : '#ffffff',
              borderWidth: 2
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: {
                  color: colors.isDark ? '#cbd5e1' : '#334155',
                  font: { family: colors.fontFamily, size: 11 },
                  boxWidth: 12,
                  padding: 12
                }
              },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                titleColor: '#ffffff',
                titleFont: { family: colors.fontFamily, weight: 'bold', size: 13 },
                bodyColor: '#e2e8f0',
                bodyFont: { family: colors.fontFamily, size: 12 },
                borderColor: 'rgba(255, 255, 255, 0.15)',
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                cornerRadius: 8,
                _customDark: true,
                callbacks: {
                  label: (ctx) => {
                    const count = ctx.raw || 0;
                    const pct = cats[ctx.dataIndex]?.percentage || 0;
                    const catName = this.formatCategoryName(cats[ctx.dataIndex]?.category || '');
                    return `${catName}: ${count} (${pct}%)`;
                  },
                  afterBody: (items) => {
                    if (!items || items.length === 0) return [];
                    const item = cats[items[0].dataIndex];
                    return this.formatDevicesTooltipAfterBody(item ? item.devices : []);
                  }
                }
              }
            },
            cutout: '65%'
          }
        });
      } catch (e) {
        console.error("Error rendering categories chart:", e);
      }
    },

    renderVendorsChart() {
      try {
        const canvas = document.getElementById('analyticsVendorsChart');
        if (!canvas) return;
        if (typeof Chart !== 'undefined' && Chart.getChart(canvas)) {
          Chart.getChart(canvas).destroy();
        }
        if (this.analyticsChartInstances && this.analyticsChartInstances['vendors']) {
          try { this.analyticsChartInstances['vendors'].destroy(); } catch (e) {}
          delete this.analyticsChartInstances['vendors'];
        }

        const vends = ((this.analyticsDistribution && this.analyticsDistribution.vendors) ? this.analyticsDistribution.vendors : []).slice(0, 6);
        if (vends.length === 0) return;

        const labels = vends.map(v => this.formatVendorName(v.vendor));
        const data = vends.map(v => v.count);
        const colors = this.getChartThemeColors();

        this.analyticsChartInstances['vendors'] = new Chart(canvas, {
          type: 'bar',
          data: {
            labels: labels,
            datasets: [{
              label: this.t('nav.devices'),
              data: data,
              backgroundColor: 'rgba(99, 102, 241, 0.8)',
              borderColor: '#6366f1',
              borderWidth: 1,
              borderRadius: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.96)',
                titleColor: '#ffffff',
                titleFont: { family: colors.fontFamily, weight: 'bold', size: 13 },
                bodyColor: '#e2e8f0',
                bodyFont: { family: colors.fontFamily, size: 12 },
                borderColor: 'rgba(255, 255, 255, 0.15)',
                borderWidth: 1,
                padding: 10,
                boxPadding: 4,
                cornerRadius: 8,
                _customDark: true,
                callbacks: {
                  label: (ctx) => {
                    const val = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.raw;
                    const pct = vends[ctx.dataIndex]?.percentage || 0;
                    const vName = this.formatVendorName(vends[ctx.dataIndex]?.vendor || '');
                    return `${vName}: ${val} (${pct}%)`;
                  },
                  afterBody: (items) => {
                    if (!items || items.length === 0) return [];
                    const item = vends[items[0].dataIndex];
                    return this.formatDevicesTooltipAfterBody(item ? item.devices : []);
                  }
                }
              }
            },
            scales: {
              x: {
                ticks: { color: colors.ticksColor, font: { family: colors.fontFamily, size: 10 } },
                grid: { display: false }
              },
              y: {
                beginAtZero: true,
                ticks: { color: colors.ticksColor, precision: 0 },
                grid: { color: colors.gridColor }
              }
            }
          }
        });
      } catch (e) {
        console.error("Error rendering vendors chart:", e);
      }
    },

    renderSlaChart() {
      try {
        const canvas = document.getElementById('analyticsSlaChart');
        if (!canvas) return;
        if (typeof Chart !== 'undefined' && Chart.getChart(canvas)) {
          Chart.getChart(canvas).destroy();
        }
        if (this.analyticsChartInstances && this.analyticsChartInstances['sla']) {
          try { this.analyticsChartInstances['sla'].destroy(); } catch (e) {}
          delete this.analyticsChartInstances['sla'];
        }

        const points = (this.analyticsSla && this.analyticsSla.history_points) ? this.analyticsSla.history_points : [];
        if (points.length === 0) return;

        const labels = points.map(p => {
          const d = new Date(p.timestamp);
          return isNaN(d.getTime()) ? p.timestamp : d.toLocaleDateString(this.dateLocale(), { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });
        const dlData = points.map(p => p.download_mbps);
        const ulData = points.map(p => p.upload_mbps);
        const pingData = points.map(p => p.ping_ms);
        const colors = this.getChartThemeColors();

        this.analyticsChartInstances['sla'] = new Chart(canvas, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [
              {
                label: this.t('charts.download_mbps'),
                data: dlData,
                borderColor: '#0067c0',
                backgroundColor: 'rgba(0, 103, 192, 0.1)',
                borderWidth: 2,
                pointRadius: 2,
                tension: 0.3,
                fill: true,
                yAxisID: 'y'
              },
              {
                label: this.t('charts.upload_mbps'),
                data: ulData,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.05)',
                borderWidth: 2,
                pointRadius: 2,
                tension: 0.3,
                fill: true,
                yAxisID: 'y'
              },
              {
                label: this.t('charts.ping_ms'),
                data: pingData,
                borderColor: '#f59e0b',
                borderWidth: 1.5,
                pointRadius: 2,
                borderDash: [4, 4],
                tension: 0.3,
                fill: false,
                yAxisID: 'y1'
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
              legend: {
                position: 'top',
                labels: { color: colors.isDark ? '#cbd5e1' : '#334155', font: { family: colors.fontFamily, size: 11 } }
              }
            },
            scales: {
              x: {
                ticks: { color: colors.ticksColor, maxTicksLimit: 8, font: { size: 10 } },
                grid: { color: colors.gridColor }
              },
              y: {
                type: 'linear',
                display: true,
                position: 'left',
                beginAtZero: true,
                ticks: { color: colors.ticksColor, font: { size: 10 } },
                grid: { color: colors.gridColor },
                title: { display: true, text: this.t('charts.axis_throughput_mbps'), color: colors.ticksColor, font: { size: 10 } }
              },
              y1: {
                type: 'linear',
                display: true,
                position: 'right',
                beginAtZero: true,
                ticks: { color: '#f59e0b', font: { size: 10 } },
                grid: { drawOnChartArea: false },
                title: { display: true, text: this.t('charts.axis_latency_ms'), color: '#f59e0b', font: { size: 10 } }
              }
            }
          }
        });
      } catch (e) {
        console.error("Error rendering SLA chart:", e);
      }
    },

    async exportData(dataType, format) {
      this.exportLoading = true;
      try {
        const url = `/api/analytics/export/${encodeURIComponent(dataType)}?format=${encodeURIComponent(format)}`;
        const res = await fetch(url);
        if (!res.ok) {
          throw new Error(this.t('js.export_data.export_failed', { status: res.statusText }));
        }
        const blob = await res.blob();
        const disposition = res.headers.get('Content-Disposition') || '';
        let filename = `eero_${dataType}_export.${format}`;
        const match = disposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) {
          filename = match[1];
        }
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        const succTitle = this.t('js.export_data.data_export');
        const succMsg = this.t('js.export_data.file_downloaded_successfully', { filename: filename });
        this.showToast(succTitle, succMsg, 'success');
      } catch (err) {
        console.error("Export error:", err);
        const errTitle = this.t('js.export_data.export_error');
        this.showToast(errTitle, err.message, 'error');
      } finally {
        this.exportLoading = false;
      }
    },

// =========================================================================
    // MODULE 3: BANDWIDTH HOGS MULTI-FILTERS COMPUTED
    // =========================================================================
    // Distinct device categories for the hogs category filter; values stay in
    // their stored (Italian) form and are translated for display via formatCategoryName().
    get availableCategories() {
      const devList = Array.isArray(this.devices) ? this.devices : [];
      if (devList.length === 0) {
        return ['Computer', 'Mobile', 'Smart Home', 'Intrattenimento', 'Server/Rete', 'Gaming', 'Altro'];
      }
      const cats = new Set(devList.map(d => (d && d.category) ? d.category : 'Altro'));
      return [...cats].sort((a, b) => {
        const nameA = (typeof this.formatCategoryName === 'function') ? (this.formatCategoryName(a) || String(a)) : String(a);
        const nameB = (typeof this.formatCategoryName === 'function') ? (this.formatCategoryName(b) || String(b)) : String(b);
        return String(nameA).localeCompare(String(nameB), this.dateLocale());
      });
    },

    getFilteredTopHogs() {
      if (!this.topHogsList || !Array.isArray(this.topHogsList)) return [];
      return this.topHogsList.filter(hog => {
        const hogMac = (hog.mac || '').toLowerCase();
        const dev = this.devices.find(d => (d.mac && d.mac.toLowerCase() === hogMac) || d.id === hog.device_id);
        
        // Category filter
        if (this.hogsCategoryFilter !== 'all') {
          const cat = (dev ? dev.category : hog.category) || 'Altro';
          if (cat !== this.hogsCategoryFilter) return false;
        }

        // Frequency band filter
        if (this.hogsBandFilter !== 'all') {
          if (!dev) return false;
          const isWiredDev = Boolean(
            dev.connection_type === 'wired' ||
            dev.connection_type === 'ethernet' ||
            dev.wired === true ||
            dev.wireless === false ||
            dev.frequency_band === 'Cablato' ||
            dev.frequency_band === 'Wired'
          );
          if (this.hogsBandFilter === 'wired') {
            if (!isWiredDev) return false;
          } else {
            if (isWiredDev) return false;
            if (this.hogsBandFilter === '6ghz') {
              const is6 = dev.wireless_band === '6GHz' || (dev.frequency_band && dev.frequency_band.includes('6'));
              if (!is6) return false;
            } else if (this.hogsBandFilter === '5ghz') {
              const is5 = dev.wireless_band === '5GHz' || (dev.frequency_band && dev.frequency_band.includes('5'));
              if (!is5) return false;
            } else if (this.hogsBandFilter === '2.4ghz') {
              const is24 = dev.wireless_band === '2.4GHz' || (dev.frequency_band && dev.frequency_band.includes('2.4'));
              if (!is24) return false;
            }
          }
        }

        // Mesh Node filter
        if (this.hogsNodeFilter !== 'all') {
          if (!dev) return false;
          if (dev.connected_eero_id !== this.hogsNodeFilter && dev.connected_eero_name !== this.hogsNodeFilter) {
            return false;
          }
        }

        return true;
      });
    },

// =========================================================================
    // MODULE 3: BUFFERBLOAT RATING HELPER
    // =========================================================================
    getBufferbloatGrade(speedtestObj) {
      const st = speedtestObj || this.latestSpeedtest || {};

      const gradeStyles = {
        'A+': {
          grade: 'A+',
          label: this.t('bufferbloat.label_a_plus'),
          class: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
        },
        'A': {
          grade: 'A',
          label: this.t('bufferbloat.label_a'),
          class: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
        },
        'B': {
          grade: 'B',
          label: this.t('bufferbloat.label_b'),
          class: 'bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30'
        },
        'C': {
          grade: 'C',
          label: this.t('bufferbloat.label_c'),
          class: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
        },
        'D': {
          grade: 'D',
          label: this.t('bufferbloat.label_d'),
          class: 'bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30'
        },
        'F': {
          grade: 'F',
          label: this.t('bufferbloat.label_f'),
          class: 'bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30'
        }
      };

      // 1. Grado diretto salvato su SQLite / backend
      const rawGrade = String(st.bufferbloat_grade || st.grade || '').toUpperCase().trim();
      if (rawGrade && gradeStyles[rawGrade]) {
        return gradeStyles[rawGrade];
      }

      // 2. Calcolo da delta o latenza sotto carico (ping_under_load)
      const ping = Number(st.ping_ms || st.ping || 0);
      const loadedLatency = Number(st.ping_under_load || st.loaded_latency_ms || st.loaded_ping || 0);
      const hasDelta = (st.bufferbloat_delta_ms !== undefined && st.bufferbloat_delta_ms !== null);
      const delta = hasDelta ? Number(st.bufferbloat_delta_ms) : (loadedLatency > 0 ? Math.max(0, loadedLatency - ping) : 0);

      if (hasDelta || loadedLatency > 0) {
        if (delta < 5.0) return gradeStyles['A+'];
        if (delta < 15.0) return gradeStyles['A'];
        if (delta < 30.0) return gradeStyles['B'];
        if (delta < 60.0) return gradeStyles['C'];
        if (delta < 200.0) return gradeStyles['D'];
        return gradeStyles['F'];
      }

      // 3. Fallback da ping idle se non sono disponibili misurazioni sotto carico
      if (ping > 0) {
        if (ping <= 12) return gradeStyles['A+'];
        if (ping <= 20) return gradeStyles['A'];
        if (ping <= 35) return gradeStyles['B'];
        if (ping <= 55) return gradeStyles['C'];
        if (ping <= 85) return gradeStyles['D'];
        return gradeStyles['F'];
      }

      return {
        grade: 'n/a',
        label: this.t('bufferbloat.not_available'),
        class: 'bg-slate-500/15 text-slate-500 dark:text-slate-400 border-slate-500/30'
      };
    },

// =========================================================================
    // MODULE 4: SYSTEM LOGGING & DIAGNOSTICS (v1.6.0)
    // =========================================================================
    logConfig: {
      enabled: true,
      level: 'INFO',
      retention_days: 7
    },
    logStats: {
      total_count: 0,
      level_counts: { DEBUG: 0, INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0 },
      oldest_timestamp: null,
      newest_timestamp: null,
      file_size_bytes: 0,
      file_size_mb: 0.0
    },
    logsList: [],
    logTotalCount: 0,
    logLoading: false,
    logLevelFilter: 'ALL',
    logSearchQuery: '',
    logAutoRefresh: false,
    logAutoRefreshTimer: null,
    customRetentionInput: 7,
    showCustomRetention: false,
    showClearLogsModal: false,
    isClearingLogs: false,
    expandedLogDetails: {},
    logTimezoneMode: localStorage.getItem('eero_log_tz') || 'local',

    async fetchLogConfig() {
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/config', { headers });
        if (res.ok) {
          const data = await res.json();
          this.logConfig = {
            enabled: Boolean(data.enabled),
            level: data.level || 'INFO',
            retention_days: Number(data.retention_days) || 7
          };
          this.logStats = data.stats || this.logStats;
          this.showCustomRetention = ![1, 7, 15, 30].includes(this.logConfig.retention_days);
          if (this.showCustomRetention) {
            this.customRetentionInput = this.logConfig.retention_days;
          }
        }
      } catch (e) {
        console.error("Failed to fetch log config:", e);
      }
    },

    async fetchSystemLogs() {
      this.logLoading = true;
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        let url = `/api/system/logs?limit=150&offset=0`;
        if (this.logLevelFilter && this.logLevelFilter !== 'ALL') {
          url += `&level=${encodeURIComponent(this.logLevelFilter)}`;
        }
        if (this.logSearchQuery && this.logSearchQuery.trim()) {
          url += `&q=${encodeURIComponent(this.logSearchQuery.trim())}`;
        }
        const res = await fetch(url, { headers });
        if (res.ok) {
          const data = await res.json();
          this.logsList = data.logs || [];
          this.logTotalCount = data.total || this.logsList.length;
        }
      } catch (e) {
        console.error("Failed to fetch system logs:", e);
      } finally {
        this.logLoading = false;
      }
    },

    async toggleLogEnabled() {
      if (!this.can('action_manage_rules')) return;
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/config', {
          method: 'POST',
          headers,
          body: JSON.stringify({ enabled: this.logConfig.enabled })
        });
        if (res.ok) {
          const data = await res.json();
          this.logConfig.enabled = data.enabled;
          this.showToast(this.t('toasts.logs_title'), this.t('logs.saved_success'), 'success');
        } else {
          this.logConfig.enabled = !this.logConfig.enabled;
          this.showToast(this.t('toasts.logs_title'), this.t('toasts.logs_toggle_error'), 'error');
        }
      } catch (e) {
        this.logConfig.enabled = !this.logConfig.enabled;
        console.error("Failed to toggle log enabled:", e);
      }
    },

    async setLogLevel(lvl) {
      if (!this.can('action_manage_rules') || !this.logConfig.enabled) return;
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/config', {
          method: 'POST',
          headers,
          body: JSON.stringify({ level: lvl })
        });
        if (res.ok) {
          const data = await res.json();
          this.logConfig.level = data.level;
          this.showToast(this.t('toasts.logs_title'), this.t('logs.saved_success'), 'success');
          await this.fetchSystemLogs();
        }
      } catch (e) {
        console.error("Failed to set log level:", e);
      }
    },

    async setLogRetention(days) {
      if (!this.can('action_manage_rules') || !this.logConfig.enabled) return;
      if (days === 'custom') {
        this.showCustomRetention = true;
        return;
      }
      this.showCustomRetention = false;
      const d = parseInt(days, 10);
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/config', {
          method: 'POST',
          headers,
          body: JSON.stringify({ retention_days: d })
        });
        if (res.ok) {
          const data = await res.json();
          this.logConfig.retention_days = data.retention_days;
          this.showToast(this.t('toasts.logs_title'), this.t('logs.saved_success'), 'success');
        }
      } catch (e) {
        console.error("Failed to set log retention:", e);
      }
    },

    async applyCustomRetention() {
      if (!this.can('action_manage_rules') || !this.logConfig.enabled) return;
      const d = Math.max(0, parseInt(this.customRetentionInput, 10) || 0);
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/config', {
          method: 'POST',
          headers,
          body: JSON.stringify({ retention_days: d })
        });
        if (res.ok) {
          const data = await res.json();
          this.logConfig.retention_days = data.retention_days;
          this.showToast(this.t('toasts.logs_title'), this.t('logs.saved_success'), 'success');
        }
      } catch (e) {
        console.error("Failed to apply custom retention:", e);
      }
    },

    openClearLogsModal() {
      this.showClearLogsModal = true;
    },

    closeClearLogsModal() {
      this.showClearLogsModal = false;
    },

    async confirmClearLogs() {
      if (!this.can('action_manage_rules')) return;
      this.isClearingLogs = true;
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/logs/clear', {
          method: 'POST',
          headers
        });
        if (res.ok) {
          const data = await res.json();
          this.showClearLogsModal = false;
          this.showToast(this.t('toasts.logs_title'), this.t('toasts.logs_cleared', { count: data.deleted_records || 0 }), 'success');
          await this.fetchLogConfig();
          await this.fetchSystemLogs();
        } else {
          this.showToast(this.t('toasts.logs_title'), this.t('toasts.logs_clear_error'), 'error');
        }
      } catch (e) {
        console.error("Failed to clear system logs:", e);
      } finally {
        this.isClearingLogs = false;
      }
    },

    downloadSystemLogs(format = 'log') {
      let url = `/api/system/logs/download?format=${format}`;
      if (this.localAuthToken) {
        url += `&token=${encodeURIComponent(this.localAuthToken)}`;
      }
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.download = '';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    },

    toggleLogAutoRefresh() {
      if (this.logAutoRefresh) {
        if (!this.logAutoRefreshTimer) {
          this.logAutoRefreshTimer = setInterval(() => {
            if (this.currentTab === 'settings-controls' || this.currentTab === 'automations' || this.currentTab === 'controls') {
              this.fetchSystemLogs();
              this.fetchLogConfig();
            }
          }, 10000);
        }
      } else {
        if (this.logAutoRefreshTimer) {
          clearInterval(this.logAutoRefreshTimer);
          this.logAutoRefreshTimer = null;
        }
      }
    },

    toggleLogDetail(id) {
      this.expandedLogDetails[id] = !this.expandedLogDetails[id];
    },

    toggleLogTimezone() {
      this.logTimezoneMode = this.logTimezoneMode === 'local' ? 'utc' : 'local';
      try {
        localStorage.setItem('eero_log_tz', this.logTimezoneMode);
      } catch (e) {}
    },

    formatLogTimestamp(ts) {
      if (!ts) return '';
      if (this.logTimezoneMode === 'utc') {
        return ts.replace('T', ' ').replace('Z', '') + ' UTC';
      }
      try {
        const utcIso = ts.includes('T') ? (ts.endsWith('Z') ? ts : ts + 'Z') : ts.replace(' ', 'T') + 'Z';
        const d = new Date(utcIso);
        if (isNaN(d.getTime())) return ts;
        const localeCode = this.dateLocale();
        return d.toLocaleString(localeCode, {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        });
      } catch (e) {
        return ts;
      }
    }
  };
}

if (typeof window !== 'undefined') {
  window.createDiagnosticsModule = createDiagnosticsModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createDiagnosticsModule };
}
