/**
 * eero Custom Dashboard & Management Suite - Frontend Application Logic
 * Core Orchestrator (Modular Alpine.js Architecture - v1.8.0)
 * Powered by Alpine.js & Chart.js
 */

// Tag every same-origin API call with the dashboard language so the server
// answers (errors, confirmations) in the language the user is reading.
(() => {
  if (typeof window === 'undefined' || !window.fetch) return;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const sameOriginApi = url.startsWith('/api/') || url.startsWith(`${window.location.origin}/api/`);
    if (!sameOriginApi || typeof input !== 'string') return nativeFetch(input, init);
    const headers = new Headers(init.headers || {});
    if (!headers.has('X-Dashboard-Lang')) headers.set('X-Dashboard-Lang', document.documentElement.lang || 'en');
    return nativeFetch(input, { ...init, headers }).then((res) => {
      // Startup or database repair in progress (Issue #117): let the app show its maintenance overlay.
      if (res.status === 503 && res.headers.has('X-Dashboard-Maintenance')) {
        window.dispatchEvent(new CustomEvent('eero-maintenance'));
      }
      return res;
    });
  };
})();

document.addEventListener('alpine:init', () => {
  Alpine.data('eeroApp', () => {
    const merge = (typeof EeroUtils !== 'undefined' && EeroUtils.mergeModules)
      || function(target, ...sources) {
        for (const source of sources) {
          if (!source) continue;
          Object.defineProperties(target, Object.getOwnPropertyDescriptors(source));
        }
        return target;
      };

    const core = {
appVersion: (window.APP_CONFIG && window.APP_CONFIG.version && !window.APP_CONFIG.version.startsWith('{')) ? window.APP_CONFIG.version : '1.7.0',
    buildNumber: (window.APP_CONFIG && window.APP_CONFIG.buildNumber && !window.APP_CONFIG.buildNumber.startsWith('{')) ? window.APP_CONFIG.buildNumber : '1',
    fullVersion: (window.APP_CONFIG && window.APP_CONFIG.fullVersion && !window.APP_CONFIG.fullVersion.startsWith('{')) ? window.APP_CONFIG.fullVersion : '1.7.0 build 1',

    // Windows 11 Dual Theme Engine State
    currentTheme: localStorage.getItem('eero_theme') || 'system',

    // i18n Multi-Language State
    supportedLanguages: (window.APP_CONFIG && Array.isArray(window.APP_CONFIG.supportedLanguages) && window.APP_CONFIG.supportedLanguages.length) ? window.APP_CONFIG.supportedLanguages : ['en', 'it', 'fr', 'es', 'de', 'nl', 'pt', 'pl', 'el'],
    currentLanguage: (() => {
      // A choice saved in this browser wins; otherwise the server default
      // (saved system language, else DASHBOARD_LANG, else English).
      const supported = (window.APP_CONFIG && Array.isArray(window.APP_CONFIG.supportedLanguages) && window.APP_CONFIG.supportedLanguages.length) ? window.APP_CONFIG.supportedLanguages : ['en', 'it', 'fr', 'es', 'de', 'nl', 'pt', 'pl', 'el'];
      const saved = localStorage.getItem('eero_lang');
      if (supported.includes(saved)) return saved;
      const serverDefault = (typeof window !== 'undefined' && window.APP_CONFIG && window.APP_CONFIG.defaultLanguage) || '';
      return supported.includes(serverDefault) ? serverDefault : 'en';
    })(),
    translations: {},
    fallbackTranslations: {},
    translationsLoaded: false,

    // Navigation & Sidebar State
    routes: {
      overview: '/dashboard',
      devices: '/devices',
      speedtest: '/speedtest',
      guests: '/guests',
      'quality-analytics': '/quality-analytics',
      'settings-controls': '/settings/controls',
      'settings-users': '/settings/users',
      'settings-backup': '/settings/backup',
      'settings-export': '/settings/export',
      'settings-updates': '/settings/updates',
      analytics: '/quality-analytics',
      automations: '/settings/controls',
      controls: '/settings/controls',
      export: '/settings/export',
      manual: '/manual',
      news: '/news'
    },
    currentTab: 'overview',
    settingsExpanded: false,
    isSettingsTab() {
      return ['settings-controls', 'settings-users', 'settings-backup', 'settings-export', 'settings-updates'].includes(this.currentTab);
    },
    toggleSettingsMenu() {
      if (this.sidebarCollapsed) {
        this.sidebarCollapsed = false;
        this.settingsExpanded = true;
        if (!this.isSettingsTab()) {
          this.setTab('settings-controls');
        }
        return;
      }
      this.settingsExpanded = !this.settingsExpanded;
      if (this.settingsExpanded && !this.isSettingsTab()) {
        this.setTab('settings-controls');
      }
    },
    sidebarCollapsed: (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 1199px)').matches) || localStorage.getItem('eero_sidebar_collapsed') === 'true',
    showMobileMenu: false,
    showMobileDeviceFilters: false,
    toggleMobileMenu() {
      this.showMobileMenu = !this.showMobileMenu;
    },
    closeMobileMenu() {
      this.showMobileMenu = false;
    },
    toggleSidebar() {
      if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {
        this.toggleMobileMenu();
        return;
      }
      this.sidebarCollapsed = !this.sidebarCollapsed;
      localStorage.setItem('eero_sidebar_collapsed', this.sidebarCollapsed);
    },
    // Sidebar hover text: a one-line description, prefixed by the label when the menu is collapsed to icons.
    navTitle(label, hintKey) {
      const hint = this.t('nav_hints.' + hintKey);
      return this.sidebarCollapsed ? `${label} — ${hint}` : hint;
    },
    themeCycleTitle() {
      const next = { light: 'dark', dark: 'system', system: 'light' }[this.currentTheme] || 'light';
      return this.t('nav_hints.theme_cycle', {
        current: this.t('header.theme_' + this.currentTheme),
        next: this.t('header.theme_' + next),
      });
    },

// =========================================================================
    // INITIALIZATION & I18N
    // =========================================================================
    async init() {
      console.log("Initializing eero Custom Dashboard application...");
      this.currentTab = this.tabFromPath();
      // Keep the Devices table Name column fitted when the panel resizes (sidebar, window).
      this.$nextTick(() => {
        const scroll = document.querySelector('.device-table-scroll');
        if (scroll && typeof ResizeObserver !== 'undefined') {
          new ResizeObserver(() => this.fitDeviceNameColumn()).observe(scroll);
        }
      });
      if (typeof window !== 'undefined' && window.location && window.location.pathname === '/') {
        window.history.replaceState({}, '', this.routes.overview);
      }
      if (this.currentTab === 'devices') {
        this.loadDeviceFiltersFromUrl();
      }
      this.initTheme();
      if (typeof window !== 'undefined' && window.matchMedia) {
        const mql = window.matchMedia('(max-width: 1199px)');
        if (mql && mql.addEventListener) {
          mql.addEventListener('change', ({ matches }) => {
            this.sidebarCollapsed = matches || localStorage.getItem('eero_sidebar_collapsed') === 'true';
          });
        }
      }

      // Versione, lingua e stato auth sono indipendenti: caricati in parallelo per ridurre l'attesa al refresh
      if (typeof window !== 'undefined') {
        window.addEventListener('eero-maintenance', () => this.enterMaintenance());
      }
      const syncVersion = async () => {
        try {
          const healthRes = await fetch('/api/health', { cache: 'no-store' });
          const hData = await healthRes.json().catch(() => ({}));
          if (hData.maintenance) this.enterMaintenance(hData.maintenance);
          if (healthRes.ok) {
            if (hData.full_version) this.fullVersion = hData.full_version;
            if (hData.build_number) this.buildNumber = String(hData.build_number);
            if (hData.version) this.appVersion = hData.version;
          }
        } catch (e) {}
      };
      await Promise.all([
        syncVersion(),
        this.setLanguage(this.currentLanguage, { syncServer: false }),
        this.checkAuthStatus()
      ]);
      // The dashboard reloads once maintenance ends; skip the login prompt and data loads meanwhile.
      if (this.maintenance) return;
      await this.checkLocalAuthSession();
      await this.loadSessionTimeoutSetting();
      this.initInactivityWatchdog();

      // Se l'utente non è loggato, limita la visualizzazione solo a ospiti (QR) o release notes (news)
      if (!this.currentUser && this.currentTab !== 'guests' && this.currentTab !== 'news') {
        this.currentTab = 'guests';
        if (typeof window !== 'undefined' && window.history) {
          window.history.replaceState({}, '', this.routes.guests);
        }
      }

      // Prompt Gatekeeping Rigoroso: se non loggato, propone immediatamente il login (o setup se primo avvio)
      if (!this.currentUser) {
        if (this.adminSetupRequired) {
          this.openAdminSetupModal();
        } else {
          this.openLocalLoginModal();
        }
      }

      await this.loadManualSections();

      if (this.isAuthenticated) {
        await this.refreshAllData();
        this.startPolling();
        this.checkForUpdates(false);
        this.fetchEeroNews(false);
      } else {
        this.deviceFiltersReady = true;
      }

      // Reattività cambio tab con rendering forzato e resize automatico
      this.$watch('currentTab', (tab) => {
        if (tab === 'speedtest') {
          this.loadSpeedtestData();
        } else if (tab === 'quality-analytics' || tab === 'analytics') {
          if (this.$nextTick) {
            this.$nextTick(() => {
              this.loadSignalOverview();
              this.loadAnalyticsData();
            });
          } else {
            this.loadSignalOverview();
            this.loadAnalyticsData();
          }
        } else if (tab === 'guests') {
          this.fetchGuestNetwork();
        } else if (tab === 'settings-controls' || tab === 'automations' || tab === 'controls') {
          this.fetchNightMode();
          this.fetchNotificationSettings();
          this.fetchDigestSettings();
          this.fetchDnsSettings();
          this.fetchAdGuardSettings();
          this.fetchMqttSettings();
          this.fetchAlerts();
          this.fetchSchedules();
          this.fetchGuestNetwork();
          this.fetchIpv6FirewallRules();
          this.fetchGuardianVpn();
          this.fetchLogConfig();
          this.fetchSystemLogs();
        } else if (tab === 'settings-users') {
          this.loadPermissionsCatalog();
          this.loadLocalUsers();
        } else if (tab === 'settings-backup') {
          this.fetchDbStats();
        } else if (tab === 'settings-updates') {
          this.checkForUpdates(false);
          this.fetchRuntimeInfo();
        } else if (tab === 'news') {
          this.fetchEeroNews();
        }
      });

      if (this.$watch) {
        for (const filter of ['deviceSearchQuery', 'selectedBandFilter', 'selectedNodeFilter', 'selectedCategoryFilter', 'selectedProfileFilter', 'selectedIpTypeFilter', 'showConnectedOnly']) {
          this.$watch(filter, () => this.syncDeviceFiltersToUrl());
        }
        this.$watch('logLevelFilter', () => this.fetchSystemLogs());
        this.$watch('logSearchQuery', () => this.fetchSystemLogs());
        this.$watch('logAutoRefresh', () => this.toggleLogAutoRefresh());
      }

      if (typeof window !== 'undefined' && window.addEventListener) {
        window.addEventListener('popstate', () => {
          const tab = this.tabFromPath();
          if (!this.currentUser && tab !== 'guests' && tab !== 'news') {
            this.setTab('guests', false);
            return;
          }
          if (tab === 'devices') this.loadDeviceFiltersFromUrl();
          this.setTab(tab, false);
        });
      }
      await this.setTab(this.currentTab, false);
    },

    async fetchLocale(lang) {
      const cfg = (typeof window !== 'undefined' && window.APP_CONFIG) || {};
      const ver = (cfg.version && !cfg.version.startsWith('{')) ? `${cfg.version}.b${cfg.buildNumber || ''}` : this.appVersion;
      try {
        const res = await fetch(`/static/locales/${lang}.json?v=${encodeURIComponent(ver)}`);
        if (res.ok) return await res.json();
      } catch (e) {
        console.warn("Could not load translations for", lang, e);
      }
      return null;
    },

    // syncServer: an explicit user switch also updates the server's alert
    // language; the page-load call must not, or every browser that opens the
    // dashboard would overwrite it.
    async setLanguage(lang, { syncServer = true } = {}) {
      if (this.currentUser && !this.can('action_change_language') && syncServer) {
        return;
      }
      this.currentLanguage = this.supportedLanguages.includes(lang) ? lang : 'en';
      localStorage.setItem('eero_lang', this.currentLanguage);
      document.documentElement.lang = this.currentLanguage;
      // English is the reference locale: keep it loaded so any key missing from
      // the active locale still renders in English instead of blank.
      if (!this.fallbackTranslations || !Object.keys(this.fallbackTranslations).length) {
        this.fallbackTranslations = (await this.fetchLocale('en')) || {};
      }
      const active = this.currentLanguage === 'en' ? this.fallbackTranslations : await this.fetchLocale(this.currentLanguage);
      this.translations = active || this.fallbackTranslations;
      this.translationsLoaded = Object.keys(this.translations).length > 0;
      document.body.classList.remove('i18n-pending');
      if (this.translationsLoaded) document.title = this.t('app_title');
      if (syncServer && this.can('action_change_language')) {
        try {
          await fetch('/api/system/language', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: this.currentLanguage })
          });
        } catch (e) {
          console.warn("Could not sync language with backend:", e);
        }
      }
      await this.loadManualSections();
      if (this.showChangelogModal) {
        await this.openChangelogModal();
      }
      if (this.currentTab === 'analytics' || this.currentTab === 'quality-analytics') {
        this.renderAnalyticsCharts();
      }
      // Server-side localized payloads: Demo Mode sample names and the update-check
      // release notes come back in the request language, so refetch them now
      // instead of waiting for the next polling cycle.
      if (this.isDemoMode && typeof this.manualRefresh === 'function') {
        this.manualRefresh();
      }
      if (this.updateInfo && this.updateInfo.checked_at) {
        this.checkForUpdates(false);
      }
    },

// =========================================================================
    // DUAL THEME ENGINE (WINDOWS 11 FLUENT DESIGN)
    // =========================================================================
    initTheme() {
      this.applyTheme(this.currentTheme);
      try {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', () => {
          if (this.currentTheme === 'system') {
            this.applyTheme('system');
          }
        });
      } catch (e) {
        console.warn('prefers-color-scheme listener not supported:', e);
      }
    },

    setTheme(mode) {
      this.currentTheme = mode;
      localStorage.setItem('eero_theme', mode);
      this.applyTheme(mode);
      const title = this.t('js.set_theme.theme_updated');
      const modeLabel = mode === 'light' ? (this.t('header.theme_light'))
        : mode === 'dark' ? (this.t('header.theme_dark'))
        : (this.t('header.theme_system'));
      this.showToast(title, `${title}: ${modeLabel}`, "info");
    },

    applyTheme(mode) {
      const prefersDark = Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
      const isDark = mode === 'dark' || (mode === 'system' && prefersDark);
      if (isDark) {
        document.documentElement.classList.add('dark');
        document.documentElement.style.colorScheme = 'dark';
      } else {
        document.documentElement.classList.remove('dark');
        document.documentElement.style.colorScheme = 'light';
      }
      this.updateActiveQrCode();
      setTimeout(() => {
        this.updateAllChartsTheme();
      }, 50);
    },

    updateActiveQrCode() {
      const isDark = document.documentElement.classList.contains('dark');
      if (isDark && this.guestQrCodeUrlDark) {
        this.guestQrCodeUrl = this.guestQrCodeUrlDark;
      } else if (!isDark && this.guestQrCodeUrlLight) {
        this.guestQrCodeUrl = this.guestQrCodeUrlLight;
      } else if (this.guestQrCodeUrlLight || this.guestQrCodeUrlDark) {
        this.guestQrCodeUrl = isDark ? (this.guestQrCodeUrlDark || this.guestQrCodeUrlLight) : (this.guestQrCodeUrlLight || this.guestQrCodeUrlDark);
      }
    },

    getChartThemeColors() {
      const isDark = document.documentElement.classList.contains('dark');
      return {
        isDark,
        fontFamily: "'Segoe UI Variable', 'Segoe UI', 'Inter', -apple-system, sans-serif",
        gridColor: isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)',
        ticksColor: isDark ? '#9e9e9e' : '#5c5c5c',
        titleColor: isDark ? '#d1d1d1' : '#1c1c1c',
        tooltipBg: isDark ? 'rgba(32, 32, 32, 0.96)' : 'rgba(255, 255, 255, 0.96)',
        tooltipTitle: isDark ? '#60cdff' : '#0067c0',
        tooltipBody: isDark ? '#ffffff' : '#1c1c1c',
        tooltipBorder: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.10)'
      };
    },

    updateAllChartsTheme() {
      const colors = this.getChartThemeColors();
      const charts = [
        this.wanChartInstance,
        this.hogsChartInstance,
        this.speedtestChartInstance,
        this.signalChartInstance,
        ...(this.analyticsChartInstances ? Object.values(this.analyticsChartInstances) : [])
      ];

      charts.forEach(chart => {
        if (!chart || !chart.ctx) return;
        try {
          if (chart.options?.scales) {
            Object.values(chart.options.scales).forEach(scale => {
              if (scale.grid) scale.grid.color = colors.gridColor;
              if (scale.ticks) {
                scale.ticks.color = colors.ticksColor;
                if (!scale.ticks.font) scale.ticks.font = {};
                scale.ticks.font.family = colors.fontFamily;
              }
              if (scale.title) {
                scale.title.color = colors.titleColor;
                if (!scale.title.font) scale.title.font = {};
                scale.title.font.family = colors.fontFamily;
              }
            });
          }
          if (chart.options?.plugins?.tooltip && !chart.options.plugins.tooltip._customDark) {
            chart.options.plugins.tooltip.backgroundColor = colors.tooltipBg;
            chart.options.plugins.tooltip.titleColor = colors.tooltipTitle;
            chart.options.plugins.tooltip.bodyColor = colors.tooltipBody;
            chart.options.plugins.tooltip.borderColor = colors.tooltipBorder;
          }
          if (chart.options?.plugins?.legend?.labels) {
            chart.options.plugins.legend.labels.color = colors.ticksColor;
            chart.options.plugins.legend.labels.font = { family: colors.fontFamily, size: 12 };
          }
          chart.update('none');
        } catch (err) {
          console.warn('Error updating chart theme:', err);
        }
      });
    },

