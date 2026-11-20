/**
 * eero Custom Dashboard & Management Suite - DNS Module
 * Handles multi-engine DNS synchronization (AdGuard Home, Pi-hole, Technitium),
 * local hostname resolution, and DNS client mapping.
 */
function createDnsModule() {
  return {
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
        const res = await fetch('/api/automations/dns', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
              saved_url: this.normalizeDnsUrl(i.url),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
        const res = await fetch('/api/automations/adguard', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
    }
  };
}

if (typeof window !== 'undefined') {
  window.createDnsModule = createDnsModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createDnsModule };
}
