/**
 * eero Custom Dashboard & Management Suite - Devices Module
 * Handles device table/card views, real-time filtering, column preferences,
 * sorting, device detail modal, IP conflicts, and cloud profiles.
 */
function createDevicesModule() {
  return {
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
      if (c === 'other' || c === 'altro') {
        return 'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z';
      }
      return 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z';
    },

devices: [],

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

    // Table Column Customization State (v1.6.1 - Issue #60),

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

    // Devices view mode: 'list' (table, default) or 'cards'. Per-browser preference, not part of the URL filters.,

deviceViewMode: (() => {
      try {
        if (typeof localStorage !== 'undefined' && localStorage.getItem('eero_device_view') === 'cards') return 'cards';
      } catch (e) {}
      return 'list';
    })(),

    setDeviceViewMode(mode) {
      this.deviceViewMode = mode === 'cards' ? 'cards' : 'list';
      try {
        if (typeof localStorage !== 'undefined') localStorage.setItem('eero_device_view', this.deviceViewMode);
      } catch (e) {}
    },

    // Dashboard view mode: 'advanced' (default) or 'simple' (streamlined for basic users),

dashboardViewMode: (() => {
      try {
        if (typeof localStorage !== 'undefined') {
          const m = localStorage.getItem('eero_dashboard_view_mode');
          if (m === 'simple' || m === 'advanced') return m;
        }
      } catch (e) {}
      return 'advanced';
    })(),
    simpleDeviceFilter: 'all',
    simpleDeviceSearch: '',
    simpleDeviceLimit: 12,

    setDashboardViewMode(mode) {
      this.dashboardViewMode = mode === 'simple' ? 'simple' : 'advanced';
      try {
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('eero_dashboard_view_mode', this.dashboardViewMode);
        }
      } catch (e) {}
    },

    simpleFilteredDevices() {
      if (!this.devices || !Array.isArray(this.devices)) return [];
      let list = [...this.devices];
      if (this.simpleDeviceFilter === 'online') {
        list = list.filter(d => Boolean(d.connected));
      } else if (this.simpleDeviceFilter === 'offline') {
        list = list.filter(d => !d.connected);
      }
      if (this.simpleDeviceSearch && this.simpleDeviceSearch.trim()) {
        const q = this.simpleDeviceSearch.trim().toLowerCase();
        list = list.filter(d => {
          const name = (d.nickname || d.hostname || d.ip || d.mac || '').toLowerCase();
          const cat = (d.category || '').toLowerCase();
          return name.includes(q) || cat.includes(q);
        });
      }
      list.sort((a, b) => {
        if (Boolean(a.connected) !== Boolean(b.connected)) {
          return a.connected ? -1 : 1;
        }
        const na = (a.nickname || a.hostname || a.ip || a.mac || '').toLowerCase();
        const nb = (b.nickname || b.hostname || b.ip || b.mac || '').toLowerCase();
        return na.localeCompare(nb);
      });
      return list;
    },

    // 0 = idle/offline, 1 = trickle (<1 Mbps), 2 = active (<25 Mbps), 3 = heavy. Drives the card glow and flow animations.
    deviceActivityLevel(dev) {
      if (!dev || !dev.connected || dev.paused || dev.is_paused) return 0;
      const rate = Math.max(Number(dev.download_rate_mbps) || 0, Number(dev.upload_rate_mbps) || 0);
      if (rate <= 0.05) return 0;
      if (rate < 1) return 1;
      return rate < 25 ? 2 : 3;
    },

    // Log-scaled 0-100 so a 2 Mbps stream and a 500 Mbps transfer both register on the activity bar.
    deviceRatePercent(mbps) {
      const n = Number(mbps) || 0;
      if (n <= 0.05) return 0;
      return Math.max(4, Math.min(100, Math.round(Math.log10(1 + n) / Math.log10(1001) * 100)));
    },

    deviceRateLabel(mbps) {
      const n = Number(mbps) || 0;
      if (n <= 0.05) return '0 Mbps';
      return (n >= 100 ? Math.round(n) : n.toFixed(1)) + ' Mbps';
    },

    deviceSignalBars(dev) {
      if (dev.signal_bars) return dev.signal_bars;
      const rssi = Number(dev.signal_rssi);
      if (!rssi) return 0;
      return rssi >= -50 ? 5 : rssi >= -60 ? 4 : rssi >= -67 ? 3 : rssi >= -75 ? 2 : 1;
    },

    // Device types offered in the details modal. Category and icon are one choice: picking a type sets both,
    // so the icon shown on cards and rows always matches the category (the icon value is resolved by getDeviceIconPath()).,