lookupTranslation(dict, keys) {
      let val = dict;
      for (const k of keys) {
        if (val && typeof val === 'object' && k in val) {
          val = val[k];
        } else {
          return null;
        }
      }
      return typeof val === 'string' ? val : null;
    },

    // Picks the viewer-language variant of a server payload field. Prefers a
    // `<field>_i18n` map ({en, it, ...}), then legacy `<field>_<lang>` keys,
    // then English, then the bare field.
    localized(obj, field) {
      if (!obj) return '';
      const lang = this.currentLanguage;
      const map = obj[`${field}_i18n`];
      if (map && typeof map === 'object') {
        if (map[lang]) return map[lang];
        if (map.en) return map.en;
      }
      return obj[`${field}_${lang}`] ?? obj[`${field}_en`] ?? obj[field] ?? '';
    },

    languageFlags: {
      en: '🇬🇧',
      it: '🇮🇹',
      fr: '🇫🇷',
      es: '🇪🇸',
      de: '🇩🇪',
      nl: '🇳🇱',
      pt: '🇵🇹',
      pl: '🇵🇱',
      el: '🇬🇷'
    },
    // Default BCP 47 region per dashboard language, used by dateLocale().
    dateLocales: {
      en: 'en-US',
      it: 'it-IT',
      fr: 'fr-FR',
      es: 'es-ES',
      de: 'de-DE',
      nl: 'nl-NL',
      pt: 'pt-PT',
      pl: 'pl-PL',
      el: 'el-GR'
    },
    languageFlag(lang) {
      return this.languageFlags[lang] || (lang || '').toUpperCase();
    },

    // RBAC role label: auth_local.role_<role>, falling back to the raw role code.,

