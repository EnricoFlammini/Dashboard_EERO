/**
 * eero Custom Dashboard & Management Suite - Frontend Application Logic
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
    return nativeFetch(input, { ...init, headers });
  };
})();

document.addEventListener('alpine:init', () => {
  Alpine.data('eeroApp', () => ({
    // App Version & Build Metadata
    appVersion: (window.APP_CONFIG && window.APP_CONFIG.version && !window.APP_CONFIG.version.startsWith('{')) ? window.APP_CONFIG.version : '1.6.2',
    buildNumber: (window.APP_CONFIG && window.APP_CONFIG.buildNumber && !window.APP_CONFIG.buildNumber.startsWith('{')) ? window.APP_CONFIG.buildNumber : '1',
    fullVersion: (window.APP_CONFIG && window.APP_CONFIG.fullVersion && !window.APP_CONFIG.fullVersion.startsWith('{')) ? window.APP_CONFIG.fullVersion : '1.6.2 build 1',

    // Windows 11 Dual Theme Engine State
    currentTheme: localStorage.getItem('eero_theme') || 'system',

    // i18n Multi-Language State
    supportedLanguages: (window.APP_CONFIG && Array.isArray(window.APP_CONFIG.supportedLanguages) && window.APP_CONFIG.supportedLanguages.length) ? window.APP_CONFIG.supportedLanguages : ['en', 'it'],
    currentLanguage: (() => {
      // A choice saved in this browser wins; otherwise the server default
      // (saved system language, else DASHBOARD_LANG, else English).
      const supported = (window.APP_CONFIG && Array.isArray(window.APP_CONFIG.supportedLanguages) && window.APP_CONFIG.supportedLanguages.length) ? window.APP_CONFIG.supportedLanguages : ['en', 'it'];
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
    getDeviceIconPath(cat) {
      const c = (cat || '').toLowerCase();
      if (c.includes('game') || c.includes('gaming') || c.includes('console') || c.includes('playstation') || c.includes('xbox') || c.includes('nintendo') || c.includes('switch')) {
        return 'M6 11h4m-2-2v4m7-2h.01m3 0h.01M4 9a5 5 0 0110-3h2a5 5 0 015 5v4a4 4 0 01-4 4l-2-2h-6l-2 2a4 4 0 01-4-4V9z';
      }
      if (c.includes('server') || c.includes('rete') || c.includes('network') || c.includes('nas') || c.includes('storage') || c.includes('switch') || c.includes('router')) {
        return 'M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01';
      }
      if (c.includes('audio') || c.includes('speaker') || c.includes('sound') || c.includes('music') || c.includes('echo') || c.includes('homepod') || c.includes('sonos')) {
        return 'M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z';
      }
      if (c.includes('phone') || c.includes('mobile') || c.includes('smartphone') || c.includes('iphone') || c.includes('android')) {
        return 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z';
      }
      if (c.includes('tablet') || c.includes('ipad')) {
        return 'M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z';
      }
      if (c.includes('tv') || c.includes('media') || c.includes('entertainment') || c.includes('intrattenimento') || c.includes('streaming') || c.includes('chromecast') || c.includes('firetv') || c.includes('apple tv')) {
        return 'M7 4h10a2 2 0 012 2v10a2 2 0 01-2 2H7a2 2 0 01-2-2V6a2 2 0 012-2zm-3 16h16';
      }
      if (c.includes('iot') || c.includes('home') || c.includes('smart') || c.includes('plug') || c.includes('relay') || c.includes('light') || c.includes('lamp') || c.includes('sensor') || c.includes('camera') || c.includes('thermostat')) {
        return 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z';
      }
      return 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';
    },
    
    // Auth & Session State
    // Seeded from the server-rendered page so a logged-in refresh never flashes the login modal;
    // the modal waits for authChecked before trusting a "not authenticated" state.
    isAuthenticated: Boolean(window.APP_CONFIG && window.APP_CONFIG.initialAuthenticated === 'true'),
    authChecked: false,
    isDemoMode: false,
    hasSavedLiveToken: false,
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

    // Multi-Network Fleet Management State (v1.5.0 - Issue #22, Issue #69)
    availableNetworks: [],
    activeNetworkId: '',
    isSwitchingNetwork: false,
    get noNetworksFound() {
      return Boolean(this.isAuthenticated && !this.isDemoMode && this.authChecked && Array.isArray(this.availableNetworks) && this.availableNetworks.length === 0);
    },

    // Device Data Usage Insights State (v1.5.0)
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

    deviceSearchQuery: '',
    selectedBandFilter: 'all',
    selectedNodeFilter: 'all',
    selectedCategoryFilter: 'all',
    selectedProfileFilter: 'all',
    selectedIpTypeFilter: 'all',
    showConnectedOnly: false,
    deviceFiltersReady: false,
    deviceSortField: 'name',
    deviceSortDirection: 'asc',
    openDeviceDropdown: null,
    toggleDeviceDropdown(name) {
      this.openDeviceDropdown = this.openDeviceDropdown === name ? null : name;
    },
    closeDeviceDropdowns() {
      this.openDeviceDropdown = null;
    },
    getBandFilterLabel() {
      const map = {
        all: this.t('devices.filter_all_bands'),
        '6GHz': this.t('devices.filter_band_6ghz'),
        '5GHz': this.t('devices.filter_band_5ghz'),
        '2.4GHz': this.t('devices.filter_band_24ghz'),
        wired: this.t('devices.filter_band_wired')
      };
      return map[this.selectedBandFilter] || this.t('devices.filter_all_bands');
    },
    getNodeFilterLabel() {
      if (this.selectedNodeFilter === 'all') return this.t('devices.filter_all_nodes');
      const node = (this.eeros || []).find(e => (e.id || e.serial) === this.selectedNodeFilter);
      return node ? node.name : this.t('devices.filter_all_nodes');
    },
    getCategoryFilterLabel() {
      if (this.selectedCategoryFilter === 'all') return this.t('devices.filter_all_categories');
      if (this.selectedCategoryFilter === 'favorites') return this.t('devices.filter_favorites');
      if (this.selectedCategoryFilter === 'new') return this.t('devices.filter_new_devices');
      const map = {
        Computer: this.t('devices.cat_computer'),
        Mobile: this.t('devices.cat_mobile'),
        'Smart Home': this.t('devices.cat_smarthome'),
        Intrattenimento: this.t('devices.cat_entertainment'),
        Gaming: this.t('devices.cat_gaming'),
        'Server/Rete': this.t('devices.cat_server'),
        Altro: this.t('devices.cat_other')
      };
      return map[this.selectedCategoryFilter] || this.selectedCategoryFilter;
    },
    getSortLabel() {
      if (this.deviceSortField === 'first_seen') {
        return this.t('devices.sort_first_seen');
      }
      if (this.deviceSortField === 'ip') return this.t('devices.sort_ip');
      if (this.deviceSortField === 'signal') return this.t('devices.sort_signal');
      if (this.deviceSortField === 'download') return this.t('devices.sort_download');
      if (this.deviceSortField === 'upload') return this.t('devices.sort_upload');
      if (this.deviceSortField === 'status') return this.t('devices.sort_status');
      return this.t('devices.sort_name');
    },
    getProfileFilterLabel() {
      if (this.selectedProfileFilter === 'all') return this.t('devices.filter_all_profiles');
      if (this.selectedProfileFilter === 'unassigned') return this.t('devices.filter_unassigned');
      const prof = (this.profiles || []).find(p => p.id === this.selectedProfileFilter);
      return prof ? ('👤 ' + prof.name) : this.t('devices.filter_all_profiles');
    },
    getIpTypeFilterLabel() {
      if (this.selectedIpTypeFilter === 'static') return this.t('devices.filter_only_static');
      if (this.selectedIpTypeFilter === 'dhcp') return this.t('devices.filter_only_dhcp');
      return this.t('devices.filter_all_assignments');
    },

    // Table Column Customization State (v1.6.1 - Issue #60)
    deviceTableColumns: (() => {
      const defaults = {
        address: true,
        profile: true,
        node: true,
        band: true,
        signal: true,
        traffic: true,
        status: true,
        first_seen: false
      };
      try {
        if (typeof localStorage !== 'undefined') {
          const saved = localStorage.getItem('eero_device_columns');
          if (saved) {
            const parsed = JSON.parse(saved);
            return { ...defaults, ...parsed };
          }
        }
      } catch (e) {}
      return defaults;
    })(),

    toggleTableColumn(colKey) {
      if (this.deviceTableColumns[colKey] !== undefined) {
        this.deviceTableColumns[colKey] = !this.deviceTableColumns[colKey];
        try {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('eero_device_columns', JSON.stringify(this.deviceTableColumns));
          }
        } catch (e) {}
      }
    },

    resetTableColumns() {
      this.deviceTableColumns = {
        address: true,
        profile: true,
        node: true,
        band: true,
        signal: true,
        traffic: true,
        status: true,
        first_seen: false
      };
      try {
        if (typeof localStorage !== 'undefined') {
          localStorage.removeItem('eero_device_columns');
        }
      } catch (e) {}
    },

    isTableColumnVisible(colKey) {
      if (colKey === 'name' || colKey === 'actions') return true;
      return this.deviceTableColumns[colKey] !== false;
    },

    getActiveColumnsCount() {
      const keys = ['address', 'profile', 'node', 'band', 'signal', 'traffic', 'status', 'first_seen'];
      return keys.filter(k => this.deviceTableColumns[k]).length;
    },

    // eeroOS Release Notes & Community Updates State (v1.6.0)
    eeroNewsLoading: false,
    eeroNewsError: null,
    eeroNewsData: null,
    eeroNewsSearchQuery: '',
    eeroNewsFilter: 'all', // 'all', 'security', 'wifi7', 'stability'
    eeroNewsExpandedVersions: {},
    eeroNewsShowAllReleases: false,
    eeroNewsDefaultLimit: 5,

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
      is_low_latency_target: false,
      dns_sync_excluded: false
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
    isClearingUla: false,

    // Port Forwarding Global State
    allForwards: [],
    newForwardForm: {
      ip: '',
      port_from: '',
      port_to: '',
      protocol: 'tcp',
      description: ''
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
    guestQrCodeUrlLight: '',
    guestQrCodeUrlDark: '',
    get activeGuestQrCodeUrl() {
      return this.guestQrCodeUrl;
    },
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
      enabled: true,
      hour: 21,
      last_sent_date: null
    },
    
    // Multi-Engine DNS Integration State (AdGuard Home, Pi-hole, Technitium)
    dnsSettings: {
      enabled: false,
      instances: []
    },
    dnsTesting: false,
    dnsSyncing: false,
    dnsTestingId: null,
    dnsSyncingId: null,
    
    // AdGuard Home DNS Integration State (Retrocompatibilità)
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

    // MQTT & Home Assistant Integration State (v1.6.1)
    mqttSettings: {
      enabled: false,
      broker_host: 'localhost',
      broker_port: 1883,
      username: '',
      has_password: false,
      base_topic: 'eero',
      discovery_enabled: true,
      discovery_prefix: 'homeassistant',
      publish_interval: 60,
      connected: false,
      available: false,
      stats: {
        messages_published: 0,
        last_published: null,
        last_error: null
      }
    },
    mqttModalForm: {
      enabled: false,
      broker_host: 'localhost',
      broker_port: 1883,
      username: '',
      password: '',
      has_password: false,
      base_topic: 'eero',
      discovery_enabled: true,
      discovery_prefix: 'homeassistant',
      publish_interval: 60
    },
    showMqttModal: false,
    mqttTesting: false,
    mqttSaving: false,
    showMqttPassword: false,
    
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
    changelogVersion: '1.6.0',
    changelogLoading: false,

    // About Modal State
    showAboutModal: false,

    // Estimated Data Usage Info Modal State
    showUsageInfoModal: false,

    // Where this instance runs (local / Docker / Kubernetes) and its source branch
    runtimeInfo: null,

    // Auto-Update State (v1.6.2)
    updateInfo: {
      update_available: false,
      current_version: '1.6.2',
      latest_version: '1.6.2',
      latest_build_number: '1',
      latest_full_version: '1.6.2 build 1',
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
    // MODULE 3: LOCAL AUTHENTICATION & RBAC STATE
    // =========================================================================
    currentUser: null,
    localAuthToken: (typeof sessionStorage !== 'undefined' && sessionStorage.getItem('eero_local_auth_token')) 
      ? sessionStorage.getItem('eero_local_auth_token') 
      : ((typeof localStorage !== 'undefined' && localStorage.getItem('eero_local_auth_token')) 
          ? localStorage.getItem('eero_local_auth_token') 
          : null),
    showLocalLoginModal: false,
    showAdminSetupModal: false,
    adminSetupRequired: false,
    localSetupData: {
      username: '',
      password: '',
      passwordConfirm: '',
      remember_me: false,
      error: '',
      loading: false
    },
    localLoginData: { username: '', password: '', remember_me: false, error: '' },
    isLocalAuthChecking: false,
    sessionTimeoutMinutes: (typeof localStorage !== 'undefined' && localStorage.getItem('eero_session_timeout') !== null) ? Number(localStorage.getItem('eero_session_timeout')) : 15,
    lastUserActivity: Date.now(),
    inactivityWatchdogStarted: false,

    // =========================================================================
    // MODULE 3: USERS & GRANULAR PERMISSIONS MANAGEMENT
    // =========================================================================
    showUsersModal: false,
    usersLoading: false,
    localUsersList: [],
    permissionsCatalog: [],
    userModalMode: 'list', // 'list' | 'create' | 'edit'
    userForm: {
      id: '',
      username: '',
      display_name: '',
      role: 'operator',
      password: '',
      is_active: true,
      permissions: []
    },

    // =========================================================================
    // MODULE 3: BACKUP & ATOMIC RESTORE
    // =========================================================================
    showBackupModal: false,
    backupLoading: false,
    backupRestoreStatus: '',
    backupRestoreIsError: false,
    dbStats: null,
    dbStatsLoading: false,
    dbCompacting: false,

    // =========================================================================
    // MODULE 3: PARENTAL SCHEDULING & TIME WINDOWS
    // =========================================================================
    schedulesList: [],
    schedulesLoading: false,
    showScheduleModal: false,
    scheduleModalMode: 'create', // 'create' | 'edit'
    scheduleForm: {
      id: '',
      name: '',
      days: ['mon', 'tue', 'wed', 'thu', 'fri'],
      start_time: '21:00',
      end_time: '07:00',
      action: 'pause',
      target_type: 'category',
      target_id: 'gaming',
      is_active: true
    },

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

    // =========================================================================
    // INITIALIZATION & I18N
    // =========================================================================
    async init() {
      console.log("Initializing eero Custom Dashboard application...");
      this.currentTab = this.tabFromPath();
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
      const syncVersion = async () => {
        try {
          const healthRes = await fetch('/api/health');
          if (healthRes.ok) {
            const hData = await healthRes.json();
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
      if (syncServer) {
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
      const isDark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (isDark) {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
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

    formatBackhaul(eero) {
      if (!eero) return '';
      if (eero.is_gateway) {
        return this.t('dashboard.backhaul_gateway');
      }
      const bh = String(eero.backhaul_type || '').trim();
      const isWired = Boolean(eero.is_wired || eero.wired || bh.toLowerCase().includes('cablato') || bh.toLowerCase().includes('ethernet') || bh.toLowerCase().includes('wired'));
      if (isWired) {
        if (/\b10\s*Gbps\b/i.test(bh) || bh.includes('10000')) return 'Ethernet (10 Gbps)';
        if (/\b2\.5\s*Gbps\b/i.test(bh) || bh.includes('2500') || bh.includes('2.5G')) return 'Ethernet (2.5 Gbps)';
        if (/\b5(?:\.0)?\s*Gbps\b/i.test(bh) || bh.includes('5000') || bh.includes('5.0G')) return 'Ethernet (5.0 Gbps)';
        if (/\b1(?:\.0)?\s*Gbps\b/i.test(bh) || bh.includes('1000') || bh.includes('1Gbps')) return 'Ethernet (1.0 Gbps)';
        if (/\b100\s*Mbps\b/i.test(bh) || bh.includes('100M')) return 'Ethernet (100 Mbps)';
        if (bh.includes('(') && bh.includes(')')) return bh;
        return this.t('dashboard.backhaul_wired');
      }
      if (bh) {
        const cleanBh = bh.replace(/\s*\((?:stimata|estimated)\)/gi, '').trim();
        const isEstimated = Boolean(eero.backhaul_estimated || /\((?:stimata|estimated)\)/i.test(bh));
        if (isEstimated) {
          const estLabel = this.t('dashboard.backhaul_estimated');
          return `${cleanBh} ${estLabel}`;
        }
        return cleanBh;
      }
      const modelStr = String(eero.model || '').toLowerCase();
      const is6Eor7 = modelStr.includes('pro 6e') || modelStr.includes('max 7') || modelStr.includes('outdoor 7') || modelStr.includes('k010001') || modelStr.includes('s010001') || modelStr.includes('t010001');
      if (is6Eor7) {
        return this.t('dashboard.backhaul_wireless_6ghz');
      }
      return this.t('dashboard.backhaul_wireless');
    },

    formatNodeStatus(eero) {
      if (!eero) return '';
      const isRebooting = ['rebooting', 'yellow'].includes(eero.status) || String(eero.state || '').toUpperCase() === 'REBOOTING';
      if (isRebooting) {
        const rebootLabel = this.t('js.format_node_status.rebooting');
        const reconnLabel = this.t('js.format_node_status.reconnecting');
        return `${rebootLabel} • ${reconnLabel}`;
      }
      const isOnline = ['online', 'green'].includes(eero.status);
      const statusLabel = isOnline ? this.t('devices.status_online') : this.t('devices.status_offline');
      const healthLabel = isOnline 
        ? this.t('dashboard.status_normal')
        : (this.t('controls.mqtt_status_disconnected'));
      return `${statusLabel} • ${healthLabel}`;
    },

    formatDnsServers(dns) {
      const fallbackIp = this.network?.gateway_ip || '192.168.4.1';
      if (!dns) return fallbackIp;
      const cleanIps = [];
      const extract = (val) => {
        if (!val) return;
        if (Array.isArray(val)) {
          val.forEach(extract);
        } else if (typeof val === 'object') {
          if (val.custom) extract(val.custom);
          if (val.nameservers) extract(val.nameservers);
          if (val.ips) extract(val.ips);
          if (val.servers) extract(val.servers);
          if (!val.custom && !val.nameservers && !val.ips && !val.servers) {
            Object.values(val).forEach(extract);
          }
        } else if (typeof val === 'string') {
          const matches = val.match(/\b(?:\d{1,3}\.){3}\d{1,3}\b/g);
          if (matches) {
            matches.forEach(ip => cleanIps.push(ip));
          } else {
            const trimmed = val.trim();
            if (trimmed && !trimmed.startsWith('{') && !trimmed.startsWith('[')) {
              cleanIps.push(trimmed);
            }
          }
        }
      };
      extract(dns);
      const unique = [...new Set(cleanIps)];
      return unique.length > 0 ? unique.join(', ') : fallbackIp;
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

    languageFlags: { en: '🇬🇧', it: '🇮🇹' },
    // Default BCP 47 region per dashboard language, used by dateLocale().
    dateLocales: { en: 'en-US', it: 'it-IT' },
    languageFlag(lang) {
      return this.languageFlags[lang] || (lang || '').toUpperCase();
    },

    // RBAC role label: auth_local.role_<role>, falling back to the raw role code.
    roleLabel(role) {
      const code = String(role || 'user').toLowerCase();
      const label = this.t('auth_local.role_' + code);
      return label !== '' ? label : code;
    },

    // eero news tags: the backend emits tag keys (security, stability, performance,
    // wifi7_6ghz, smart_home, bugfix, feature). Rows cached before that change still
    // carry the legacy Italian/English words, so each key also matches its aliases.
    newsTagAliases: {
      security: ['security', 'sicurezza'],
      stability: ['stability', 'stabilità'],
      performance: ['performance', 'prestazioni'],
      wifi7_6ghz: ['wifi7_6ghz', 'wifi7', 'wi-fi 7 / 6 ghz'],
      smart_home: ['smart_home', 'smarthome', 'smart home'],
      bugfix: ['bugfix', 'bug fix'],
      feature: ['feature', 'novità']
    },
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

    // Header toggle: steps through supportedLanguages in order.
    cycleLanguage() {
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

    loadDeviceFiltersFromUrl() {
      if (typeof window === 'undefined' || !window.location) return;
      const params = new URLSearchParams(window.location.search);
      this.deviceSearchQuery = params.get('search');
      this.selectedBandFilter = params.get('band');
      this.selectedNodeFilter = params.get('node');
      this.selectedCategoryFilter = params.get('category');
      this.selectedProfileFilter = params.get('profile');
      this.selectedIpTypeFilter = params.get('assignment');
      this.showConnectedOnly = params.get('connected') === 'true';
    },

    deviceFiltersUrl() {
      const params = new URLSearchParams();
      for (const [key, value, defaultValue] of [
        ['search', this.deviceSearchQuery, ''],
        ['band', this.selectedBandFilter, 'all'],
        ['node', this.selectedNodeFilter, 'all'],
        ['category', this.selectedCategoryFilter, 'all'],
        ['profile', this.selectedProfileFilter, 'all'],
        ['assignment', this.selectedIpTypeFilter, 'all']
      ]) {
        if (value !== defaultValue) params.set(key, value);
      }
      if (this.showConnectedOnly) params.set('connected', 'true');
      const query = params.toString();
      return `${this.routes.devices}${query ? `?${query}` : ''}`;
    },

    syncDeviceFiltersToUrl() {
      if (this.currentTab !== 'devices' || typeof window === 'undefined' || !window.location) return;
      const url = this.deviceFiltersUrl();
      if (`${window.location.pathname}${window.location.search}` !== url) {
        window.history.replaceState({}, '', url);
      }
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
    // AUTHENTICATION
    // =========================================================================
    async checkAuthStatus() {
      try {
        const res = await fetch('/api/auth/status');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.isAuthenticated = Boolean(data.authenticated);
        this.isDemoMode = Boolean(data.demo_mode);
        this.hasSavedLiveToken = Boolean(data.has_saved_live_token);
        this.userAccount = data.account;
      } catch (err) {
        // Keep the server-rendered state: a failed check must not force the login modal
        console.error("Auth status check failed:", err);
      } finally {
        this.authChecked = true;
      }
    },

    async toggleDemoMode(enableDemo) {
      this.authLoading = true;
      try {
        const resp = await fetch('/api/auth/mode', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ demo: Boolean(enableDemo) })
        });
        const data = await resp.json();
        if (resp.ok) {
          this.isDemoMode = Boolean(data.demo_mode);
          this.hasSavedLiveToken = Boolean(data.has_saved_live_token);
          this.isAuthenticated = Boolean(data.authenticated);
          this.userAccount = data.account;
          await this.refreshAllData();
          if (this.isAuthenticated) {
            this.startPolling();
          }
          const title = this.t('js.toggle_demo_mode.mode_switched');
          const msg = this.isDemoMode
            ? (this.t('js.toggle_demo_mode.demo_mode_active_your'))
            : (this.t('js.toggle_demo_mode.live_network_active_real'));
          this.showToast(title, msg, "info");
        }
      } catch (err) {
        console.error("Failed to toggle demo mode:", err);
      } finally {
        this.authLoading = false;
      }
    },

    async startDemoSession() {
      await this.toggleDemoMode(true);
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
        if (!res.ok) throw new Error(data.detail || this.t('toasts.otp_request_failed'));
        if (data.user_token) {
          this.tempUserToken = data.user_token;
        }
        this.otpSent = true;
        const title = this.t('js.request_otp.code_sent');
        const msg = this.t('js.request_otp.enter_the_6_digit');
        this.showToast(title, msg, "info");
      } catch (err) {
        this.authError = err.message;
        const title = this.t('js.request_otp.login_error');
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
        if (!res.ok) throw new Error(data.detail || (this.t('js.verify_otp.otp_verification_failed')));
        
        this.isAuthenticated = true;
        this.isDemoMode = false;
        this.hasSavedLiveToken = true;
        this.otpSent = false;
        this.otpCode = '';
        this.tempUserToken = null;
        await this.checkAuthStatus();
        const title = this.t('js.verify_otp.login_successful');
        const msg = this.t('js.verify_otp.connected_to_eero_mesh');
        this.showToast(title, msg, "success");
        await this.refreshAllData();
        this.startPolling();
      } catch (err) {
        this.authError = err.message;
        const title = this.t('js.verify_otp.otp_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.authLoading = false;
      }
    },

    async logout() {
      try {
        await fetch('/api/auth/logout', { method: 'POST' });
        this.isAuthenticated = false;
        this.isDemoMode = false;
        this.userAccount = null;
        if (this.pollingTimer) clearInterval(this.pollingTimer);
        const title = this.t('js.logout.logged_out');
        const msg = this.t('js.logout.session_closed_successfully');
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
        this.loadSpeedtestData(),
      ]);
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
    // NETWORK & NODES ACTIONS
    // =========================================================================
    async rebootNetwork() {
      const confirmMsg = this.t('js.reboot_network.are_you_sure_you');
      if (!confirm(confirmMsg)) return;

      try {
        const res = await fetch('/api/network/reboot', { method: 'POST' });
        const data = await res.json();
        const title = this.t('js.reboot_network.network_reboot');
        this.showToast(title, data.message || (this.t('js.reboot_network.reboot_command_sent')), "info");
      } catch (err) {
        const title = this.t('js.reboot_network.reboot_error');
        this.showToast(title, err.message, "error");
      }
    },

    async rebootEero(eero) {
      const eid = eero.id || eero.serial;
      const confirmMsg = this.t('js.reboot_eero.reboot_node', { name: eero.name || eid });
      if (!confirm(confirmMsg)) return;

      try {
        const res = await fetch(`/api/network/eeros/${eid}/reboot`, { method: 'POST' });
        const data = await res.json();
        const title = this.t('js.reboot_eero.node_reboot');
        this.showToast(title, data.message || (this.t('js.reboot_eero.rebooting_node', { name: eero.name })), "info");
      } catch (err) {
        const title = this.t('js.reboot_network.reboot_error');
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
          throw new Error(data.message || data.detail || (this.t('js.toggle_eero_led.failed_to_update_led')));
        }
        eero.led_on = targetState;
        const title = this.t('js.toggle_eero_led.led_updated');
        const msg = this.t('js.toggle_eero_led.led_state', { name: eero.name, state: targetState ? this.t('common.on') : this.t('common.off') });
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.t('js.toggle_eero_led.led_error');
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
          throw new Error(data.message || data.detail || (this.t('js.toggle_all_leds.failed_to_update_all')));
        }
        this.eeros.forEach(e => e.led_on = ledOn);
        const title = this.t('js.toggle_all_leds.all_leds');
        const msg = this.t('js.toggle_all_leds.all_leds_set_to', { state: ledOn ? this.t('common.on_plural') : this.t('common.off_plural') });
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.t('js.toggle_eero_led.led_error');
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

    get filteredDevices() {
      const list = this.devices.filter(d => {
        // Filtro online
        if (this.showConnectedOnly && !d.connected) return false;
        
        // Filtro banda
        if (this.selectedBandFilter !== 'all') {
          const b = this.selectedBandFilter;
          if (b === 'wired') {
            if (d.connection_type !== 'wired' && d.wireless && d.frequency_band !== 'Cablato') return false;
          } else {
            const is6G = Boolean(
              d.wireless_band === '6GHz' || 
              d.frequency_band === '6 GHz' || 
              d.frequency_band === '6GHz' || 
              (d.channel > 177) ||
              (d.channel && [37, 53, 69, 85, 101, 117, 133, 181, 197, 213, 229].includes(d.channel)) ||
              (d.frequency && d.frequency >= 5900 && d.frequency <= 7200)
            );
            const is24G = Boolean(
              d.wireless_band === '2.4GHz' || 
              d.frequency_band === '2.4 GHz' || 
              d.frequency_band === '2.4GHz' || 
              (d.channel >= 1 && d.channel <= 14 && !is6G) ||
              (d.frequency && d.frequency >= 2400 && d.frequency <= 2500)
            );
            const is5G = Boolean(!is6G && !is24G && (
              d.wireless_band === '5GHz' || 
              d.frequency_band === '5 GHz' || 
              d.frequency_band === '5GHz' || 
              (d.channel >= 32 && d.channel <= 177) ||
              (d.frequency && d.frequency >= 5000 && d.frequency < 5900)
            ));
            
            let match = false;
            if (b === '6GHz') match = is6G;
            else if (b === '5GHz') match = is5G;
            else if (b === '2.4GHz') match = is24G;
            else match = (d.wireless_band === b) || (d.frequency_band && d.frequency_band.replace(' ', '') === b);
            
            if (!match) return false;
          }
        }

        // Filtro nodo
        if (this.selectedNodeFilter !== 'all') {
          if (d.connected_eero_id !== this.selectedNodeFilter && d.connected_eero_name !== this.selectedNodeFilter) {
            return false;
          }
        }

        // Filtro categoria / preferiti / nuovi dispositivi (Issue #60)
        if (this.selectedCategoryFilter !== 'all') {
          if (this.selectedCategoryFilter === 'favorites') {
            if (!d.is_favorite) return false;
          } else if (this.selectedCategoryFilter === 'new') {
            if (!d.is_new) return false;
          } else if (this.selectedCategoryFilter === 'Altro' || this.selectedCategoryFilter === 'Other') {
            const dc = (d.category || '').toLowerCase();
            if (dc !== 'altro' && dc !== 'other' && dc !== '') return false;
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
          const ipv6 = (d.ipv6 || '').toLowerCase();
          const ipv6List = (d.ipv6_all || d.ipv6_addresses || []).join(' ').toLowerCase();
          return name.includes(q) || ip.includes(q) || mac.includes(q) || notes.includes(q) || cat.includes(q) || prof.includes(q) || ipv6.includes(q) || ipv6List.includes(q);
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
            res = nameA.localeCompare(nameB, this.dateLocale());
            break;
          }
          case 'ip': {
            const numA = ipToInt(a.ip);
            const numB = ipToInt(b.ip);
            res = numA - numB;
            if (res === 0) {
              res = (a.mac || '').localeCompare(b.mac || '', this.dateLocale());
            }
            break;
          }
          case 'profile': {
            const profA = (a.profile_name || '').toLowerCase();
            const profB = (b.profile_name || '').toLowerCase();
            res = profA.localeCompare(profB, this.dateLocale());
            break;
          }
          case 'node': {
            const nodeA = (a.connected_eero_name || this.t('common.gateway')).toLowerCase();
            const nodeB = (b.connected_eero_name || this.t('common.gateway')).toLowerCase();
            res = nodeA.localeCompare(nodeB, this.dateLocale());
            break;
          }
          case 'band': {
            const getBandRank = (d) => {
              if (d.connection_type === 'wired' || !d.wireless || d.frequency_band === 'Cablato') return '1_Ethernet';
              if (d.wireless_band === '6GHz' || d.frequency_band === '6 GHz') return '2_6GHz';
              if (d.wireless_band === '5GHz' || d.frequency_band === '5 GHz') return '3_5GHz';
              return '4_2.4GHz';
            };
            res = getBandRank(a).localeCompare(getBandRank(b), this.dateLocale());
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
          case 'download': {
            const dlA = Number(a.rx_bytes || 0);
            const dlB = Number(b.rx_bytes || 0);
            res = dlA - dlB;
            if (res === 0) {
              const nameA = (a.custom_name || a.nickname || a.hostname || '').toLowerCase();
              const nameB = (b.custom_name || b.nickname || b.hostname || '').toLowerCase();
              res = nameA.localeCompare(nameB, this.dateLocale());
            }
            break;
          }
          case 'upload': {
            const ulA = Number(a.tx_bytes || 0);
            const ulB = Number(b.tx_bytes || 0);
            res = ulA - ulB;
            if (res === 0) {
              const nameA = (a.custom_name || a.nickname || a.hostname || '').toLowerCase();
              const nameB = (b.custom_name || b.nickname || b.hostname || '').toLowerCase();
              res = nameA.localeCompare(nameB, this.dateLocale());
            }
            break;
          }
          case 'first_seen': {
            const getTimestamp = (d) => {
              if (!d || !d.first_seen) return 0;
              const s = String(d.first_seen).replace(' ', 'T');
              const t = new Date(s).getTime();
              return isNaN(t) ? 0 : t;
            };
            res = getTimestamp(a) - getTimestamp(b);
            if (res === 0) {
              const nameA = (a.custom_name || a.nickname || a.hostname || '').toLowerCase();
              const nameB = (b.custom_name || b.nickname || b.hostname || '').toLowerCase();
              res = nameA.localeCompare(nameB, this.dateLocale());
            }
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
        return { 
          hasConflict: true, 
          isReassign: false, 
          message: this.t('js.toggle_device_sort.invalid_ipv4_address_format') 
        };
      }

      // 1. Conflitto Bloccante: Gateway o nodi mesh
      if (this.network && this.network.gateway_ip === targetIp) {
        return { 
          hasConflict: true, 
          isReassign: false, 
          message: this.t('js.toggle_device_sort.ip_is_the_eero', { targetIp: targetIp }) 
        };
      }
      for (const node of (this.eeros || [])) {
        if (node.ip === targetIp) {
          return { 
            hasConflict: true, 
            isReassign: false, 
            message: this.t('js.toggle_device_sort.ip_is_assigned_to', { targetIp: targetIp, name: node.name }) 
          };
        }
      }

      // 2. Se questo stesso dispositivo sta già usando questo IP (lease dinamico o statico)
      if (this.selectedDevice.ip === targetIp) {
        return { 
          hasConflict: false, 
          isReassign: false, 
          message: this.t('js.toggle_device_sort.this_device_is_already', { targetIp: targetIp })
        };
      }

      // 3. Riassegnazione da una prenotazione esistente (es. altra scheda di rete dello stesso PC o vecchio dispositivo)
      for (const res of (this.allReservations || [])) {
        const resIp = res.ip || res.ip_address;
        const resMac = (res.mac || res.mac_address || '').toLowerCase();
        if (resIp === targetIp && resMac !== currentMac) {
          return { 
            hasConflict: false, 
            isReassign: true, 
            message: this.t('js.toggle_device_sort.ip_is_currently_reserved', { targetIp: targetIp, description: res.description || res.name || resMac })
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
            message: this.t('js.toggle_device_sort.ip_is_currently_assigned', { targetIp: targetIp, custom_name: dev.custom_name || dev.nickname || dev.hostname || dMac })
          };
        }
      }

      return { 
        hasConflict: false, 
        isReassign: false, 
        message: this.t('js.toggle_device_sort.ip_address_is_available') 
      };
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
        custom_icon: device.custom_icon || device.default_icon || 'device',
        category: device.category || device.default_category || 'Altro',
        custom_notes: device.custom_notes || '',
        is_favorite: Boolean(device.is_favorite),
        is_low_latency_target: Boolean(device.is_low_latency_target),
        dns_sync_excluded: Boolean(device.dns_sync_excluded)
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
            this.deviceStaticIpInput = this.deviceReservation.ip || this.deviceReservation.ip_address || '';
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

    async clearDeviceDiscoveredUla(device) {
      if (!device || this.isClearingUla) return;
      const mac = (device.mac || device.mac_address || '').toLowerCase();
      if (!mac) return;
      
      const count = (device.ipv6_details ? device.ipv6_details.filter(d => d.origin === 'ndp_discovered').length : 0) || (device.discovered_ips ? device.discovered_ips.length : 1);
      if (!confirm(this.t('device_modal.clear_ula_confirm', { count }))) {
        return;
      }

      this.isClearingUla = true;
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch(`/api/devices/${encodeURIComponent(mac)}/clear-ula`, {
          method: 'POST',
          headers
        });
        if (res.ok) {
          if (this.selectedDevice) {
            this.selectedDevice.ipv6_details = (this.selectedDevice.ipv6_details || []).filter(d => d.origin !== 'ndp_discovered');
            const discSet = new Set((this.selectedDevice.discovered_ips || []).map(i => i.ip_address));
            this.selectedDevice.ipv6_ula = (this.selectedDevice.ipv6_ula || []).filter(ip => !discSet.has(ip));
            this.selectedDevice.ipv6_addresses = (this.selectedDevice.ipv6_addresses || []).filter(ip => !discSet.has(ip));
            this.selectedDevice.ipv6_all = this.selectedDevice.ipv6_addresses;
            this.selectedDevice.has_discovered_ips = false;
            this.selectedDevice.discovered_ips = [];
          }
          this.showToast(this.t('toasts.success_title'), this.t('device_modal.clear_ula_success'), 'success');
        } else {
          this.showToast(this.t('toasts.error'), this.t('device_modal.clear_ula_error'), 'error');
        }
      } catch (err) {
        console.error("Clear device ULA error:", err);
        this.showToast(this.t('toasts.error'), this.t('device_modal.clear_ula_error'), 'error');
      } finally {
        this.isClearingUla = false;
      }
    },

    async saveDeviceReservation() {
      if (!this.selectedDevice || !this.deviceStaticIpInput) return;
      const mac = (this.selectedDevice.mac || this.selectedDevice.mac_address || '').toLowerCase();
      try {
        const desc = this.deviceMetadataForm.custom_name || this.selectedDevice.nickname || this.selectedDevice.hostname || this.t('devices.generic_device');
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
          throw new Error(data.detail || data.message || this.t('device_modal.reservation_error'));
        }

        const title = this.t('toasts.static_reserved');
        const msg = this.t('js.save_device_reservation.ip_address_successfully_reserved', { ip: this.deviceStaticIpInput });
        this.showToast(title, msg, "success");
        await this.loadDeviceRules(mac);
        await this.fetchDevices();
      } catch (err) {
        const title = this.t('js.save_device_reservation.ip_reservation_error');
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
          throw new Error(data.detail || data.message || (this.t('js.remove_device_reservation.error_removing_ip_reservation')));
        }

        const title = this.t('toasts.static_removed');
        const msg = this.t('js.remove_device_reservation.static_ip_reservation_removed');
        this.showToast(title, msg, "info");
        await this.loadDeviceRules(mac);
        await this.fetchDevices();
      } catch (err) {
        const title = this.t('js.remove_device_reservation.removal_error');
        this.showToast(title, err.message, "error");
      }
    },

    async addDevicePortForward() {
      if (!this.selectedDevice) return;
      const targetIp = (this.deviceReservation ? (this.deviceReservation.ip || this.deviceReservation.ip_address || '') : (this.selectedDevice.ip || '')).trim();
      if (!targetIp) {
        const title = this.t('js.add_device_port_forward.missing_ip');
        const msg = this.t('js.add_device_port_forward.device_must_have_a');
        this.showToast(title, msg, "warning");
        return;
      }
      const pFrom = parseInt(this.newPortForward.port_from);
      const pTo = parseInt(this.newPortForward.port_to);
      if (isNaN(pFrom) || isNaN(pTo) || pFrom < 1 || pFrom > 65535 || pTo < 1 || pTo > 65535) {
        const title = this.t('js.add_device_port_forward.invalid_port');
        const msg = this.t('js.add_device_port_forward.please_enter_valid_port');
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
            description: this.newPortForward.description || this.t('js.add_device_port_forward.custom_forward')
          })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.t('js.add_device_port_forward.error_creating_port_forward')));
        }

        const title = this.t('toasts.forward_added');
        const msg = this.t('js.add_device_port_forward.rule_for_port_created', { pFrom: pFrom });
        this.showToast(title, msg, "success");
        this.newPortForward = { port_from: '', port_to: '', protocol: 'tcp', description: '' };
        await this.loadDeviceRules(mac);
      } catch (err) {
        const title = this.t('js.add_device_port_forward.port_forward_error');
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
          throw new Error(data.detail || data.message || (this.t('js.delete_device_port_forward.error_deleting_forwarding_rule')));
        }

        const title = this.t('toasts.forward_deleted');
        const msg = this.t('js.delete_device_port_forward.port_forwarding_rule_deleted');
        this.showToast(title, msg, "info");
        await this.loadDeviceRules(mac);
      } catch (err) {
        const title = this.t('js.delete_device_port_forward.deletion_error');
        this.showToast(title, err.message, "error");
      }
    },

    async saveDeviceMetadata() {
      if (!this.selectedDevice) return;
      const targetId = (this.selectedDevice.mac || this.selectedDevice.id || this.selectedDevice.mac_address || '').toLowerCase();
      if (!targetId) {
        this.showToast(this.t('toasts.error'), this.t('devices.device_id_not_found'), "error");
        return;
      }
      try {
        const res = await fetch(`/api/devices/${encodeURIComponent(targetId)}/metadata`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.deviceMetadataForm)
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.message || `HTTP ${res.status}`);
        }
        const data = await res.json().catch(() => ({}));
        
        // Se il nome è cambiato, sincronizza anche il nickname con eero
        if (this.deviceMetadataForm.custom_name && this.deviceMetadataForm.custom_name !== this.selectedDevice.nickname) {
          const devId = this.selectedDevice.id || targetId;
          try {
            await fetch(`/api/devices/${encodeURIComponent(devId)}/rename`, {
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
          is_low_latency_target: Boolean(this.deviceMetadataForm.is_low_latency_target),
          dns_sync_excluded: Boolean(this.deviceMetadataForm.dns_sync_excluded)
        });

        const title = this.t('toasts.saved');
        const msg = this.t('js.save_device_metadata.device_metadata_and_category');
        this.showToast(title, msg, "success");
        this.showDeviceModal = false;
        await this.fetchDevices();
      } catch (err) {
        const title = this.t('js.save_device_metadata.save_error');
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
        const title = this.t('js.create_profile.name_required');
        const msg = this.t('js.create_profile.please_enter_a_profile');
        this.showToast(title, msg, "warning");
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
          throw new Error(data.detail || data.message || (this.t('js.create_profile.unable_to_create_profile')));
        }

        const title = this.t('js.create_profile.profile_created');
        const msg = this.t('js.create_profile.profile_created_successfully_on', { name: this.newProfileForm.name });
        this.showToast(title, msg, "success");
        this.showCreateProfileModal = false;
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        const title = this.t('js.create_profile.profile_creation_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.profileAssigningLoading = false;
      }
    },

    async deleteProfile(profile) {
      const pName = profile.name || (this.t('js.delete_profile.this_profile'));
      const promptMsg = (this.translations.profiles && this.translations.profiles.delete_profile_confirm)
        ? this.translations.profiles.delete_profile_confirm.replace('{name}', pName)
        : (this.t('js.delete_profile.are_you_sure_you', { pName: pName }));

      if (!confirm(promptMsg)) return;

      try {
        const res = await fetch(`/api/profiles/${profile.id}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.t('js.delete_profile.unable_to_delete_profile')));
        }

        const title = this.t('js.delete_profile.profile_deleted');
        const msg = this.t('js.delete_profile.profile_removed_from_eero', { pName: pName });
        this.showToast(title, msg, "info");
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        const title = this.t('js.delete_profile.deletion_error');
        this.showToast(title, err.message, "error");
      }
    },

    async assignDeviceToProfile(deviceMacOrId, profileId) {
      if (!deviceMacOrId) return;
      const isRemoving = !profileId;
      try {
        const res = await fetch(`/api/devices/${deviceMacOrId}/profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile_id: profileId || null })
        });
        const data = await res.json();
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || (this.t('js.assign_device_to_profile.profile_assignment_error')));
        }

        const title = this.t('js.assign_device_to_profile.profile_updated');
        const msg = isRemoving
          ? (this.t('js.assign_device_to_profile.device_removed_from_profile'))
          : (this.t('js.assign_device_to_profile.device_assigned_to_profile'));
        this.showToast(title, msg, "success");
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        const title = this.t('js.assign_device_to_profile.assignment_error');
        this.showToast(title, err.message, "error");
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
    // SIGNAL QUALITY & MESH COVERAGE (v1.04.00)
    // =========================================================================
    async loadSignalOverview() {
      try {
        const res = await fetch('/api/metrics/signal/overview');
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success' && data.overview) {
            this.signalOverview = data.overview;
            if (!this.selectedSignalDeviceMac && this.signalOverview.devices && this.signalOverview.devices.length > 0) {
              this.selectedSignalDeviceMac = this.signalOverview.devices[0].mac_address;
              await this.loadDeviceSignalHistory();
            }
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
        const res = await fetch(`/api/metrics/signal/history?mac=${encodeURIComponent(this.selectedSignalDeviceMac)}&hours=${this.signalHistoryHours}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'success' && data.history) {
            this.renderSignalChart(data.history);
          }
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
    // CONTROLS & AUTOMATIONS
    // =========================================================================
    async fetchGuestNetwork() {
      try {
        const res = await fetch('/api/network/guest');
        const json = await res.json();
        if (json.status === 'success') {
          this.guestNetwork = json.guest_network || {};
          this.guestQrCodeUrlLight = json.qr_code_data_url_light || json.qr_code_data_url || '';
          this.guestQrCodeUrlDark = json.qr_code_data_url_dark || '';
          this.updateActiveQrCode();
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
        this.guestQrCodeUrlLight = json.qr_code_data_url_light || json.qr_code_data_url || '';
        this.guestQrCodeUrlDark = json.qr_code_data_url_dark || '';
        this.updateActiveQrCode();
        this.showToast(this.t('toasts.guest_network'), this.t(targetState ? 'toasts.guest_enabled' : 'toasts.guest_disabled'), "info");
      } catch (err) {
        this.showToast(this.t('toasts.guest_error'), err.message, "error");
      }
    },

    async generateGuestPassword() {
      try {
        const res = await fetch('/api/network/guest/generate-password', { method: 'POST' });
        const json = await res.json();
        this.guestNetwork.password = json.password;
        this.showToast(this.t('toasts.new_password'), this.t('toasts.password_generated'), "info");
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
        this.guestQrCodeUrlLight = json.qr_code_data_url_light || json.qr_code_data_url || '';
        this.guestQrCodeUrlDark = json.qr_code_data_url_dark || '';
        this.updateActiveQrCode();
        this.showToast(this.t('toasts.guest_updated'), this.t('toasts.guest_saved_desc'), "success");
      } catch (err) {
        this.showToast(this.t('toasts.error'), err.message, "error");
      }
    },

    copyGuestCredentials() {
      const name = this.guestNetwork?.name || 'eero-guest';
      const password = this.guestNetwork?.password || '';
      const text = password 
        ? this.t('js.copy_guest_credentials.wi_fi_with_password', { name: name, password: password })
        : (this.t('js.copy_guest_credentials.wi_fi_open_network', { name: name }));
      const msg = this.t('js.copy_guest_credentials.guest_wi_fi_credentials');
      this.copyToClipboard(text, msg);
    },

    copyGuestPassword() {
      const password = this.guestNetwork?.password || '';
      if (!password) {
        this.showToast(
          this.t('js.copy_guest_password.open_network'), 
          this.t('js.copy_guest_password.guest_network_is_open'), 
          'info'
        );
        return;
      }
      const msg = this.t('js.copy_guest_password.guest_password_copied_to');
      this.copyToClipboard(password, msg);
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
        const title = targetState 
          ? (this.t('js.toggle_focus_mode.gaming_mode_activated'))
          : (this.t('js.toggle_focus_mode.gaming_mode_deactivated'));
        this.showToast(
          title,
          json.message,
          targetState ? "warning" : "success"
        );
        await this.fetchDevices();
      } catch (err) {
        const title = this.t('js.toggle_focus_mode.focus_mode_error');
        this.showToast(title, err.message, "error");
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
        const title = this.t('js.save_night_mode.night_mode');
        const msg = this.t('js.save_night_mode.led_schedule_saved_successfully');
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.t('toasts.error');
        this.showToast(title, err.message, "error");
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
          body: JSON.stringify({
            ...this.notificationSettings,
            language: this.currentLanguage
          })
        });
        const title = this.t('js.save_notification_settings.notifications_saved');
        const msg = this.t('js.save_notification_settings.alert_channel_settings_updated');
        this.showToast(title, msg, "success");
      } catch (err) {
        const title = this.t('toasts.error');
        this.showToast(title, err.message, "error");
      }
    },

    async testNotifications() {
      try {
        const res = await fetch('/api/automations/notifications/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: this.currentLanguage })
        });
        const json = await res.json();
        const title = this.t('js.test_notifications.test_sent');
        const okLabel = this.t('js.test_notifications.status_ok');
        const noLabel = this.t('js.test_notifications.status_no');
        this.showToast(title, `Telegram: ${json.telegram_sent ? okLabel : noLabel} | Webhook: ${json.webhook_sent ? okLabel : noLabel}`, 'info');
      } catch (err) {
        const title = this.t('js.test_notifications.test_error');
        this.showToast(title, err.message, "error");
      }
    },

    // =========================================================================
    // MULTI-ENGINE DNS SYNCHRONIZER (AdGuard, Pi-hole, Technitium)
    // =========================================================================
    // Stessa normalizzazione di normalize_dns_url (backend): frammento, slash finali, http:// se manca lo schema
    normalizeDnsUrl(url) {
      let clean = String(url || '').trim();
      if (!clean) return '';
      if (clean.includes('#')) clean = clean.split('#')[0];
      clean = clean.replace(/\/+$/, '');
      if (!clean.startsWith('http://') && !clean.startsWith('https://')) clean = 'http://' + clean;
      return clean;
    },

    async fetchDnsSettings() {
      try {
        const res = await fetch('/api/automations/dns');
        const json = await res.json().catch(() => ({}));
        if (json.status === 'success') {
          this.dnsSettings = {
            enabled: Boolean(json.enabled),
            instances: (json.instances || []).map(i => ({
              id: i.id || ('inst-' + Math.random().toString(36).substr(2, 9)),
              name: i.name || this.t('controls.dns_default_name'),
              engine: i.engine || 'adguard',
              url: i.url || '',
              username: i.username || '',
              password: '',
              token: '',
              zone: (i.zone !== undefined && i.zone !== null) ? i.zone : 'lan',
              has_password: Boolean(i.has_password),
              has_token: Boolean(i.has_token),
              enabled: i.enabled !== false,
              prune_stale_ips: i.prune_stale_ips !== undefined ? Boolean(i.prune_stale_ips) : true,
              drop_ipv6: Boolean(i.drop_ipv6),
              insecure_tls: i.insecure_tls === true,
              tls_url: i.insecure_tls === true ? this.normalizeDnsUrl(i.url) : '',
              last_sync_time: i.last_sync_time || '',
              last_sync_status: i.last_sync_status || '',
              last_sync_count: i.last_sync_count || 0
            }))
          };
          // Sync retrocompatibilità con adguardSettings
          const firstAdg = this.dnsSettings.instances.find(x => x.engine === 'adguard');
          if (firstAdg) {
            this.adguardSettings = {
              enabled: this.dnsSettings.enabled && firstAdg.enabled,
              url: firstAdg.url,
              username: firstAdg.username,
              password: '',
              has_password: firstAdg.has_password,
              last_sync_time: firstAdg.last_sync_time,
              last_sync_count: firstAdg.last_sync_count,
              last_sync_status: firstAdg.last_sync_status
            };
          }
        }
      } catch (err) {
        console.error("Fetch DNS settings error:", err);
      }
    },

    addDnsInstance() {
      const newInst = {
        id: 'inst-' + Date.now(),
        name: this.t('controls.dns_default_name_n', { n: this.dnsSettings.instances.length + 1 }),
        engine: 'adguard',
        url: 'http://192.168.1.50:80',
        username: '',
        password: '',
        token: '',
        zone: 'lan',
        has_password: false,
        has_token: false,
        enabled: true,
        prune_stale_ips: true,
        drop_ipv6: false,
        insecure_tls: false,
        tls_url: '',
        last_sync_time: '',
        last_sync_status: '',
        last_sync_count: 0
      };
      this.dnsSettings.instances.push(newInst);
      const title = this.t('js.add_dns_instance.new_instance_added');
      this.showToast(title, newInst.name, "info");
    },

    removeDnsInstance(instId) {
      const idx = this.dnsSettings.instances.findIndex(x => x.id === instId);
      if (idx >= 0) {
        const inst = this.dnsSettings.instances[idx];
        const confirmMsg = this.t('js.remove_dns_instance.are_you_sure_you', { name: inst.name });
        if (confirm(confirmMsg)) {
          this.dnsSettings.instances.splice(idx, 1);
          const title = this.t('js.remove_dns_instance.instance_removed');
          this.showToast(title, inst.name, "info");
        }
      }
    },

    async saveDnsSettings() {
      try {
        const payload = {
          enabled: Boolean(this.dnsSettings.enabled),
          instances: this.dnsSettings.instances.map(inst => ({
            id: inst.id,
            name: inst.name,
            engine: inst.engine,
            url: inst.url,
            username: inst.username,
            password: inst.password || undefined,
            token: inst.token || undefined,
            zone: inst.zone,
            enabled: inst.enabled,
            prune_stale_ips: inst.prune_stale_ips !== false,
            drop_ipv6: Boolean(inst.drop_ipv6),
            insecure_tls: inst.insecure_tls === true
          }))
        };
        const res = await fetch('/api/automations/dns', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok) {
          const title = "Multi-DNS";
          const msg = this.t('js.save_dns_settings.multi_dns_settings_saved');
          this.showToast(title, msg, "success");
          await this.fetchDnsSettings();
        } else {
          throw new Error(json.detail || json.message || this.t('toasts.dns_save_error'));
        }
      } catch (err) {
        const title = this.t('js.save_device_metadata.save_error');
        this.showToast(title, err.message, "error");
      }
    },

    async testDnsInstance(inst) {
      this.dnsTesting = true;
      this.dnsTestingId = inst.id;
      try {
        const payload = {
          instance: {
            id: inst.id,
            name: inst.name,
            engine: inst.engine,
            url: inst.url,
            username: inst.username,
            password: inst.password || undefined,
            token: inst.token || undefined,
            zone: inst.zone,
            enabled: inst.enabled,
            insecure_tls: inst.insecure_tls === true
          }
        };
        const res = await fetch('/api/automations/dns/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.success) {
          if (json.normalized_url) inst.url = json.normalized_url;
          const title = this.t('js.test_dns_instance.connection_test_succeeded');
          this.showToast(title, `${inst.name}: ${json.message}`, "success");
        } else {
          const title = this.t('js.test_dns_instance.test_failed');
          const failMsg = (json.tls_error && this.t('controls.dns_tls_error')) || json.message || this.t('toasts.connection_failed');
          this.showToast(title, `${inst.name}: ${failMsg}`, "error");
        }
      } catch (err) {
        const title = this.t('js.test_notifications.test_error');
        this.showToast(title, `${inst.name}: ${err.message}`, "error");
      } finally {
        this.dnsTesting = false;
        this.dnsTestingId = null;
      }
    },

    async testAllDns() {
      this.dnsTesting = true;
      this.dnsTestingId = 'all';
      try {
        const res = await fetch('/api/automations/dns/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.success) {
          const title = this.t('js.test_all_dns.all_tests_succeeded');
          const msg = this.t('js.test_all_dns.all_dns_instances_are', { total_tested: json.total_tested });
          this.showToast(title, msg, "success");
        } else {
          const title = this.t('js.test_all_dns.some_tests_failed');
          this.showToast(title, json.message || this.t('js.test_all_dns.instances_not_responding'), 'warning');
        }
      } catch (err) {
        const title = this.t('js.test_all_dns.global_test_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.dnsTesting = false;
        this.dnsTestingId = null;
      }
    },

    async syncDnsInstance(inst) {
      this.dnsSyncing = true;
      this.dnsSyncingId = inst.id;
      try {
        const res = await fetch('/api/automations/dns/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ instance_id: inst.id })
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.status === 'success') {
          const title = this.t('js.sync_dns_instance.sync_succeeded');
          const msg = json.message || this.t('js.sync_dns_instance.completed');
          this.showToast(title, `${inst.name}: ${msg}`, "success");
          await this.fetchDnsSettings();
        } else {
          const title = this.t('js.sync_dns_instance.sync_error');
          this.showToast(title, `${inst.name}: ${json.detail || json.message || this.t('toasts.sync_failed')}`, "error");
        }
      } catch (err) {
        const title = this.t('js.sync_dns_instance.sync_error');
        this.showToast(title, `${inst.name}: ${err.message}`, "error");
      } finally {
        this.dnsSyncing = false;
        this.dnsSyncingId = null;
      }
    },

    async syncAllDns() {
      this.dnsSyncing = true;
      this.dnsSyncingId = 'all';
      try {
        const res = await fetch('/api/automations/dns/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.status === 'success') {
          const title = this.t('js.sync_all_dns.global_sync_completed');
          const msg = json.message || this.t('js.sync_all_dns.completed');
          this.showToast(title, msg, "success");
          await this.fetchDnsSettings();
        } else {
          const title = this.t('js.sync_dns_instance.sync_error');
          this.showToast(title, json.detail || json.message || this.t('toasts.sync_failed'), "error");
        }
      } catch (err) {
        const title = this.t('js.sync_dns_instance.sync_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.dnsSyncing = false;
        this.dnsSyncingId = null;
      }
    },

    // =========================================================================
    // ADGUARD HOME DNS & DHCP CLIENT SYNC (Retrocompatibilità)
    // =========================================================================
    async fetchAdGuardSettings() {
      try {
        const res = await fetch('/api/automations/adguard');
        const json = await res.json().catch(() => ({}));
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
        const json = await res.json().catch(() => ({}));
        if (res.ok) {
          const msg = json.message || (this.t('js.save_ad_guard_settings.settings_saved_successfully'));
          this.showToast("AdGuard Home", msg, "success");
          await this.fetchAdGuardSettings();
        } else {
          const title = this.t('js.save_ad_guard_settings.adguard_error');
          const msg = json.detail || json.message || (this.t('js.save_ad_guard_settings.could_not_save_settings'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.save_ad_guard_settings.adguard_error');
        this.showToast(title, err.message, "error");
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
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.success) {
          if (json.normalized_url) {
            this.adguardSettings.url = json.normalized_url;
          }
          const title = this.t('js.test_dns_instance.connection_test_succeeded');
          this.showToast(title, json.message, "success");
        } else {
          const title = this.t('js.test_dns_instance.test_failed');
          const msg = json.message || json.detail || (this.t('js.test_ad_guard_connection.could_not_connect_to'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.test_notifications.test_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.adguardTesting = false;
      }
    },

    async syncAdGuardNow() {
      this.adguardSyncing = true;
      try {
        const payload = {
          url: this.adguardSettings.url,
          username: this.adguardSettings.username,
          password: this.adguardSettings.password || undefined
        };
        const res = await fetch('/api/automations/adguard/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.status === 'success') {
          const title = this.t('js.sync_ad_guard_now.sync_completed');
          const msg = json.message || this.t('js.sync_ad_guard_now.completed');
          this.showToast(title, msg, "success");
          await this.fetchAdGuardSettings();
        } else {
          const title = this.t('js.sync_dns_instance.sync_error');
          const msg = json.detail || json.message || (this.t('js.sync_ad_guard_now.synchronization_failed'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.sync_dns_instance.sync_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.adguardSyncing = false;
      }
    },

    // =========================================================================
    // MQTT & HOME ASSISTANT GATEWAY (v1.6.1 - Modulo 2)
    // =========================================================================
    async fetchMqttSettings() {
      try {
        const res = await fetch('/api/automations/mqtt/config');
        const json = await res.json();
        const cfg = (json && typeof json === 'object') ? (json.config || json) : null;
        if (cfg && typeof cfg === 'object') {
          this.mqttSettings = {
            ...this.mqttSettings,
            ...cfg,
            connected: Boolean(cfg.connected),
            available: Boolean(cfg.available),
            stats: cfg.stats || {
              messages_published: 0,
              last_published: null,
              last_error: null
            }
          };
        }
      } catch (err) {
        console.error("Fetch MQTT settings error:", err);
      }
    },

    openMqttModal() {
      this.mqttModalForm = {
        enabled: Boolean(this.mqttSettings.enabled),
        broker_host: this.mqttSettings.broker_host || 'localhost',
        broker_port: this.mqttSettings.broker_port || 1883,
        username: this.mqttSettings.username || '',
        password: '',
        has_password: Boolean(this.mqttSettings.has_password),
        base_topic: this.mqttSettings.base_topic || 'eero',
        discovery_enabled: this.mqttSettings.discovery_enabled !== false,
        discovery_prefix: this.mqttSettings.ha_discovery_prefix || this.mqttSettings.discovery_prefix || 'homeassistant',
        publish_interval: this.mqttSettings.publish_interval || 60
      };
      this.showMqttPassword = false;
      this.showMqttModal = true;
    },

    closeMqttModal() {
      this.showMqttModal = false;
      this.showMqttPassword = false;
    },

    async saveMqttSettings() {
      this.mqttSaving = true;
      try {
        const payload = {
          enabled: Boolean(this.mqttModalForm.enabled),
          broker_host: (this.mqttModalForm.broker_host || 'localhost').trim(),
          broker_port: parseInt(this.mqttModalForm.broker_port, 10) || 1883,
          username: (this.mqttModalForm.username || '').trim(),
          base_topic: (this.mqttModalForm.base_topic || 'eero').trim() || 'eero',
          discovery_enabled: Boolean(this.mqttModalForm.discovery_enabled),
          ha_discovery_prefix: (this.mqttModalForm.discovery_prefix || 'homeassistant').trim() || 'homeassistant',
          publish_interval: parseInt(this.mqttModalForm.publish_interval, 10) || 60
        };
        if (this.mqttModalForm.password) {
          payload.password = this.mqttModalForm.password;
        }

        const res = await fetch('/api/automations/mqtt/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const json = await res.json().catch(() => ({}));

        if (res.ok && json.status === 'success') {
          const title = this.t('js.save_mqtt_settings.mqtt_configuration');
          const msg = this.t('js.save_mqtt_settings.mqtt_settings_saved_successfully');
          this.showToast(title, msg, "success");
          this.closeMqttModal();
          await this.fetchMqttSettings();
        } else {
          const title = this.t('js.save_mqtt_settings.mqtt_error');
          const msg = json.detail || json.message || (this.t('js.save_mqtt_settings.failed_to_save_mqtt'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.save_mqtt_settings.mqtt_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.mqttSaving = false;
      }
    },

    async testMqttConnection(useModalForm = false) {
      this.mqttTesting = true;
      try {
        let payload = null;
        if (useModalForm) {
          payload = {
            broker_host: (this.mqttModalForm.broker_host || 'localhost').trim(),
            broker_port: parseInt(this.mqttModalForm.broker_port, 10) || 1883,
            username: (this.mqttModalForm.username || '').trim()
          };
          if (this.mqttModalForm.password) {
            payload.password = this.mqttModalForm.password;
          }
        }
        const res = await fetch('/api/automations/mqtt/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload ? JSON.stringify(payload) : null
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.status === 'success') {
          const title = this.t('js.test_mqtt_connection.mqtt_connection_test');
          const msg = json.message || (this.t('js.test_mqtt_connection.connection_to_broker_succeeded'));
          this.showToast(title, msg, "success");
          await this.fetchMqttSettings();
        } else {
          const title = this.t('js.test_mqtt_connection.mqtt_test_failed');
          const msg = json.detail || json.message || (this.t('js.test_mqtt_connection.could_not_connect_to'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.test_mqtt_connection.mqtt_test_error');
        this.showToast(title, err.message, "error");
      } finally {
        this.mqttTesting = false;
      }
    },

    async toggleMqttEnabled() {
      const nextState = !this.mqttSettings.enabled;
      try {
        const res = await fetch('/api/automations/mqtt/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: nextState })
        });
        const json = await res.json().catch(() => ({}));
        if (res.ok && json.status === 'success') {
          this.mqttSettings.enabled = nextState;
          const title = this.t('js.toggle_mqtt_enabled.mqtt_integration');
          const msg = nextState
            ? (this.t('js.toggle_mqtt_enabled.mqtt_enabled_and_started'))
            : (this.t('js.toggle_mqtt_enabled.mqtt_disabled'));
          this.showToast(title, msg, "info");
          await this.fetchMqttSettings();
        } else {
          const title = this.t('js.save_mqtt_settings.mqtt_error');
          this.showToast(title, json.detail || this.t('toasts.mqtt_toggle_error'), "error");
        }
      } catch (err) {
        this.showToast(this.t('js.save_mqtt_settings.mqtt_error'), err.message, "error");
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
          if (json.hour !== undefined && json.hour !== null) {
            this.digestSettings.hour = Number(json.hour);
          }
          this.digestSettings.last_sent_date = json.last_sent_date || null;
        }
      } catch (err) {
        console.error("Fetch digest settings error:", err);
      }
    },

    digestHourBadgeText() {
      const h = (this.digestSettings && this.digestSettings.hour !== undefined && this.digestSettings.hour !== null) 
        ? this.digestSettings.hour 
        : 21;
      const formatted = String(h).padStart(2, '0') + ':00';
      return this.t('js.digest_hour_badge_text.text', { formatted: formatted });
    },

    async saveDigestSettings() {
      try {
        const targetHour = (this.digestSettings.hour !== undefined && this.digestSettings.hour !== null)
          ? Number(this.digestSettings.hour)
          : 21;
        const res = await fetch('/api/automations/digest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            enabled: Boolean(this.digestSettings.enabled),
            hour: targetHour
          })
        });
        const json = await res.json();
        if (res.ok) {
          const hStr = String(targetHour).padStart(2, '0') + ':00';
          const title = this.digestSettings.enabled 
            ? (this.t('js.save_digest_settings.scheduled_digest_enabled')) 
            : (this.t('js.save_digest_settings.scheduled_digest_disabled'));
          const msg = this.digestSettings.enabled 
            ? (this.t('js.save_digest_settings.automatic_daily_report_at', { hStr: hStr })) 
            : (this.t('js.save_digest_settings.automatic_daily_report_dispatch'));
          this.showToast(title, msg, "info");
        } else {
          const title = this.t('toasts.error');
          const msg = json.detail || (this.t('js.save_digest_settings.could_not_save_setting'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('toasts.error');
        this.showToast(title, err.message, "error");
      }
    },

    async triggerDigest() {
      try {
        const res = await fetch('/api/automations/digest/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: this.currentLanguage })
        });
        const json = await res.json();
        if (res.ok && json.status === 'success') {
          const title = this.t('js.trigger_digest.digest_sent');
          const msg = json.message || (this.t('js.trigger_digest.digest_generated_and_sent'));
          this.showToast(title, msg, "success");
          await this.fetchAlerts();
        } else {
          const title = this.t('js.trigger_digest.digest_sending_error');
          const msg = json.detail || json.message || (this.t('js.trigger_digest.could_not_send_digest'));
          this.showToast(title, msg, "error");
        }
      } catch (err) {
        const title = this.t('js.trigger_digest.digest_error');
        this.showToast(title, err.message, "error");
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
          const summaryMatch = (r.summary || '').toLowerCase().includes(q);
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
          if (/^(?:https?:\/\/|mailto:|\/|#)/i.test(cleanHref)) {
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
    // MULTI-NETWORK FLEET MANAGEMENT (v1.5.0 - Issue #22)
    // =========================================================================
    formatBytes(bytes, decimals = 1) {
      if (!bytes || bytes <= 0 || isNaN(bytes)) return '0 B';
      const k = 1024;
      const dm = decimals < 0 ? 0 : decimals;
      const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      const idx = Math.min(i, sizes.length - 1);
      return parseFloat((bytes / Math.pow(k, idx)).toFixed(dm)) + ' ' + sizes[idx];
    },

    formatTrafficRate(mbps) {
      if (mbps === undefined || mbps === null || isNaN(mbps)) return '';
      const num = Number(mbps);
      if (num <= 0.05) return '';
      if (num >= 100) return Math.round(num) + 'M';
      return num.toFixed(1) + 'M';
    },

    formatSpeed(mbps) {
      return this.formatTrafficRate(mbps);
    },

    async fetchAvailableNetworks() {
      try {
        const res = await fetch('/api/network/list');
        const data = await res.json();
        if (data.status === 'success') {
          this.availableNetworks = data.networks || [];
          this.activeNetworkId = data.active_network_id || (this.network ? this.network.id : '');
        }
      } catch (err) {
        console.error('Fetch available networks error:', err);
      }
    },

    async switchActiveNetwork(networkId) {
      if (!networkId || networkId === this.activeNetworkId || this.isSwitchingNetwork) return;
      this.isSwitchingNetwork = true;
      try {
        const res = await fetch('/api/network/switch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ network_id: networkId })
        });
        const data = await res.json();
        if (data.status === 'success') {
          this.activeNetworkId = data.active_network_id;
          if (data.data) {
            this.network = data.data.network || {};
            this.eeros = data.data.eeros || [];
            this.devices = data.data.devices || [];
            this.profiles = data.data.profiles || [];
            this.healthScore = data.data.health_score || 100;
            this.healthDetails = data.data.health_details || null;
            this.lastPollTime = data.data.last_poll_time;
          }
          await this.fetchAvailableNetworks();
          await this.fetchTopHogs(this.topHogsPeriod);
          this.showToast(this.t('toasts.network_switched'), this.t('toasts.network_switched_desc', { network: networkId }), 'success');
        } else {
          this.showToast(this.t('toasts.network_switch_error'), data.detail || data.message || this.t('toasts.operation_failed'), 'error');
        }
      } catch (err) {
        console.error('Switch network error:', err);
        this.showToast(this.t('toasts.error'), String(err), 'error');
      } finally {
        this.isSwitchingNetwork = false;
      }
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
        const disposition = res.headers.get('Content-Disposition');
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
    // MODULE 3: LOCAL AUTHENTICATION & RBAC LOGIC
    // =========================================================================
    can(permKey) {
      if (!this.currentUser) {
        // Modalità Viewer / Non autenticato (Read-Only Guest Mode):
        // NESSUN permesso di tipo action_* o amministrativo è consentito se non loggati
        if (!permKey) return false;
        if (permKey.startsWith('action_')) return false;
        // Consente la consultazione in sola lettura per gli scope view_*
        return true;
      }
      if (this.currentUser.role === 'admin' || this.currentUser.is_admin) return true;
      if (Array.isArray(this.currentUser.permissions)) {
        if (this.currentUser.permissions.includes('*')) return true;
        return this.currentUser.permissions.includes(permKey);
      }
      return false;
    },

    openLocalLoginModal() {
      if (this.adminSetupRequired) {
        this.openAdminSetupModal();
        return;
      }
      this.localLoginData = {
        username: '',
        password: '',
        remember_me: false,
        error: ''
      };
      this.showLocalLoginModal = true;
    },

    openAdminSetupModal() {
      this.localSetupData = {
        username: '',
        password: '',
        passwordConfirm: '',
        remember_me: false,
        error: '',
        loading: false
      };
      this.showLocalLoginModal = false;
      this.showAdminSetupModal = true;
    },

    async checkLocalAuthSession() {
      // 1. Verifica preventiva se è necessario il Setup Iniziale Amministratore (primo avvio)
      try {
        const statusRes = await fetch('/api/auth/local/status');
        if (statusRes.ok) {
          const statusData = await statusRes.json();
          this.adminSetupRequired = !!statusData.setup_required;
          if (this.adminSetupRequired && !this.currentUser && !this.localAuthToken) {
            // Primo avvio: apri automaticamente il Setup Wizard per invitare l'admin a configurarsi
            this.showAdminSetupModal = true;
          }
        }
      } catch (e) {
        console.debug("Local auth status check error:", e);
      }

      if (!this.localAuthToken) {
        try {
          const res = await fetch('/api/auth/local/me');
          if (res.ok) {
            const data = await res.json();
            this.currentUser = data.user;
          }
        } catch (e) {}
        return;
      }
      try {
        const res = await fetch('/api/auth/local/me', {
          headers: { 'Authorization': `Bearer ${this.localAuthToken}` }
        });
        if (res.ok) {
          const data = await res.json();
          this.currentUser = data.user;
        } else {
          this.localAuthToken = null;
          if (typeof localStorage !== 'undefined') localStorage.removeItem('eero_local_auth_token');
          if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('eero_local_auth_token');
          this.currentUser = null;
        }
      } catch (e) {
        console.error("Local auth check error:", e);
      }
    },

    async performAdminSetup() {
      this.localSetupData.error = '';
      const u = (this.localSetupData.username || '').trim();
      const p = this.localSetupData.password || '';
      const pc = this.localSetupData.passwordConfirm || '';

      if (u.length < 3) {
        this.localSetupData.error = this.t('js.perform_admin_setup.username_must_be_at');
        return;
      }
      if (p.length < 6) {
        this.localSetupData.error = this.t('js.perform_admin_setup.password_must_be_at');
        return;
      }
      if (p !== pc) {
        this.localSetupData.error = this.t('js.perform_admin_setup.passwords_do_not_match');
        return;
      }

      this.localSetupData.loading = true;
      try {
        const res = await fetch('/api/auth/local/setup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: u,
            password: p,
            display_name: u.charAt(0).toUpperCase() + u.slice(1),
            remember_me: !!this.localSetupData.remember_me
          })
        });
        const data = await res.json();
        if (res.ok && data.token) {
          this.localAuthToken = data.token;
          if (this.localSetupData.remember_me) {
            if (typeof localStorage !== 'undefined') localStorage.setItem('eero_local_auth_token', data.token);
            if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('eero_local_auth_token');
          } else {
            if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('eero_local_auth_token', data.token);
            if (typeof localStorage !== 'undefined') localStorage.removeItem('eero_local_auth_token');
          }
          this.currentUser = data.user;
          this.adminSetupRequired = false;
          this.showAdminSetupModal = false;
          this.showToast(
            this.t('js.perform_admin_setup.administrator_setup_complete'),
            (this.t('js.perform_admin_setup.welcome')) + (this.currentUser.display_name || this.currentUser.username),
            'success'
          );
        } else {
          this.localSetupData.error = data.detail || (this.t('js.perform_admin_setup.setup_failed'));
        }
      } catch (err) {
        this.localSetupData.error = String(err);
      } finally {
        this.localSetupData.loading = false;
      }
    },

    async performLocalLogin() {
      this.localLoginData.error = '';
      if (!this.localLoginData.username || !this.localLoginData.password) {
        this.localLoginData.error = this.t('js.perform_local_login.username_and_password_required');
        return;
      }
      this.isLocalAuthChecking = true;
      try {
        const res = await fetch('/api/auth/local/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: this.localLoginData.username,
            password: this.localLoginData.password,
            remember_me: !!this.localLoginData.remember_me
          })
        });
        const data = await res.json();
        if (res.ok && data.token) {
          this.localAuthToken = data.token;
          if (this.localLoginData.remember_me) {
            if (typeof localStorage !== 'undefined') localStorage.setItem('eero_local_auth_token', data.token);
            if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('eero_local_auth_token');
          } else {
            if (typeof sessionStorage !== 'undefined') sessionStorage.setItem('eero_local_auth_token', data.token);
            if (typeof localStorage !== 'undefined') localStorage.removeItem('eero_local_auth_token');
          }
          this.currentUser = data.user;
          this.lastUserActivity = Date.now();
          this.showLocalLoginModal = false;
          this.localLoginData = { username: '', password: '', remember_me: false, error: '' };
          this.showToast(
            this.t('js.perform_local_login.login_successful'),
            (this.t('js.perform_admin_setup.welcome')) + (this.currentUser.display_name || this.currentUser.username),
            'success'
          );
          if (this.currentTab === 'guests') {
            await this.setTab('overview');
          } else if (this.currentTab === 'settings-users') {
            await this.loadPermissionsCatalog();
            await this.loadLocalUsers();
          }
        } else {
          this.localLoginData.error = data.detail || (this.t('js.perform_local_login.invalid_credentials'));
        }
      } catch (err) {
        this.localLoginData.error = String(err);
      } finally {
        this.isLocalAuthChecking = false;
      }
    },

    async performLocalLogout() {
      if (this.localAuthToken) {
        try {
          await fetch('/api/auth/local/logout', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${this.localAuthToken}` }
          });
        } catch (e) {}
      }
      this.localAuthToken = null;
      if (typeof localStorage !== 'undefined') localStorage.removeItem('eero_local_auth_token');
      if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('eero_local_auth_token');
      this.currentUser = null;
      await this.setTab('guests');
      this.showToast(
        this.t('js.logout.logged_out'),
        this.t('js.perform_local_logout.local_session_terminated'),
        'info'
      );
    },

    // =========================================================================
    // INACTIVITY AUTO-LOGOUT WATCHDOG & CONFIGURATION
    // =========================================================================
    initInactivityWatchdog() {
      if (this.inactivityWatchdogStarted) return;
      this.inactivityWatchdogStarted = true;
      this.lastUserActivity = Date.now();

      if (typeof window !== 'undefined' && window.addEventListener) {
        let lastThrottle = 0;
        const onActivity = () => {
          const now = Date.now();
          if (now - lastThrottle > 2000) {
            lastThrottle = now;
            this.lastUserActivity = now;
          }
        };
        ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'].forEach(evt => {
          window.addEventListener(evt, onActivity, { passive: true });
        });
      }

      setInterval(() => {
        if (!this.currentUser) return;
        const timeout = Number(this.sessionTimeoutMinutes);
        if (!timeout || timeout <= 0) return;
        const elapsedMinutes = (Date.now() - this.lastUserActivity) / (60 * 1000);
        if (elapsedMinutes >= timeout) {
          console.warn(`Auto-logout: user inactive for ${elapsedMinutes.toFixed(1)}m (timeout: ${timeout}m)`);
          this.performLocalLogout();
          this.showToast(
            this.t('js.init_inactivity_watchdog.session_expired'),
            this.t('js.init_inactivity_watchdog.automatically_logged_out_after', { timeout: timeout }),
            'warning'
          );
        }
      }, 10000);
    },

    async loadSessionTimeoutSetting() {
      try {
        const res = await fetch('/api/auth/local/session-timeout');
        if (res.ok) {
          const data = await res.json();
          if (typeof data.session_timeout_minutes !== 'undefined') {
            this.sessionTimeoutMinutes = Number(data.session_timeout_minutes);
            if (typeof localStorage !== 'undefined') {
              localStorage.setItem('eero_session_timeout', String(this.sessionTimeoutMinutes));
            }
          }
        }
      } catch (e) {
        // Fallback already loaded from localStorage
      }
    },

    async saveSessionTimeout(minutes) {
      const val = Number(minutes);
      this.sessionTimeoutMinutes = val;
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('eero_session_timeout', String(val));
      }
      this.lastUserActivity = Date.now();
      try {
        await fetch('/api/auth/local/session-timeout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(this.localAuthToken ? { 'Authorization': `Bearer ${this.localAuthToken}` } : {})
          },
          body: JSON.stringify({ minutes: val })
        });
        this.showToast(
          this.t('js.save_session_timeout.setting_saved'),
          val > 0 ? this.t('js.save_session_timeout.timeout_set', { val }) : this.t('js.save_session_timeout.auto_logout_disabled'),
          'success'
        );
      } catch (e) {
        console.error("Error saving session timeout:", e);
      }
    },

    // =========================================================================
    // MODULE 3: USERS & GRANULAR PERMISSIONS MODAL
    // =========================================================================
    async openUsersModal() {
      this.showUsersModal = true;
      this.userModalMode = 'list';
      await this.loadPermissionsCatalog();
      await this.loadLocalUsers();
    },

    async loadPermissionsCatalog() {
      try {
        const res = await fetch('/api/auth/local/permissions');
        if (res.ok) {
          const data = await res.json();
          this.permissionsCatalog = data.permissions || (data.data && data.data.permissions) || [];
        }
      } catch (e) {
        console.error("Failed to load permissions catalog:", e);
      }
    },

    async loadLocalUsers() {
      this.usersLoading = true;
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/users', { headers });
        if (res.ok) {
          const data = await res.json();
          this.localUsersList = data.users || [];
        }
      } catch (e) {
        console.error("Failed to load users:", e);
      } finally {
        this.usersLoading = false;
      }
    },

    startCreateUser() {
      if (!this.localAuthToken) {
        this.showToast(
          this.t('js.start_create_user.authentication_required'),
          this.t('js.start_create_user.log_in_as_administrator'),
          'warning'
        );
        this.openLocalLoginModal();
        return;
      }
      this.userForm = {
        id: '',
        username: '',
        display_name: '',
        role: 'operator',
        password: '',
        is_active: true,
        permissions: ['view_topology', 'view_clients', 'view_analytics', 'view_logs']
      };
      this.userModalMode = 'create';
    },

    startEditUser(u) {
      if (!this.localAuthToken) {
        this.openLocalLoginModal();
        return;
      }
      this.userForm = {
        id: u.id,
        username: u.username,
        display_name: u.display_name || '',
        role: u.role || (u.is_admin ? 'admin' : 'operator'),
        password: '',
        is_active: u.is_active !== undefined ? Boolean(u.is_active) : true,
        permissions: Array.isArray(u.permissions) ? [...u.permissions] : []
      };
      this.userModalMode = 'edit';
    },

    toggleUserPermission(permKey) {
      const idx = this.userForm.permissions.indexOf(permKey);
      if (idx > -1) {
        this.userForm.permissions.splice(idx, 1);
      } else {
        this.userForm.permissions.push(permKey);
      }
    },

    applyPermissionPreset(preset) {
      if (preset === 'all') {
        const allKeys = this.permissionsCatalog.length 
          ? this.permissionsCatalog.map(p => p.key) 
          : ['view_topology', 'view_clients', 'view_analytics', 'view_logs', 'action_reboot_nodes', 'action_pause_devices', 'action_manage_rules', 'action_sync_dns', 'action_manage_users', 'action_system_backup'];
        this.userForm.permissions = allKeys;
        this.userForm.role = 'admin';
      } else if (preset === 'readonly') {
        this.userForm.permissions = ['view_topology', 'view_clients', 'view_analytics', 'view_logs'];
        this.userForm.role = 'viewer';
      } else if (preset === 'operator') {
        this.userForm.permissions = ['view_topology', 'view_clients', 'view_analytics', 'view_logs', 'action_reboot_nodes', 'action_pause_devices', 'action_manage_rules', 'action_sync_dns'];
        this.userForm.role = 'operator';
      } else if (preset === 'none') {
        this.userForm.permissions = [];
      }
    },

    // Permission catalog for the RBAC grids: the backend catalog when loaded,
    // otherwise the known keys so the grid still renders.
    permissionsForDisplay() {
      if (this.permissionsCatalog && this.permissionsCatalog.length) return this.permissionsCatalog;
      return Object.keys(this.lookupTranslationNode('permissions') || {}).map(key => ({ key }));
    },

    permissionLabel(perm) {
      if (!perm) return '';
      return this.t(`permissions.${perm.key}`)
        || this.localized(perm, 'label')
        || perm.key;
    },

    lookupTranslationNode(key) {
      const node = (this.translations && this.translations[key]) || (this.fallbackTranslations && this.fallbackTranslations[key]);
      return (node && typeof node === 'object') ? node : null;
    },

    formatUserPermissionsCount(u) {
      if (!u) return '';
      const total = (this.permissionsCatalog && this.permissionsCatalog.length) ? this.permissionsCatalog.length : 10;
      if (u.is_admin || u.role === 'admin') {
        return this.t('js.format_user_permissions_count.all_active', { total: total });
      }
      const activeCount = (this.permissionsCatalog && this.permissionsCatalog.length)
        ? this.permissionsCatalog.filter(p => (u.permissions || []).includes(p.key)).length
        : (u.permissions ? u.permissions.length : 0);
      return `${activeCount} / ${total} ` + (this.t('js.format_user_permissions_count.active'));
    },

    async saveLocalUser() {
      if (!this.localAuthToken) {
        this.showToast(
          this.t('js.start_create_user.authentication_required'),
          this.t('js.save_local_user.log_in_as_administrator'),
          'warning'
        );
        this.openLocalLoginModal();
        return;
      }
      if (!this.userForm.username) {
        this.showToast(
          this.t('toasts.error'),
          this.t('js.save_local_user.username_is_required'),
          'warning'
        );
        return;
      }
      const headers = { 'Content-Type': 'application/json' };
      if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
      try {
        let res;
        const isAdm = this.userForm.role === 'admin';
        if (this.userModalMode === 'create') {
          res = await fetch('/api/users', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              username: this.userForm.username,
              display_name: this.userForm.display_name,
              role: this.userForm.role,
              is_admin: isAdm,
              password: this.userForm.password || 'password123',
              is_active: Boolean(this.userForm.is_active),
              permissions: this.userForm.permissions
            })
          });
        } else {
          const payload = {
            display_name: this.userForm.display_name,
            role: this.userForm.role,
            is_admin: isAdm,
            is_active: Boolean(this.userForm.is_active),
            permissions: this.userForm.permissions
          };
          if (this.userForm.password) payload.password = this.userForm.password;
          res = await fetch(`/api/users/${encodeURIComponent(this.userForm.id)}`, {
            method: 'PUT',
            headers,
            body: JSON.stringify(payload)
          });
        }
        if (res.ok) {
          this.showToast(
            this.t('toasts.success_title'),
            this.t('js.save_local_user.user_saved_successfully'),
            'success'
          );
          this.userModalMode = 'list';
          await this.loadLocalUsers();
        } else {
          const err = await res.json();
          if (res.status === 401) {
            this.localAuthToken = null;
            if (typeof localStorage !== 'undefined') localStorage.removeItem('eero_local_auth_token');
            if (typeof sessionStorage !== 'undefined') sessionStorage.removeItem('eero_local_auth_token');
            this.currentUser = null;
            this.openLocalLoginModal();
          }
          this.showToast(
            this.t('toasts.error'),
            err.detail || (this.t('js.save_local_user.operation_failed')),
            'error'
          );
        }
      } catch (e) {
        this.showToast(this.t('toasts.error'), String(e), 'error');
      }
    },

    async deleteLocalUser(userId, username) {
      if (!this.localAuthToken) {
        this.openLocalLoginModal();
        return;
      }
      const confirmMsg = this.t('js.delete_local_user.are_you_sure_you', { username: username });
      if (!confirm(confirmMsg)) return;
      const headers = {};
      if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
      try {
        const res = await fetch(`/api/users/${encodeURIComponent(userId)}`, {
          method: 'DELETE',
          headers
        });
        if (res.ok) {
          this.showToast(
            this.t('toasts.success_title'),
            this.t('js.delete_local_user.user_deleted', { username: username }),
            'success'
          );
          await this.loadLocalUsers();
        } else {
          const err = await res.json();
          this.showToast(
            this.t('toasts.error'),
            err.detail || (this.t('js.delete_local_user.failed_to_delete_user')),
            'error'
          );
        }
      } catch (e) {
        this.showToast(this.t('toasts.error'), String(e), 'error');
      }
    },

    // =========================================================================
    // MODULE 3: BACKUP & ATOMIC RESTORE LOGIC
    // =========================================================================
    openBackupModal() {
      this.showBackupModal = true;
      this.backupRestoreStatus = '';
      this.backupRestoreIsError = false;
    },

    async downloadBackup() {
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/backup/export', { headers });
        if (!res.ok) throw new Error(this.t('js.download_backup.error_during_backup_export'));
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `eero_dashboard_backup_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        this.showToast(
          this.t('js.download_backup.backup_exported'),
          this.t('js.download_backup.json_file_download_completed'),
          'success'
        );
      } catch (e) {
        this.showToast(this.t('js.download_backup.backup_error'), String(e), 'error');
      }
    },

    async uploadBackup(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.backupLoading = true;
      this.backupRestoreIsError = false;
      this.backupRestoreStatus = this.t('backup_modal.restore_in_progress');
      try {
        const text = await file.text();
        const json = JSON.parse(text);
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/backup/restore', {
          method: 'POST',
          headers,
          body: JSON.stringify(json)
        });
        const data = await res.json();
        if (res.ok) {
          this.backupRestoreStatus = this.t('js.upload_backup.configuration_restored_successfully');
          this.showToast(
            this.t('js.upload_backup.restore_completed'),
            this.t('js.upload_backup.data_restored_successfully'),
            'success'
          );
          setTimeout(() => {
            window.location.reload();
          }, 1200);
        } else {
          this.backupRestoreIsError = true;
          this.backupRestoreStatus = `${this.t('toasts.error')}: ${data.detail || (this.t('js.upload_backup.unable_to_restore_file'))}`;
          this.showToast(
            this.t('js.upload_backup.restore_error'),
            data.detail || (this.t('js.upload_backup.restore_error_2')),
            'error'
          );
        }
      } catch (e) {
        this.backupRestoreIsError = true;
        this.backupRestoreStatus = `${this.t('js.upload_backup.parsing_error')}: ${e.message}`;
        this.showToast(
          this.t('js.upload_backup.file_error'),
          this.t('js.upload_backup.selected_file_is_not'),
          'error'
        );
      } finally {
        this.backupLoading = false;
        event.target.value = '';
      }
    },

    async fetchDbStats() {
      this.dbStatsLoading = true;
      try {
        const headers = {};
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/database/stats', { headers });
        if (res.ok) {
          this.dbStats = await res.json();
        }
      } catch (err) {
        console.error("Failed to load db stats:", err);
      } finally {
        this.dbStatsLoading = false;
      }
    },

    async triggerDbCompaction() {
      this.dbCompacting = true;
      try {
        const headers = { 'Content-Type': 'application/json' };
        if (this.localAuthToken) headers['Authorization'] = `Bearer ${this.localAuthToken}`;
        const res = await fetch('/api/system/database/compact', {
          method: 'POST',
          headers
        });
        const data = await res.json();
        if (res.ok) {
          this.showToast(this.t('js.trigger_db_compaction.database_compacted'), this.t('js.trigger_db_compaction.compaction_and_optimization_completed'), 'success');
          await this.fetchDbStats();
        } else {
          this.showToast(this.t('toasts.error'), data.detail || this.t('js.trigger_db_compaction.compaction_error'), 'error');
        }
      } catch (err) {
        this.showToast(this.t('toasts.error'), String(err), 'error');
      } finally {
        this.dbCompacting = false;
      }
    },

    // =========================================================================
    // MODULE 3: PARENTAL SCHEDULING LOGIC
    // =========================================================================
    async fetchSchedules() {
      this.schedulesLoading = true;
      try {
        const res = await fetch('/api/schedules');
        if (res.ok) {
          const data = await res.json();
          const rawList = Array.isArray(data) ? data : (data.schedules || []);
          this.schedulesList = rawList.map(s => {
            const daysArr = Array.isArray(s.days) ? s.days : (Array.isArray(s.days_of_week) ? s.days_of_week : []);
            const targetId = s.target_id || (Array.isArray(s.target_ids) && s.target_ids.length ? s.target_ids[0] : '');
            const isActive = s.is_active !== undefined ? Boolean(s.is_active) : (s.enabled !== undefined ? Boolean(s.enabled) : true);
            return {
              ...s,
              days: daysArr,
              days_of_week: daysArr,
              target_id: targetId,
              is_active: isActive,
              enabled: isActive
            };
          });
        }
      } catch (e) {
        console.error("Failed to fetch schedules:", e);
      } finally {
        this.schedulesLoading = false;
      }
    },

    isRebootSchedule(item = null) {
      const obj = item || this.scheduleForm;
      if (!obj) return false;
      const tt = obj.target_type;
      const act = obj.action;
      return tt === 'node_reboot' || tt === 'all_nodes_reboot' || act === 'reboot';
    },

    openScheduleModal(s = null) {
      if (s) {
        const tid = s.target_id || (Array.isArray(s.target_ids) && s.target_ids.length ? s.target_ids[0] : '');
        const isReboot = s.target_type === 'node_reboot' || s.target_type === 'all_nodes_reboot' || s.action === 'reboot';
        this.scheduleForm = {
          id: s.id,
          name: s.name,
          days: Array.isArray(s.days) ? [...s.days] : (Array.isArray(s.days_of_week) ? [...s.days_of_week] : ['mon', 'tue', 'wed', 'thu', 'fri']),
          start_time: s.start_time || '21:00',
          end_time: isReboot ? (s.start_time || '04:00') : (s.end_time || '07:00'),
          action: s.action || 'pause',
          target_type: s.target_type || 'profile',
          target_id: tid,
          is_active: s.is_active !== undefined ? Boolean(s.is_active) : (s.enabled !== undefined ? Boolean(s.enabled) : true)
        };
        this.scheduleModalMode = 'edit';
      } else {
        const defaultProf = (this.profiles && this.profiles.length > 0) ? (this.profiles[0].id || this.profiles[0].name) : '';
        this.scheduleForm = {
          id: '',
          name: '',
          days: ['mon', 'tue', 'wed', 'thu', 'fri'],
          start_time: '21:00',
          end_time: '07:00',
          action: 'pause',
          target_type: 'profile',
          target_id: defaultProf,
          is_active: true
        };
        this.scheduleModalMode = 'create';
      }
      this.showScheduleModal = true;
    },

    onScheduleTargetTypeChange() {
      const tt = this.scheduleForm.target_type;
      if (tt === 'profile') {
        this.scheduleForm.action = 'pause';
        if (!this.scheduleForm.target_id && this.profiles && this.profiles.length > 0) {
          this.scheduleForm.target_id = this.profiles[0].id || this.profiles[0].name;
        }
      } else if (tt === 'all_profiles') {
        this.scheduleForm.action = 'pause';
        this.scheduleForm.target_id = 'all';
      } else if (tt === 'node_led') {
        this.scheduleForm.action = 'turn_off';
        if ((!this.scheduleForm.target_id || this.scheduleForm.target_id === 'all') && this.eeros && this.eeros.length > 0) {
          this.scheduleForm.target_id = this.eeros[0].id || this.eeros[0].serial;
        }
      } else if (tt === 'all_nodes_led') {
        this.scheduleForm.action = 'turn_off';
        this.scheduleForm.target_id = 'all';
      } else if (tt === 'node_reboot') {
        this.scheduleForm.action = 'reboot';
        this.scheduleForm.end_time = this.scheduleForm.start_time || '04:00';
        if ((!this.scheduleForm.target_id || this.scheduleForm.target_id === 'all') && this.eeros && this.eeros.length > 0) {
          this.scheduleForm.target_id = this.eeros[0].id || this.eeros[0].serial;
        }
      } else if (tt === 'all_nodes_reboot') {
        this.scheduleForm.action = 'reboot';
        this.scheduleForm.end_time = this.scheduleForm.start_time || '04:00';
        this.scheduleForm.target_id = 'all';
      }
    },

    getScheduleActionOptions() {
      const tt = this.scheduleForm.target_type;
      if (tt === 'node_led' || tt === 'all_nodes_led') {
        return [
          { value: 'turn_off', label: this.t('schedules.action_turn_off') },
          { value: 'turn_on', label: this.t('schedules.action_turn_on') }
        ];
      }
      if (tt === 'node_reboot' || tt === 'all_nodes_reboot') {
        return [
          { value: 'reboot', label: this.t('schedules.action_reboot') }
        ];
      }
      return [
        { value: 'pause', label: this.t('schedules.action_pause') },
        { value: 'unpause', label: this.t('schedules.action_unpause') }
      ];
    },

    formatScheduleTarget(s) {
      if (!s) return '';
      const tt = s.target_type;
      const tid = s.target_id || (Array.isArray(s.target_ids) && s.target_ids[0]) || '';
      if (tt === 'profile') {
        const prof = (this.profiles || []).find(p => String(p.id) === String(tid) || String(p.url || '').endsWith(String(tid)) || p.name === tid);
        return (this.t('js.format_schedule_target.user')) + (prof ? prof.name : tid);
      }
      if (tt === 'all_profiles') {
        return this.t('schedules.target_all_users');
      }
      if (tt === 'node_led') {
        const node = (this.eeros || []).find(e => String(e.id) === String(tid) || String(e.serial) === String(tid));
        return (this.t('js.format_schedule_target.led')) + (node ? (node.name || node.location || 'eero') : tid);
      }
      if (tt === 'all_nodes_led') {
        return this.t('js.format_schedule_target.led_all_nodes');
      }
      if (tt === 'node_reboot') {
        const node = (this.eeros || []).find(e => String(e.id) === String(tid) || String(e.serial) === String(tid));
        return (this.t('js.format_schedule_target.reboot')) + (node ? (node.name || node.location || 'eero') : tid);
      }
      if (tt === 'all_nodes_reboot') {
        return this.t('js.format_schedule_target.reboot_entire_mesh');
      }
      if (tt === 'category') {
        return (this.t('js.format_schedule_target.category')) + tid;
      }
      if (tt === 'device') {
        const dev = (this.devices || []).find(d => String(d.id) === String(tid) || String(d.mac).toLowerCase() === String(tid).toLowerCase());
        return (this.t('js.format_schedule_target.device')) + (dev ? (dev.custom_name || dev.nickname || dev.hostname || tid) : tid);
      }
      return this.t('js.format_schedule_target.entire_network');
    },

    formatScheduleAction(s) {
      if (!s) return '';
      switch (s.action) {
        case 'pause': return this.t('js.format_schedule_action.pause_connection');
        case 'unpause': return this.t('js.format_schedule_action.resume_connection');
        case 'turn_off': return this.t('js.format_schedule_action.led_off');
        case 'turn_on': return this.t('js.format_schedule_action.led_on');
        case 'reboot': return this.t('js.format_schedule_action.scheduled_reboot');
        default: return s.action;
      }
    },

    toggleScheduleDay(day) {
      const idx = this.scheduleForm.days.indexOf(day);
      if (idx > -1) {
        if (this.scheduleForm.days.length > 1) {
          this.scheduleForm.days.splice(idx, 1);
        }
      } else {
        this.scheduleForm.days.push(day);
      }
    },

    async saveSchedule() {
      if (!this.scheduleForm.name) {
        this.showToast(this.t('toasts.error'), this.t('schedules.name_required'), 'warning');
        return;
      }
      const isSpecialAll = ['all_profiles', 'all_nodes_led', 'all_nodes_reboot'].includes(this.scheduleForm.target_type);
      const tid = this.scheduleForm.target_id || (isSpecialAll ? 'all' : '');
      if (!tid && !isSpecialAll) {
        this.showToast(this.t('toasts.error'), this.t('schedules.target_required'), 'warning');
        return;
      }
      if (this.isRebootSchedule()) {
        this.scheduleForm.end_time = this.scheduleForm.start_time;
      }
      try {
        let res;
        const payload = {
          name: this.scheduleForm.name,
          days: this.scheduleForm.days,
          start_time: this.scheduleForm.start_time,
          end_time: this.scheduleForm.end_time,
          action: this.scheduleForm.action,
          target_type: this.scheduleForm.target_type,
          target_id: tid,
          target_ids: [tid],
          is_active: this.scheduleForm.is_active
        };
        if (this.scheduleModalMode === 'create') {
          res = await fetch('/api/schedules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          res = await fetch(`/api/schedules/${encodeURIComponent(this.scheduleForm.id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }
        if (res.ok) {
          this.showToast(this.t('toasts.success_title'), this.t('schedules.saved'), 'success');
          this.showScheduleModal = false;
          await this.fetchSchedules();
        } else {
          const err = await res.json();
          this.showToast(this.t('toasts.error'), err.detail || this.t('schedules.save_error'), 'error');
        }
      } catch (e) {
        this.showToast(this.t('toasts.error'), String(e), 'error');
      }
    },

    async toggleSchedule(id) {
      try {
        const res = await fetch(`/api/schedules/${encodeURIComponent(id)}/toggle`, {
          method: 'POST'
        });
        if (res.ok) {
          await this.fetchSchedules();
        }
      } catch (e) {
        console.error("Toggle schedule error:", e);
      }
    },

    async deleteSchedule(id) {
      if (!confirmthis.t('schedules.delete_confirm')) return;
      try {
        const res = await fetch(`/api/schedules/${encodeURIComponent(id)}`, {
          method: 'DELETE'
        });
        if (res.ok) {
          this.showToast(this.t('toasts.success_title'), this.t('schedules.deleted'), 'info');
          await this.fetchSchedules();
        }
      } catch (e) {
        this.showToast(this.t('toasts.error'), String(e), 'error');
      }
    },

    async evaluateSchedulesNow() {
      try {
        const res = await fetch('/api/schedules/evaluate', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          this.showToast(
            this.t('schedules.evaluated_title'),
            this.t('schedules.evaluated_desc', { evaluated: data.evaluated || 0, actions: data.actions_taken || 0 }),
            'success'
          );
        }
      } catch (e) {
        this.showToast(this.t('toasts.error'), String(e), 'error');
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