deviceTypeOptions: [
      { category: 'Computer', icon: 'laptop', labelKey: 'devices.cat_computer' },
      { category: 'Mobile', icon: 'smartphone', labelKey: 'devices.cat_mobile' },
      { category: 'Smart Home', icon: 'iot', labelKey: 'devices.cat_smarthome' },
      { category: 'Intrattenimento', icon: 'tv', labelKey: 'devices.cat_entertainment' },
      { category: 'Gaming', icon: 'gamepad', labelKey: 'devices.cat_gaming' },
      { category: 'Server/Rete', icon: 'server', labelKey: 'devices.cat_server' },
      // 'Altro' means "no override" in the poller: eero's detected category and icon are used, so this is the reset option
      { category: 'Altro', icon: 'other', pickIcon: 'device', labelKey: 'device_modal.type_auto' }
    ],

    // The standard types, plus the device's current category when it is not one of them (e.g. a category from eero).
    deviceTypeOptionsForForm() {
      const opts = this.deviceTypeOptions.map(o => ({ category: o.category, icon: o.icon, pickIcon: o.pickIcon, label: this.t(o.labelKey) }));
      const current = this.deviceMetadataForm.category;
      if (current && !opts.some(o => o.category === current)) {
        opts.push({ category: current, icon: this.deviceMetadataForm.custom_icon || current, label: this.formatCategoryName(current) });
      }
      return opts;
    },

    selectDeviceType(opt) {
      this.deviceMetadataForm.category = opt.category;
      this.deviceMetadataForm.custom_icon = opt.pickIcon || opt.icon;
    },

    deviceBandLabel(dev) {
      if (dev.wireless === false || dev.connection_type === 'wired' || ['Ethernet', 'Cablato', 'Wired'].includes(dev.frequency_band)) {
        return this.t('common.ethernet');
      }
      if (dev.frequency_band) return dev.frequency_band;
      if (dev.wireless_band) return dev.wireless_band;
      if (dev.channel && dev.channel <= 14) return '2.4 GHz';
      return dev.channel && dev.channel > 177 ? '6 GHz' : '5 GHz';
    },

    /**
     * Sizes the Devices table "Device / Host" and "Profile / User" columns to the widest
     * device name (+ badges) and profile name on screen, so neither wraps or clips. Profile
     * is capped at 16rem; Device / Host absorbs whatever space is left. If both do not fit
     * next to the other columns, those are scaled down together (never below 85%), then
     * Profile gives way (never below 7.5rem) so the device name keeps priority. Re-run whenever the device list, the visible
     * columns, the language or the panel width changes.
     */
    fitDeviceNameColumn() {
      const scroll = document.querySelector('.device-table-scroll');
      const table = scroll ? scroll.querySelector('table.device-table') : null;
      if (!table || !scroll.clientWidth) return;
      const nameTh = table.querySelector('th.device-col-name');
      const profileTh = table.querySelector('th.device-col-profile');
      const profileVisible = !!profileTh && profileTh.offsetParent !== null;
      const cells = table.querySelectorAll('td.device-name-cell .device-identity');
      const profiles = profileVisible ? table.querySelectorAll('td.device-profile-cell .device-profile') : [];
      if (!nameTh || !cells.length) {
        ['--device-col-name-w', '--device-col-profile-w', '--device-col-squeeze'].forEach((v) => table.style.removeProperty(v));
        return;
      }
      // Measure each block unwrapped, in a hidden probe that inherits the table styles.
      const probe = document.createElement('div');
      probe.style.cssText = 'position:absolute;left:-99999px;top:0;visibility:hidden;pointer-events:none;white-space:nowrap;width:max-content;';
      const nameProbe = document.createElement('div');
      const profileProbe = document.createElement('div');
      probe.append(nameProbe, profileProbe);
      cells.forEach((el) => {
        const clone = el.cloneNode(true);
        clone.style.width = 'max-content';
        // Only the name row (icon + name + badges) must fit on one line; the category /
        // first-seen details row may still wrap underneath it.
        clone.querySelectorAll('div').forEach((n) => { if (n.className.includes('text-[11px]')) n.remove(); });
        clone.querySelectorAll('.flex-wrap').forEach((n) => n.classList.remove('flex-wrap'));
        clone.querySelectorAll('.truncate').forEach((n) => n.classList.remove('truncate'));
        clone.querySelectorAll('.device-name').forEach((n) => {
          n.style.display = 'block';
          n.style.maxWidth = 'none';
          n.style.whiteSpace = 'nowrap';
          n.style.webkitLineClamp = 'unset';
        });
        nameProbe.appendChild(clone);
      });
      profiles.forEach((el) => {
        const clone = el.cloneNode(true);
        clone.style.maxWidth = 'none';
        clone.style.width = 'max-content';
        clone.querySelectorAll('.truncate').forEach((n) => n.classList.remove('truncate'));
        profileProbe.appendChild(clone);
      });
      table.appendChild(probe);
      let widest = 0;
      nameProbe.childNodes.forEach((c) => { widest = Math.max(widest, c.scrollWidth); });
      let widestProfile = 0;
      profileProbe.childNodes.forEach((c) => { widestProfile = Math.max(widestProfile, c.scrollWidth); });
      probe.remove();
      const pad = (th) => {
        const c = getComputedStyle(th);
        return parseFloat(c.paddingLeft) + parseFloat(c.paddingRight) + 2;
      };
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      const wanted = Math.ceil(widest + pad(nameTh));
      // Profile keeps at least the old minimum (7.5rem) and is capped so one very long
      // name cannot starve the rest of the table (it then truncates with a tooltip).
      const profileWanted = profileVisible
        ? Math.min(16 * rem, Math.max(7.5 * rem, Math.ceil(widestProfile + pad(profileTh))))
        : 0;
      // Natural width of the other visible columns (measured unsqueezed). Status and
      // Actions are pinned at a fixed width and never scaled, so track them apart.
      table.style.setProperty('--device-col-squeeze', '1');
      table.style.removeProperty('--device-col-profile-w');
      let flexible = 0;
      let fixed = 0;
      table.querySelectorAll('thead th').forEach((th) => {
        if (th === nameTh || th === profileTh || th.offsetParent === null) return;
        const w = th.getBoundingClientRect().width;
        if (th.classList.contains('device-col-status') || th.classList.contains('device-col-actions')) fixed += w;
        else flexible += w;
      });
      // The table never gets narrower than its CSS min-width (the panel scrolls instead).
      const available = Math.max(scroll.clientWidth, parseFloat(getComputedStyle(table).minWidth) || 0);
      const profileMin = profileVisible ? Math.min(profileWanted, 7.5 * rem) : 0;
      let squeeze = 1;
      let profileWidth = profileWanted;
      let nameWidth;
      if (wanted + profileWanted + flexible + fixed <= available) {
        nameWidth = Math.max(wanted, available - profileWanted - flexible - fixed); // absorb the leftover, as before
      } else {
        // Over budget: squeeze the other columns first (floor 85%), then let Profile give way
        // (floor 7.5rem) so the device name keeps priority.
        squeeze = flexible > 0 ? Math.max(0.85, (available - wanted - profileWanted - fixed) / flexible) : 1;
        const room = available - fixed - flexible * squeeze;
        profileWidth = Math.max(profileMin, Math.min(profileWanted, room - wanted));
        nameWidth = Math.max(10 * rem, room - profileWidth);
      }
      table.style.setProperty('--device-col-squeeze', String(Number(squeeze.toFixed(3))));
      table.style.setProperty('--device-col-name-w', Math.floor(nameWidth) + 'px');
      if (profileVisible) table.style.setProperty('--device-col-profile-w', Math.floor(profileWidth) + 'px');
    },

    isTableColumnVisible(colKey) {
      if (colKey === 'name' || colKey === 'actions') return true;
      return this.deviceTableColumns[colKey] !== false;
    },

    getActiveColumnsCount() {
      const keys = ['address', 'profile', 'node', 'band', 'signal', 'traffic', 'status', 'first_seen'];
      return keys.filter(k => this.deviceTableColumns[k]).length;
    },