cycleLanguage() {
      if (this.currentUser && !this.can('action_change_language')) {
        this.showToast(this.t('toasts.error'), this.t('auth_local.no_access'), 'error');
        return;
      }
      const list = this.supportedLanguages;
      const next = list[(list.indexOf(this.currentLanguage) + 1) % list.length];
      return this.setLanguage(next);
    },

    t(path, params = {}) {
      if (!path) return '';
      const keys = path.split('.');
      const val = this.lookupTranslation(this.translations, keys) ?? this.lookupTranslation(this.fallbackTranslations, keys);
      if (val === null) {
        return '';
      }
      let res = val;
      for (const [k, v] of Object.entries(params)) {
        res = res.replaceAll(`{${k}}`, v);
      }
      return res;
    },

tabFromPath() {
      const path = (typeof window !== 'undefined' && window.location ? window.location.pathname : '').replace(/\/$/, '') || '/dashboard';
      if (path === '/eero-news') return 'news';
      if (path === '/settings') return 'settings-controls';
      if (path === '/settings/export' || path === '/export') return 'settings-export';
      if (path === '/automations' || path === '/controls') return 'settings-controls';
      if (path === '/analytics') return 'quality-analytics';
      return Object.keys(this.routes).find(tab => this.routes[tab] === path) || 'overview';
    },

