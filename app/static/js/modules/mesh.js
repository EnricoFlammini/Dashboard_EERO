/**
 * eero Custom Dashboard & Management Suite - Mesh & Network Module
 * Handles mesh node topology, reboot actions, public WAN IP resolution,
 * node placement diagnostics, and multi-network fleet management.
 */
function createMeshModule() {
  return {
network: {},
    // Public WAN IP & double-NAT detection (Issue #115)
    publicIpInfo: null,
    publicIpFetchedAt: 0,
    eeros: [],

availableNetworks: [],
    activeNetworkId: '',
    isSwitchingNetwork: false,
    get noNetworksFound() {
      return Boolean(this.isAuthenticated && !this.isDemoMode && this.authChecked && Array.isArray(this.availableNetworks) && this.availableNetworks.length === 0);
    },

    // Device Data Usage Insights State (v1.5.0),

serialClaimForm: {
      serial: '',
      location: ''
    },
    assistantPrompt: '',
    assistantReply: '',
    assistantLoading: false,
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

getEeroProductImage(node) {
      if (!node || node.is_echo_node) return null;
      const codes = {
        A01: 'eero-gen1',
        B01: 'eero-pro',
        D01: 'eero-beacon',
        J01: 'eero-gen2',
        K01: 'eero-pro-6',
        N01: 'eero-6',
        Q01: 'eero-6-extender',
        R01: 'eero-6-plus',
        S01: 'eero-pro-6e',
        T01: 'eero-poe-6',
        U01: 'eero-poe-gateway',
        V01: 'eero-max-7',
        PA1: 'eero-7',
        ME1: 'eero-pro-7',
        SN1: 'eero-outdoor-7',
        NV01: 'eero-poe-7',
        RG4: 'eero-signal-4g',
        RG5: 'eero-signal-5g',
        FH01: 'eero-telephone-adapter'
      };
      const names = {
        eeromax7: 'eero-max-7',
        eeropro7: 'eero-pro-7',
        eero7: 'eero-7',
        eerooutdoor7: 'eero-outdoor-7',
        eeropoe7: 'eero-poe-7',
        eeropoe6: 'eero-poe-6',
        eeropoegateway: 'eero-poe-gateway',
        eeropro6e: 'eero-pro-6e',
        eeropro6: 'eero-pro-6',
        'eero6+': 'eero-6-plus',
        eero6plus: 'eero-6-plus',
        'eero6+extender': 'eero-6-plus-extender',
        eero6plusextender: 'eero-6-plus-extender',
        eero6extender: 'eero-6-extender',
        eero6: 'eero-6',
        eerobeacon: 'eero-beacon',
        eeropro: 'eero-pro',
        eeropro2ndgen: 'eero-pro',
        eero1stgen: 'eero-gen1',
        eero1stgeneration: 'eero-gen1',
        eero2ndgen: 'eero-gen2',
        eero2ndgeneration: 'eero-gen2',
        eerosignal4glte: 'eero-signal-4g',
        eerosignal4g: 'eero-signal-4g',
        eerosignal5g: 'eero-signal-5g',
        eerotelephoneadapter: 'eero-telephone-adapter',
        eerofh01: 'eero-telephone-adapter'
      };

      const rawCode = String(node.model_number || node.model_code || node.hardware_model || '').replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
      if (rawCode) {
        for (const [prefix, img] of Object.entries(codes)) {
          if (rawCode.startsWith(prefix) && rawCode.length >= prefix.length + (prefix.length === 4 ? 0 : 1)) {
            return `/static/img/products/${img}.png`;
          }
        }
      }

      const rawModel = String(node.model || node.model_name || node.product_name || '');
      const baseModel = rawModel.replace(/\([^)]*\)/g, '').replace(/[\s_()\-]/g, '').toLowerCase();
      if (names[baseModel]) {
        return `/static/img/products/${names[baseModel]}.png`;
      }
      const fullModel = rawModel.replace(/[\s_()\-]/g, '').toLowerCase();
      if (names[fullModel]) {
        return `/static/img/products/${names[fullModel]}.png`;
      }

      const modelAsCode = rawModel.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
      if (/^[A-Z]{1,2}[0-9][A-Z0-9]{1,6}$/.test(modelAsCode)) {
        for (const [prefix, img] of Object.entries(codes)) {
          if (modelAsCode.startsWith(prefix) && modelAsCode.length >= prefix.length + (prefix.length === 4 ? 0 : 1)) {
            return `/static/img/products/${img}.png`;
          }
        }
      }
      return null;
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
        // "Ethernet (Wired)" from the API (or "Ethernet (Cablato)" in older cached data) carries no speed: localize the label.
        if (/\((?:wired|cablato)\)/i.test(bh)) return this.t('dashboard.backhaul_wired');
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

async openConnectedDevices(nodeId = 'all') {
      this.deviceSearchQuery = '';
      this.selectedBandFilter = 'all';
      this.selectedNodeFilter = nodeId || 'all';
      this.selectedCategoryFilter = 'all';
      this.selectedProfileFilter = 'all';
      this.selectedIpTypeFilter = 'all';
      this.showConnectedOnly = true;
      await this.setTab('devices');
    },

async fetchPublicIp() {
      // The server caches lookups for 30 minutes; re-ask every 5 or when eero's WAN IP changes.
      const wanChanged = this.publicIpInfo && this.publicIpInfo.eero_wan_ip !== (this.network.public_ip || null);
      if (this.publicIpInfo && !wanChanged && Date.now() - this.publicIpFetchedAt < 300000) return;
      this.publicIpFetchedAt = Date.now();
      try {
        const res = await fetch('/api/network/public-ip');
        const json = await res.json();
        if (json.status === 'success') this.publicIpInfo = json.data;
      } catch (err) {
        console.error("Fetch public IP error:", err);
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

    get gatewayNode() {
      return (this.eeros || []).find(e => e.is_gateway) || (this.eeros || [])[0] || {};
    },

    get onlineNodeCount() {
      return (this.eeros || []).filter(e => ['online', 'green'].includes(e.status)).length;
    },

    // Dashboard card: connected clients split by Wi-Fi band / wired, plus guest and new counts.
    get connectedClientSummary() {
      const connected = (this.devices || []).filter(d => d.connected);
      const bands = [
        { key: '6', label: '6 GHz', color: 'bg-violet-500', match: d => String(d.wireless_band || '').startsWith('6') },
        { key: '5', label: '5 GHz', color: 'bg-sky-500', match: d => String(d.wireless_band || '').startsWith('5') },
        { key: '2.4', label: '2.4 GHz', color: 'bg-amber-500', match: d => String(d.wireless_band || '').startsWith('2') },
        { key: 'wired', label: this.t('devices.wired_tag'), color: 'bg-emerald-500', match: d => d.connection_type === 'wired' || d.wireless === false }
      ];
      const counted = new Set();
      const segments = bands.map(b => {
        const hits = connected.filter(d => !counted.has(d) && b.match(d));
        hits.forEach(d => counted.add(d));
        return { key: b.key, label: b.label, color: b.color, count: hits.length };
      }).filter(s => s.count > 0);
      return {
        total: connected.length,
        known: (this.devices || []).length,
        guests: connected.filter(d => d.is_guest).length,
        fresh: (this.devices || []).filter(d => d.is_new).length,
        segments
      };
    },

    // Polyline points (viewBox 100x28) for the dashboard card's download trend, oldest test first.
    get speedtestSparkline() {
      const values = (this.speedtestHistory || []).slice(0, 20).reverse().map(t => Number(t.download_mbps) || 0);
      if (values.length < 2) return '';
      const max = Math.max(...values);
      const min = Math.min(...values);
      const range = max - min || 1;
      return values.map((v, i) => {
        const x = (i / (values.length - 1)) * 100;
        const y = 26 - ((v - min) / range) * 24;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
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
    }
  };
}

if (typeof window !== 'undefined') {
  window.createMeshModule = createMeshModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createMeshModule };
}
