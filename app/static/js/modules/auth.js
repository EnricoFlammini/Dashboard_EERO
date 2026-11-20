/**
 * eero Custom Dashboard & Management Suite - Authentication & RBAC Module
 * Handles local authentication, granular RBAC permissions, user management,
 * session timeouts and Amazon/eero cloud authentication flows.
 */
function createAuthModule() {
  return {
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
    // v1.7.0: AMAZON OAUTH2, IPV6 FIREWALL, PLACEMENT TEST, GUARDIAN VPN & AI ASSISTANT
    // =========================================================================
    showAmazonCallbackInput: false,
    amazonCallbackCode: '',
    ipv6FirewallRules: [],
    ipv6RuleForm: {
      device_name: '',
      mac: '',
      protocol: 'tcp',
      ports: ''
    },
    placementTestLoading: false,
    placementTestResult: null,
    guardianVpnLoading: false,
    guardianVpn: {
      supported: false,
      enabled: false,
      provider: 'Guardian (eero Plus)',
      details: null
    },

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
      if (this.currentUser && !this.can('action_toggle_demo')) {
        this.showToast(this.t('toasts.error'), this.t('auth_local.no_access'), 'error');
        return;
      }
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
        } else {
          this.showToast(this.t('toasts.error'), data.detail || this.t('toasts.operation_failed'), 'error');
        }
      } catch (err) {
        console.error("Failed to toggle demo mode:", err);
        this.showToast(this.t('toasts.error'), String(err), 'error');
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

    async startAmazonOAuth() {
      this.authLoading = true;
      try {
        const res = await fetch('/api/auth/amazon/login-url');
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Amazon OAuth initialization failed');
        this.showAmazonCallbackInput = true;
        if (data.login_url && typeof window !== 'undefined') {
          window.open(data.login_url, '_blank', 'noopener,noreferrer');
        }
        this.showToast(this.t('auth.amazon_login_btn'), this.t('auth.amazon_callback_label'), 'info');
      } catch (err) {
        this.showToast(this.t('js.request_otp.login_error'), err.message, 'error');
      } finally {
        this.authLoading = false;
      }
    },

    async submitAmazonOAuthExchange() {
      if (!this.amazonCallbackCode) return;
      this.authLoading = true;
      try {
        const res = await fetch('/api/auth/amazon/exchange', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code_or_url: this.amazonCallbackCode })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Amazon OAuth exchange failed');
        this.isAuthenticated = true;
        this.isDemoMode = false;
        this.hasSavedLiveToken = true;
        this.showAmazonCallbackInput = false;
        this.amazonCallbackCode = '';
        await this.checkAuthStatus();
        this.showToast(this.t('js.verify_otp.login_successful'), this.t('js.verify_otp.connected_to_eero_mesh'), 'success');
        await this.refreshAllData();
        this.startPolling();
      } catch (err) {
        this.showToast(this.t('js.request_otp.login_error'), err.message, 'error');
      } finally {
        this.authLoading = false;
      }
    },

    getAuthHeaders(customHeaders = {}) {
      const headers = { ...customHeaders };
      if (this.localAuthToken) {
        headers['Authorization'] = `Bearer ${this.localAuthToken}`;
      }
      return headers;
    },

    async fetchIpv6FirewallRules() {
      try {
        const res = await fetch('/api/network/ipv6-firewall', {
          headers: this.getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          this.ipv6FirewallRules = data.rules || [];
        }
      } catch (e) {
        console.warn('Could not load IPv6 firewall rules:', e);
      }
    },

    async addIpv6FirewallRule() {
      if (!this.ipv6RuleForm.ports) return;
      try {
        const res = await fetch('/api/network/ipv6-firewall', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(this.ipv6RuleForm)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error');
        this.ipv6RuleForm = { device_name: '', mac: '', protocol: 'tcp', ports: '' };
        await this.fetchIpv6FirewallRules();
        this.showToast(this.t('controls.ipv6_fw_title'), this.t('controls.ipv6_fw_saved'), 'success');
      } catch (err) {
        this.showToast(this.t('controls.ipv6_fw_title'), err.message, 'error');
      }
    },

    async deleteIpv6FirewallRule(ruleId) {
      try {
        const res = await fetch(`/api/network/ipv6-firewall/${encodeURIComponent(ruleId)}`, {
          method: 'DELETE',
          headers: this.getAuthHeaders()
        });
        if (res.ok) {
          await this.fetchIpv6FirewallRules();
        }
      } catch (e) {
        console.warn('Delete IPv6 firewall rule failed:', e);
      }
    },

    async runPlacementTest() {
      this.placementTestLoading = true;
      try {
        const res = await fetch('/api/network/placement-test', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ location: 'Mesh Assessment' })
        });
        const data = await res.json();
        if (res.ok) {
          this.placementTestResult = data;
          const score = data.score ?? 0;
          const rating = (data.rating || 'optimal').toUpperCase();
          this.showToast(this.t('controls.placement_test_title'), `${this.t('controls.placement_test_success')} (${score}/100 - ${rating})`, 'success');
        } else {
          throw new Error(data.detail || this.t('controls.placement_test_error'));
        }
      } catch (e) {
        console.warn('Placement test error:', e);
        this.showToast(this.t('controls.placement_test_title'), e.message || this.t('controls.placement_test_error'), 'error');
      } finally {
        this.placementTestLoading = false;
      }
    },

    async fetchGuardianVpn() {
      try {
        const res = await fetch('/api/network/guardian-vpn', {
          headers: this.getAuthHeaders()
        });
        if (res.ok) {
          const data = await res.json();
          this.guardianVpn = {
            supported: Boolean(data.supported),
            enabled: Boolean(data.enabled),
            provider: data.provider || 'Guardian (eero Plus)',
            details: data.details || null
          };
        }
      } catch (e) {
        console.warn('Guardian VPN status error:', e);
      }
    },

    async toggleGuardianVpn() {
      if (this.guardianVpnLoading) return;
      this.guardianVpnLoading = true;
      const targetState = Boolean(this.guardianVpn.enabled);
      try {
        const res = await fetch('/api/network/guardian-vpn', {
          method: 'PUT',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ enabled: targetState })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || `HTTP ${res.status}`);
        }
        const msg = targetState 
          ? this.t('controls.guardian_vpn_enabled_msg')
          : this.t('controls.guardian_vpn_disabled_msg');
        this.showToast(this.t('controls.guardian_vpn_title'), msg, 'success');
      } catch (e) {
        // Ripristina lo stato del toggle in caso di errore
        this.guardianVpn.enabled = !targetState;
        console.warn('Toggle Guardian VPN failed:', e);
        this.showToast(this.t('controls.guardian_vpn_title'), e.message || this.t('toasts.operation_failed'), 'error');
      } finally {
        this.guardianVpnLoading = false;
      }
    },

    async registerEeroNodeBySerial() {
      if (!this.serialClaimForm.serial) return;
      try {
        const res = await fetch('/api/network/eeros/register', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            serial: this.serialClaimForm.serial,
            location: this.serialClaimForm.location || 'Living Room'
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error');
        this.serialClaimForm = { serial: '', location: '' };
        await this.fetchOverview();
        this.showToast(this.t('controls.serial_claim_title'), this.t('controls.serial_claim_success'), 'success');
      } catch (err) {
        this.showToast(this.t('controls.serial_claim_title'), err.message, 'error');
      }
    },

    async askNetworkAssistant() {
      if (!this.assistantPrompt) return;
      this.assistantLoading = true;
      this.assistantReply = '';
      try {
        const res = await fetch('/api/network/assistant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: this.assistantPrompt, stream: false })
        });
        const data = await res.json();
        if (res.ok) {
          this.assistantReply = data.reply || '';
        }
      } catch (e) {
        console.warn('Assistant error:', e);
      } finally {
        this.assistantLoading = false;
      }
    },

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
            if (this.currentUser && this.currentUser.role === 'viewer' && typeof localStorage !== 'undefined' && !localStorage.getItem('eero_dashboard_view_mode')) {
              this.dashboardViewMode = 'simple';
            }
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
          if (this.currentUser && this.currentUser.role === 'viewer' && typeof localStorage !== 'undefined' && !localStorage.getItem('eero_dashboard_view_mode')) {
            this.dashboardViewMode = 'simple';
          }
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
          if (this.currentUser && this.currentUser.role === 'viewer' && typeof localStorage !== 'undefined' && !localStorage.getItem('eero_dashboard_view_mode')) {
            this.dashboardViewMode = 'simple';
          }
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
          : ['view_topology', 'view_clients', 'view_analytics', 'view_logs', 'action_reboot_nodes', 'action_pause_devices', 'action_manage_rules', 'action_sync_dns', 'action_manage_users', 'action_system_backup', 'action_toggle_demo', 'action_change_language'];
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
    }
  };
}

if (typeof window !== 'undefined') {
  window.createAuthModule = createAuthModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createAuthModule };
}