async setTab(tab, updateUrl = true) {
      // Se non autenticato, sono permesse solo la visualizzazione Wi-Fi ospiti (QR code) e note di rilascio
      if (!this.currentUser && tab !== 'guests' && tab !== 'news') {
        this.showToast(
          this.t('js.set_tab.login_required'),
          this.t('js.set_tab.please_sign_in_to'),
          'info'
        );
        this.openLocalLoginModal();
        if (this.currentTab !== 'guests' && this.currentTab !== 'news') {
          tab = 'guests';
        } else {
          return;
        }
      }

      // Protezione accessi per tab amministrative riservate
      if (tab === 'settings-users' && !this.can('action_manage_users')) {
        this.showToast(
          this.t('js.set_tab.access_restricted'),
          this.t('js.set_tab.please_sign_in_as'),
          'warning'
        );
        this.openLocalLoginModal();
        return;
      }
      if (tab === 'settings-backup' && !this.can('action_system_backup')) {
        this.showToast(
          this.t('js.set_tab.access_restricted'),
          this.t('js.set_tab.please_sign_in_as_2'),
          'warning'
        );
        this.openLocalLoginModal();
        return;
      }
      if (!this.routes[tab]) tab = 'overview';
      this.currentTab = tab;
      if (this.isSettingsTab()) {
        this.settingsExpanded = true;
      }
      this.showMobileMenu = false;
      if (typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {
        this.sidebarCollapsed = true;
      }
      const url = tab === 'devices' ? this.deviceFiltersUrl() : this.routes[tab];
      if (updateUrl && typeof window !== 'undefined' && window.history && `${window.location.pathname}${window.location.search}` !== url) {
        window.history.pushState({}, '', url);
      }
      if (tab === 'speedtest') {
        setTimeout(async () => {
          await this.loadSpeedtestData();
        }, 50);
      } else if (tab === 'quality-analytics' || tab === 'analytics') {
        setTimeout(async () => {
          await this.loadSignalOverview();
          await this.loadAnalyticsData(true);
        }, 50);
      } else if (tab === 'guests') {
        await this.fetchGuestNetwork();
      } else if (tab === 'devices') {
        await this.fetchDevices();
      } else if (tab === 'settings-controls' || tab === 'automations' || tab === 'controls') {
        await this.fetchNightMode();
        await this.fetchNotificationSettings();
        await this.fetchDigestSettings();
        await this.fetchDnsSettings();
        await this.fetchAdGuardSettings();
        await this.fetchMqttSettings();
        await this.fetchAlerts();
        await this.fetchSchedules();
        await this.fetchGuestNetwork();
        await this.fetchIpv6FirewallRules();
        await this.fetchGuardianVpn();
      } else if (tab === 'settings-users') {
        await this.loadPermissionsCatalog();
        await this.loadLocalUsers();
      } else if (tab === 'settings-backup') {
        await this.fetchDbStats();
      } else if (tab === 'settings-updates') {
        await Promise.all([this.checkForUpdates(false), this.fetchRuntimeInfo()]);
      } else if (tab === 'news') {
        await this.fetchEeroNews();
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
            } else if (this.currentTab === 'quality-analytics' || this.currentTab === 'analytics') {
              await this.loadSignalOverview();
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
        } else if (this.currentTab === 'quality-analytics' || this.currentTab === 'analytics') {
          await this.loadSignalOverview();
          await this.loadAnalyticsData(true);
        }
        const title = this.t('js.manual_refresh.data_refreshed');
        const msg = this.t('js.manual_refresh.dashboard_synchronized_in_real');
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.t('js.manual_refresh.refresh_error');
        this.showToast(title, err.message, "error");
      } finally {
        setTimeout(() => { this.isRefreshing = false; }, 400);
      }
    },

    async refreshAllData() {
      await Promise.all([
        this.fetchOverview(),
        this.fetchAvailableNetworks(),
        this.fetchTopHogs(this.topHogsPeriod),
        this.fetchRealtimeMetrics(),
        this.fetchDevices(),
        this.fetchProfiles(),
        this.fetchGuestNetwork(),
        this.fetchFocusMode(),
        this.fetchNightMode(),
        this.fetchNotificationSettings(),
        this.fetchDigestSettings(),
        this.fetchAdGuardSettings(),
        this.fetchMqttSettings(),
        this.fetchAlerts(),
        this.fetchGuardianVpn(),
        this.loadSpeedtestData(),
      ]);
      await this.loadSignalOverview();
      if (this.currentTab === 'quality-analytics' || this.currentTab === 'analytics') {
        this.loadAnalyticsData();
      }
      if (this.currentTab === 'devices') {
        if (this.$nextTick) {
          await this.$nextTick();
        }
        this.loadDeviceFiltersFromUrl();
      }
      this.deviceFiltersReady = true;
    },

    async fetchOverview() {
      try {
        const res = await fetch('/api/network/overview');
        const json = await res.json();
        if (json.status === 'success') {
          this.network = json.data.network || {};
          this.fetchPublicIp();
          this.eeros = json.data.eeros || [];
          this.healthScore = json.data.health_score || 100;
          this.healthDetails = json.data.health_details || null;
          this.lastPollTime = json.data.last_poll_time;
          if (json.data.available_networks && json.data.available_networks.length > 0) {
            this.availableNetworks = json.data.available_networks;
          }
          if (json.data.active_network_id) {
            this.activeNetworkId = json.data.active_network_id;
          }
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

    // Mark as seen (Issue #60): hides the NEW badge, or restores it when seen = false
    async setDevicesSeen(macs, seen = true) {
      const targets = (macs || []).map(m => String(m || '').toLowerCase()).filter(Boolean);
      if (!targets.length) return;
      try {
        const res = await fetch('/api/devices/seen', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ macs: targets, seen })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `HTTP ${res.status}`);
        }
        const macSet = new Set(targets);
        const apply = (d) => {
          if (!d || !macSet.has(String(d.mac || d.mac_address || '').toLowerCase())) return;
          if (seen && d.is_new) Object.assign(d, { is_new: false, is_new_24h: false, new_dismissed: true });
          if (!seen && d.new_dismissed) Object.assign(d, { is_new: true, new_dismissed: false });
        };
        this.devices.forEach(apply);
        apply(this.selectedDevice);
        if (seen) {
          this.showToast(this.t('devices.marked_seen_title'), this.t('devices.marked_seen_msg', { count: targets.length }), 'success');
        } else {
          this.showToast(this.t('devices.marked_new_title'), this.t('devices.marked_new_msg'), 'info');
        }
      } catch (err) {
        this.showToast(this.t('devices.mark_seen_error'), err.message, 'error');
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
    // MAINTENANCE OVERLAY (Issue #117)
    // =========================================================================
    enterMaintenance(info = null) {
      if (info) this.maintenance = info;
      else if (!this.maintenance) this.maintenance = { stage: 'starting', since: null };
      if (this.maintenancePollTimer) return;
      const tick = async () => {
        try {
          const res = await fetch('/api/health', { cache: 'no-store' });
          const data = await res.json();
          if (data.maintenance) {
            this.maintenance = data.maintenance;
          } else if (data.status === 'healthy') {
            clearInterval(this.maintenancePollTimer);
            window.location.reload();
            return;
          }
        } catch (e) {
          // Server restarting: keep the overlay and try again on the next tick.
        }
        const since = this.maintenance && this.maintenance.since ? Date.parse(this.maintenance.since) : NaN;
        this.maintenanceElapsed = Number.isNaN(since) ? 0 : Math.max(0, Math.round((Date.now() - since) / 1000));
      };
      this.maintenancePollTimer = setInterval(tick, 2000);
      tick();
    },

    pollForHealthAndReload() {
      let attempts = 0;
      const maxAttempts = 40;
      const interval = setInterval(async () => {
        attempts++;
        try {
          const res = await fetch('/api/health', { cache: 'no-store' });
          if (res.ok) {
            const data = await res.json();
            if (data.status === 'healthy') {
              clearInterval(interval);
              this.updateProgressMsg = this.t('js.poll_for_health_and_reload.update_completed_reloading_dashboard');
              setTimeout(() => {
                window.location.reload(true);
              }, 1200);
            }
          }
        } catch (e) {
          // Attesa normale del riavvio container
        }
        if (attempts >= maxAttempts) {
          clearInterval(interval);
          window.location.reload(true);
        }
      }, 2000);
    },

    copyCliCommand() {
      if (this.updateInfo.cli_command) {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(this.updateInfo.cli_command);
        }
        this.copiedCliCommand = true;
        setTimeout(() => { this.copiedCliCommand = false; }, 3000);
      }
    },

    copyToClipboard(text, successMsg = '') {
      if (!text) return;
      const title = this.t('js.copy_to_clipboard.clipboard');
      const msg = successMsg || (this.t('js.copy_to_clipboard.copied_to_clipboard'));
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          this.showToast(title, msg, 'success');
        }).catch(() => {
          this._fallbackCopyText(text, title, msg);
        });
      } else {
        this._fallbackCopyText(text, title, msg);
      }
    },

    _fallbackCopyText(text, title, msg) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        this.showToast(title, msg, 'success');
      } catch (e) {
        this.showToast(title, this.t('js.fallback_copy_text.copy_failed'), 'error');
      }
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
    };

    // Compose Core with Domain Modules and Utilities (Phase 3 Clean Architecture)
    const authMod = typeof createAuthModule === 'function' ? createAuthModule() : (typeof require !== 'undefined' ? require('./modules/auth').createAuthModule() : {});
    const devicesMod = typeof createDevicesModule === 'function' ? createDevicesModule() : (typeof require !== 'undefined' ? require('./modules/devices').createDevicesModule() : {});
    const meshMod = typeof createMeshModule === 'function' ? createMeshModule() : (typeof require !== 'undefined' ? require('./modules/mesh').createMeshModule() : {});
    const dnsMod = typeof createDnsModule === 'function' ? createDnsModule() : (typeof require !== 'undefined' ? require('./modules/dns').createDnsModule() : {});
    const automationsMod = typeof createAutomationsModule === 'function' ? createAutomationsModule() : (typeof require !== 'undefined' ? require('./modules/automations').createAutomationsModule() : {});
    const diagnosticsMod = typeof createDiagnosticsModule === 'function' ? createDiagnosticsModule() : (typeof require !== 'undefined' ? require('./modules/diagnostics').createDiagnosticsModule() : {});
    const utilsMod = typeof EeroUtils !== 'undefined' ? EeroUtils : (typeof require !== 'undefined' ? require('./utils') : {});

    return merge(
      core,
      utilsMod,
      authMod,
      devicesMod,
      meshMod,
      dnsMod,
      automationsMod,
      diagnosticsMod
    );
  });
});