// Profiles & Cloud Users State
    profiles: [],
    showCreateProfileModal: false,
    newProfileForm: {
      name: '',
      selectedDeviceIds: []
    },
    deviceSelectedProfileId: '',
    profileChangeStatus: { state: '', message: '' },
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
      dns_sync_excluded: false,
      is_echo_builtin: false
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

loadDeviceFiltersFromUrl() {
      if (typeof window === 'undefined' || !window.location) return;
      const params = new URLSearchParams(window.location.search);
      // Missing params mean "no filter": restore the neutral defaults, not null
      // (null would make every device fail the category/profile comparisons).
      this.deviceSearchQuery = params.get('search') || '';
      this.selectedBandFilter = params.get('band') || 'all';
      this.selectedNodeFilter = params.get('node') || 'all';
      this.selectedCategoryFilter = params.get('category') || 'all';
      this.selectedProfileFilter = params.get('profile') || 'all';
      this.selectedIpTypeFilter = params.get('assignment') || 'all';
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

    // Dashboard shortcut: open Devices showing only connected clients,
    // optionally narrowed to one mesh node. Other filters are cleared so
    // the list matches the count the user clicked on.,

syncDeviceFiltersToUrl() {
      if (this.currentTab !== 'devices' || typeof window === 'undefined' || !window.location) return;
      const url = this.deviceFiltersUrl();
      if (`${window.location.pathname}${window.location.search}` !== url) {
        window.history.replaceState({}, '', url);
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
          const vendor = [d.manufacturer, d.model_name, d.reported_hostname].filter(Boolean).join(' ').toLowerCase();
          return vendor.includes(q) || name.includes(q) || ip.includes(q) || mac.includes(q) || notes.includes(q) || cat.includes(q) || prof.includes(q) || ipv6.includes(q) || ipv6List.includes(q);
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
            const dlA = Number(a.download_bytes ?? a.tx_bytes ?? 0);
            const dlB = Number(b.download_bytes ?? b.tx_bytes ?? 0);
            res = dlA - dlB;
            if (res === 0) {
              const nameA = (a.custom_name || a.nickname || a.hostname || '').toLowerCase();
              const nameB = (b.custom_name || b.nickname || b.hostname || '').toLowerCase();
              res = nameA.localeCompare(nameB, this.dateLocale());
            }
            break;
          }
          case 'upload': {
            const ulA = Number(a.upload_bytes ?? a.rx_bytes ?? 0);
            const ulB = Number(b.upload_bytes ?? b.rx_bytes ?? 0);
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
        dns_sync_excluded: Boolean(device.dns_sync_excluded),
        is_echo_builtin: Boolean(device.is_echo_builtin)
      };

      this.deviceSelectedProfileId = device.profile_id || '';
      this.profileChangeStatus = { state: '', message: '' };
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
          custom_icon: this.deviceMetadataForm.custom_icon,
          custom_name: this.deviceMetadataForm.custom_name,
          category: this.deviceMetadataForm.category,
          custom_notes: this.deviceMetadataForm.custom_notes,
          is_favorite: Boolean(this.deviceMetadataForm.is_favorite),
          is_low_latency_target: Boolean(this.deviceMetadataForm.is_low_latency_target),
          dns_sync_excluded: Boolean(this.deviceMetadataForm.dns_sync_excluded),
          is_echo_builtin: Boolean(this.deviceMetadataForm.is_echo_builtin)
        });

        const title = this.t('toasts.saved');
        const msg = this.t('js.save_device_metadata.device_metadata_and_category');
        this.showToast(title, msg, "success");
        this.showDeviceModal = false;
        await this.fetchDevices();
        // Reload the overview too: it carries `eeros`, so the Mesh Topology picks up
        // an eero Built-in toggle right away instead of on the next poll (#135).
        await this.fetchOverview();
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

    // Profile is an eero cloud assignment, so it applies as soon as it is picked (like the static IP actions)
    // and reports the outcome inline in the details modal instead of waiting for "Save Changes".
    async changeDeviceProfile() {
      const dev = this.selectedDevice;
      if (!dev) return;
      const newId = this.deviceSelectedProfileId || '';
      const oldId = dev.profile_id || '';
      if (newId === oldId) return;
      const target = (this.profiles || []).find(p => p.id === newId);
      this.profileChangeStatus = { state: 'saving', message: this.t('device_modal.profile_saving') };
      try {
        const key = encodeURIComponent((dev.mac || dev.mac_address || dev.id || '').toLowerCase());
        const res = await fetch(`/api/devices/${key}/profile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile_id: newId || null })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status === 'error') {
          throw new Error(data.detail || data.message || `HTTP ${res.status}`);
        }
        dev.profile_id = newId || null;
        dev.profile_name = target ? target.name : null;
        this.profileChangeStatus = {
          state: 'success',
          message: target
            ? this.t('device_modal.profile_changed', { name: target.name })
            : this.t('device_modal.profile_removed')
        };
        await Promise.all([this.fetchProfiles(), this.fetchDevices()]);
      } catch (err) {
        this.deviceSelectedProfileId = oldId;
        this.profileChangeStatus = { state: 'error', message: this.t('device_modal.profile_error', { error: err.message }) };
      }
    },

    async removeDeviceFromProfile(deviceMacOrId) {
      await this.assignDeviceToProfile(deviceMacOrId, null);
    }
  };
}

if (typeof window !== 'undefined') {
  window.createDevicesModule = createDevicesModule;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { createDevicesModule };
}
