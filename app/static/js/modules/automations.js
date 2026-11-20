/**
 * eero Custom Dashboard & Management Suite - Automations & Controls Module
 * Handles MQTT / Home Assistant telemetry, notification webhooks,
 * guest Wi-Fi provisioning, parental scheduling windows, and automated backups.
 */
function createAutomationsModule() {
  return {
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
      webhook_url: '',
      discord_enabled: false,
      discord_webhook_url: '',
      pushover_enabled: false,
      pushover_user_key: '',
      pushover_api_token: '',
      ntfy_enabled: false,
      ntfy_url: 'https://ntfy.sh',
      ntfy_topic: '',
      ntfy_token: ''
    },

    digestSettings: {
      enabled: true,
      hour: 21,
      last_sent_date: null
    },

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
      live_interval: 0,
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
      publish_interval: 60,
      live_interval: 0
    },
    showMqttModal: false,
    mqttTesting: false,
    mqttSaving: false,
    showMqttPassword: false,
    
    alertsList: [],

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
        const res = await fetch('/api/automations/focus-mode', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ active: targetState })
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(json.detail || json.message || `HTTP ${res.status}`);
        }
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
        const res = await fetch('/api/automations/night-mode', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
        const res = await fetch('/api/automations/night-mode', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(this.nightMode)
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.message || `HTTP ${res.status}`);
        }
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
        const res = await fetch('/api/automations/notifications', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
        const json = await res.json();
        if (json.status === 'success') {
          this.notificationSettings = {
            ...this.notificationSettings,
            ...json
          };
        }
      } catch (err) {
        console.error("Fetch notifications settings error:", err);
      }
    },

    async saveNotificationSettings() {
      try {
        const res = await fetch('/api/automations/notifications', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            ...this.notificationSettings,
            language: this.currentLanguage
          })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.message || `HTTP ${res.status}`);
        }
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ language: this.currentLanguage })
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(json.detail || json.message || `HTTP ${res.status}`);
        }
        const title = this.t('js.test_notifications.test_sent');
        const okLabel = this.t('js.test_notifications.status_ok');
        const noLabel = this.t('js.test_notifications.status_no');
        const parts = [
          `Telegram: ${json.telegram_sent ? okLabel : noLabel}`,
          `Webhook: ${json.webhook_sent ? okLabel : noLabel}`,
          `Discord: ${json.discord_sent ? okLabel : noLabel}`,
          `Pushover: ${json.pushover_sent ? okLabel : noLabel}`,
          `Ntfy: ${json.ntfy_sent ? okLabel : noLabel}`
        ];
        this.showToast(title, parts.join(' | '), 'info');
      } catch (err) {
        const title = this.t('js.test_notifications.test_error');
        this.showToast(title, err.message, "error");
      }
    },

// =========================================================================
    // MQTT & HOME ASSISTANT GATEWAY (v1.6.1 - Modulo 2)
    // =========================================================================
    async fetchMqttSettings() {
      try {
        const res = await fetch('/api/automations/mqtt/config', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
        publish_interval: this.mqttSettings.publish_interval || 60,
        live_interval: Number(this.mqttSettings.live_interval || 0)
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
          publish_interval: parseInt(this.mqttModalForm.publish_interval, 10) || 60,
          live_interval: Math.max(0, parseInt(this.mqttModalForm.live_interval, 10) || 0)
        };
        if (this.mqttModalForm.password) {
          payload.password = this.mqttModalForm.password;
        }

        const res = await fetch('/api/automations/mqtt/config', {
          method: 'POST',
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
        const res = await fetch('/api/automations/alerts', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
        const res = await fetch('/api/automations/digest', {
          headers: this.getAuthHeaders()
        });
        if (!res.ok) return;
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
          headers: this.getAuthHeaders({ 'Content-Type': 'application/json' }),
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
    }
  };
}

if (typeof window !== 'undefined') {
  window.createAutomationsModule = createAutomationsModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createAutomationsModule };
}
