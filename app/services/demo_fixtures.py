"""
Demo Fixtures and Simulator State for eero Dashboard.
Provides DemoFixturesMixin with mock networks (Casa Rossi, Ufficio Sviluppo),
simulated device traffic, profiles, port forwards, speedtests, and demo mutation helpers.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import random
import time
from app.i18n import tr


class DemoFixturesMixin:
    """Mixin che fornisce tutti i payload mock e le simulazioni in Demo Mode per EeroClient."""

    def _init_demo_state(self) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # 1. Rete Demo 1: Residenziale Mesh 6E (Casa Rossi)
        net1 = {
            "account": {
                "name": "Mario Rossi",
                "email": "mario.rossi@homelab.local",
                "phone": "+39 340 1234567"
            },
            "network": {
                "id": "network_demo_mesh_01",
                "name": "Casa Rossi Mesh 6E",
                "status": "online",
                "public_ip": "93.42.178.105",
                "gateway_ip": "192.168.4.1",
                "subnet_mask": "255.255.252.0",
                "dns_servers": ["1.1.1.1", "1.0.0.1"],
                "isp": "TIM FTTH 1Gbps / 300Mbps",
                "ipv6_enabled": True,
                "upnp_enabled": True,
                "band_steering_enabled": True,
                "health_score": 98,
            },
            "guest_network": {
                "enabled": True,
                "name": "Casa Rossi - Ospiti",
                "password": "OspitiSicuri2026!",
            },
            "speedtest": {
                "download_mbps": 912.45,
                "upload_mbps": 298.10,
                "ping_ms": 9.2,
                "jitter": 1.1,
                "date": now_iso,
            },
            "eeros": [
                {
                    "id": "eero_01_gateway",
                    "serial": "GW-EERO6E-001",
                    "name": "Gateway Soggiorno",
                    "model": "eero Pro 6E (K010001)",
                    "is_gateway": True,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.4.1",
                    "mac": "70:54:D2:11:22:33",
                    "os_version": "v7.5.2-192",
                    "led_on": True,
                    "backhaul_type": "Gateway (WAN)",
                    "connected_clients_count": 8,
                },
                {
                    "id": "eero_02_studio",
                    "serial": "EERO6E-002-STUDIO",
                    "name": "Studio & Server Room",
                    "model": "eero Pro 6E (K010001)",
                    "is_gateway": False,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.4.2",
                    "mac": "70:54:D2:44:55:66",
                    "os_version": "v7.5.2-192",
                    "led_on": True,
                    "backhaul_type": "Ethernet (1.0 Gbps)",
                    "connected_clients_count": 5,
                },
                {
                    "id": "eero_03_camera",
                    "serial": "EERO6E-003-BEDROOM",
                    "name": "Camera da Letto",
                    "model": "eero 6+ (R010001)",
                    "is_gateway": False,
                    "wired": False,
                    "status": "online",
                    "ip": "192.168.4.3",
                    "mac": "70:54:D2:77:88:99",
                    "os_version": "v7.5.2-192",
                    "led_on": False,
                    "backhaul_type": "Wireless Mesh (5 GHz / -52 dBm)",
                    "connected_clients_count": 4,
                },
            ],
            "devices": [
                {
                    "id": "dev_01",
                    "mac": "B4:2E:99:A1:01:10",
                    "hostname": "MacBook-Pro-M3",
                    "manufacturer": "Apple",
                    "model_name": "MacBook Pro 14-inch",
                    "last_active": "2026-11-07T09:12:00Z",
                    "is_guest": False,
                    "phy_type": "WIFI7",
                    "channel_width": "160 MHZ",
                    "nickname": "MacBook Pro Lavoro",
                    "ip": "192.168.4.101",
                    "ipv6_addresses": ["2001:db8:1a:2b::101", "2001:db8:1a:2b:89ab:cdef:1234:5678"],
                    "ipv6_link_local": ["fe80::b62e:99ff:fea1:0110"],
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "6GHz",
                    "frequency_band": "6 GHz",
                    "channel": 69,
                    "signal_rssi": -48,
                    "rx_bitrate": "2400.0 MBit/s",
                    "phy_rate": "2400.0 MBit/s",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 42.8,
                    "upload_rate_mbps": 5.2,
                    "rx_bytes": 14200500100,
                    "tx_bytes": 3890200400,
                    "paused": False,
                },
                {
                    "id": "dev_02",
                    "mac": "00:11:32:9F:88:44",
                    "hostname": "Synology-DS920Plus",
                    "nickname": "Home NAS & Media Server",
                    "ip": "192.168.4.10",
                    "ipv6_addresses": ["2001:db8:1a:2b::10"],
                    "ipv6_link_local": ["fe80::211:32ff:fe9f:8844"],
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 88.4,
                    "upload_rate_mbps": 12.1,
                    "rx_bytes": 48900200100,
                    "tx_bytes": 19400100200,
                    "paused": False,
                },
                {
                    "id": "dev_03",
                    "mac": "F4:F5:DB:33:44:55",
                    "hostname": "iPhone-15-Pro",
                    "manufacturer": "Apple",
                    "model_name": "iPhone 15 Pro",
                    "last_active": "2026-11-07T09:30:00Z",
                    "is_guest": False,
                    "phy_type": "WIFI6",
                    "channel_width": "80 MHZ",
                    "nickname": "iPhone Personale",
                    "ip": "192.168.4.110",
                    "ipv6_addresses": ["2001:db8:1a:2b:f4f5:dbff:fe33:4455"],
                    "ipv6_link_local": ["fe80::f6f5:dbff:fe33:4455"],
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 44,
                    "signal_rssi": -55,
                    "rx_bitrate": "866.0 MBit/s",
                    "phy_rate": "866.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 6.2,
                    "upload_rate_mbps": 0.8,
                    "rx_bytes": 5400200100,
                    "tx_bytes": 1200400100,
                    "paused": False,
                },
                {
                    "id": "dev_04",
                    "mac": "28:70:4E:88:99:AA",
                    "hostname": "Sony-Bravia-OLED-4K",
                    "manufacturer": "Sony",
                    "model_name": "BRAVIA XR A80L",
                    "last_active": "2026-11-06T22:05:00Z",
                    "is_guest": False,
                    "phy_type": "WIFI5",
                    "channel_width": "80 MHZ",
                    "nickname": "Smart TV OLED 65\"",
                    "ip": "192.168.4.120",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "signal_rssi": -62,
                    "rx_bitrate": "433.0 MBit/s",
                    "phy_rate": "433.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 25.4,
                    "upload_rate_mbps": 0.5,
                    "rx_bytes": 28900400100,
                    "tx_bytes": 850100200,
                    "paused": False,
                },
                {
                    "id": "dev_05",
                    "mac": "A8:5E:45:12:34:56",
                    "hostname": "PlayStation-5",
                    "nickname": "PS5 Pro Console",
                    "ip": "192.168.4.125",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 0.0,
                    "upload_rate_mbps": 0.0,
                    "rx_bytes": 19400200100,
                    "tx_bytes": 4500100200,
                    "paused": False,
                },
                {
                    "id": "dev_06",
                    "mac": "DC:A6:32:88:77:66",
                    "hostname": "HomeAssistant-Yellow",
                    "nickname": "Home Assistant Hub",
                    "ip": "192.168.4.20",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_02_studio",
                    "connected_eero_name": "Studio & Server Room",
                    "download_rate_mbps": 0.8,
                    "upload_rate_mbps": 0.4,
                    "rx_bytes": 350200100,
                    "tx_bytes": 120400100,
                    "paused": False,
                },
                {
                    "id": "dev_07",
                    "mac": "5C:02:72:11:22:33",
                    "hostname": "Shelly-Pro-4PM",
                    "manufacturer": "Allterco Robotics",
                    "model_name": "Shelly Pro 4PM",
                    "last_active": "2026-11-07T09:31:00Z",
                    "is_guest": False,
                    "phy_type": "WIFI4",
                    "channel_width": "20 MHZ",
                    "nickname": "Quadro Elettrico Domotica",
                    "ip": "192.168.4.55",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "2.4GHz",
                    "frequency_band": "2.4 GHz",
                    "channel": 6,
                    "signal_rssi": -65,
                    "rx_bitrate": "72.0 MBit/s",
                    "phy_rate": "72.0 MBit/s",
                    "connected_eero_id": "eero_03_camera",
                    "connected_eero_name": "Camera da Letto",
                    "download_rate_mbps": 0.1,
                    "upload_rate_mbps": 0.1,
                    "rx_bytes": 120400100,
                    "tx_bytes": 85020010,
                    "paused": False,
                },
                {
                    "id": "dev_08",
                    "mac": "E0:4F:43:AA:BB:CC",
                    "hostname": "Apple-iPad-Air",
                    "manufacturer": "Apple",
                    "model_name": "iPad Air",
                    "last_active": "2026-11-04T18:40:00Z",
                    "is_guest": True,
                    "phy_type": "WIFI6",
                    "channel_width": "40 MHZ",
                    "nickname": "iPad Cucina / Ricette",
                    "ip": "192.168.4.135",
                    "connected": False,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 44,
                    "signal_rssi": None,
                    "rx_bitrate": None,
                    "phy_rate": None,
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 0.0,
                    "upload_rate_mbps": 0.0,
                    "rx_bytes": 4100200100,
                    "tx_bytes": 980100200,
                    "paused": False,
                },
                {
                    "id": "dev_09",
                    "mac": "AC:BC:32:44:55:66",
                    "hostname": "Nest-Doorbell-Battery",
                    "nickname": "Videocitofono Ingresso",
                    "ip": "192.168.4.140",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "signal_rssi": -52,
                    "rx_bitrate": "150.0 MBit/s",
                    "phy_rate": "150.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 1.2,
                    "upload_rate_mbps": 2.8,
                    "rx_bytes": 8900400100,
                    "tx_bytes": 15400200300,
                    "paused": False,
                },
                {
                    "id": "dev_10",
                    "mac": "7C:49:EB:12:34:78",
                    "hostname": "Sonos-Era-300-L",
                    "nickname": "Sonos Speaker Salone",
                    "ip": "192.168.4.150",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 40,
                    "signal_rssi": -58,
                    "rx_bitrate": "300.0 MBit/s",
                    "phy_rate": "300.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 4.1,
                    "upload_rate_mbps": 0.2,
                    "rx_bytes": 6700500100,
                    "tx_bytes": 230100200,
                    "paused": False,
                },
                {
                    "id": "dev_11",
                    "mac": "3C:22:FB:99:88:77",
                    "hostname": "Galaxy-Tab-S9",
                    "nickname": "Tablet Studio & Lettura",
                    "ip": "192.168.4.160",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "5GHz",
                    "frequency_band": "5 GHz",
                    "channel": 36,
                    "signal_rssi": -79,
                    "rx_bitrate": "54.0 MBit/s",
                    "phy_rate": "54.0 MBit/s",
                    "connected_eero_id": "eero_01_gateway",
                    "connected_eero_name": "Gateway Soggiorno",
                    "download_rate_mbps": 1.2,
                    "upload_rate_mbps": 0.1,
                    "rx_bytes": 18500200100,
                    "tx_bytes": 3400100200,
                    "paused": False,
                }
            ],
            "reservations": [
                {"id": "res_01", "mac": "00:11:32:9F:88:44", "ip": "192.168.4.10", "description": "Synology NAS Static IP"},
                {"id": "res_02", "mac": "DC:A6:32:88:77:66", "ip": "192.168.4.20", "description": "Home Assistant Yellow"},
            ],
            "forwards": [
                {"id": "fwd_01", "ip": "192.168.4.10", "port_from": 5001, "port_to": 5001, "protocol": "tcp", "description": "Synology DSM HTTPS"},
                {"id": "fwd_02", "ip": "192.168.4.20", "port_from": 8123, "port_to": 8123, "protocol": "tcp", "description": "Home Assistant WebUI"},
                {"id": "fwd_03", "ip": "192.168.4.10", "port_from": 32400, "port_to": 32400, "protocol": "tcp", "description": "Plex Media Server"},
            ],
            "profiles": [
                {
                    "id": "prof_01",
                    "url": "/2.2/profiles/prof_01",
                    "name": "Marco",
                    "paused": False,
                    "devices": [
                        {"id": "dev_01", "url": "/2.2/devices/dev_01", "mac": "b4:2e:99:a1:01:10", "nickname": "MacBook Pro Lavoro", "hostname": "MacBook-Pro-M3", "ip": "192.168.4.101", "connected": True, "paused": False},
                        {"id": "dev_03", "url": "/2.2/devices/dev_03", "mac": "f4:f5:db:33:44:55", "nickname": "iPhone Personale", "hostname": "iPhone-15-Pro", "ip": "192.168.4.110", "connected": True, "paused": False},
                    ]
                },
                {
                    "id": "prof_02",
                    "url": "/2.2/profiles/prof_02",
                    "name": "Giulia",
                    "paused": False,
                    "devices": [
                        {"id": "dev_08", "url": "/2.2/devices/dev_08", "mac": "e0:4f:43:aa:bb:cc", "nickname": "iPad Cucina / Ricette", "hostname": "Apple-iPad-Air", "ip": "192.168.4.135", "connected": False, "paused": False}
                    ]
                },
                {
                    "id": "prof_03",
                    "url": "/2.2/profiles/prof_03",
                    "name": "Intrattenimento & Salotto",
                    "paused": False,
                    "devices": [
                        {"id": "dev_04", "url": "/2.2/devices/dev_04", "mac": "28:70:4e:88:99:aa", "nickname": "Smart TV OLED 65\"", "hostname": "Sony-Bravia-OLED-4K", "ip": "192.168.4.120", "connected": True, "paused": False},
                        {"id": "dev_05", "url": "/2.2/devices/dev_05", "mac": "a8:5e:45:12:34:56", "nickname": "PS5 Pro Console", "hostname": "PlayStation-5", "ip": "192.168.4.125", "connected": True, "paused": False},
                        {"id": "dev_10", "url": "/2.2/devices/dev_10", "mac": "7c:49:eb:12:34:78", "nickname": "Sonos Speaker Salone", "hostname": "Sonos-Era-300-L", "ip": "192.168.4.150", "connected": True, "paused": False}
                    ]
                }
            ]
        }

        # 2. Rete Demo 2: Professionale Multi-Gigabit (Ufficio & Studio Pro Mesh - Issue #22)
        net2 = {
            "account": {
                "name": "Mario Rossi (Pro Admin)",
                "email": "mario.rossi@homelab.local",
                "phone": "+39 340 1234567"
            },
            "network": {
                "id": "network_demo_mesh_02",
                "name": "Ufficio & Studio Pro Mesh",
                "status": "online",
                "public_ip": "2.228.104.55",
                "gateway_ip": "192.168.10.1",
                "subnet_mask": "255.255.255.0",
                "dns_servers": ["9.9.9.9", "149.112.112.112"],
                "isp": "Fastweb FTTH 2.5Gbps / 1Gbps",
                "ipv6_enabled": True,
                "upnp_enabled": False,
                "band_steering_enabled": True,
                "health_score": 100,
            },
            "guest_network": {
                "enabled": False,
                "name": "Studio - Ospiti Pro",
                "password": "StudioGuest2026!",
            },
            "speedtest": {
                "download_mbps": 2240.50,
                "upload_mbps": 980.20,
                "ping_ms": 5.4,
                "jitter": 0.8,
                "date": now_iso,
            },
            "eeros": [
                {
                    "id": "eero_office_gw",
                    "serial": "GW-EEROMAX7-001",
                    "name": "Gateway Rack Ufficio",
                    "model": "eero Max 7 (T010001)",
                    "is_gateway": True,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.10.1",
                    "mac": "50:D4:F7:11:AA:BB",
                    "os_version": "v7.5.2-192",
                    "led_on": True,
                    "backhaul_type": "Gateway (WAN)",
                    "connected_clients_count": 6,
                },
                {
                    "id": "eero_office_lab",
                    "serial": "EEROMAX7-002-LAB",
                    "name": "Laboratorio & Workstation",
                    "model": "eero Max 7 (T010001)",
                    "is_gateway": False,
                    "wired": True,
                    "status": "online",
                    "ip": "192.168.10.2",
                    "mac": "50:D4:F7:22:CC:DD",
                    "os_version": "v7.5.2-192",
                    "led_on": False,
                    "backhaul_type": "Ethernet (2.5 Gbps)",
                    "connected_clients_count": 4,
                }
            ],
            "devices": [
                {
                    "id": "dev_off_01",
                    "mac": "3C:22:FB:44:55:66",
                    "hostname": "Proxmox-Cluster-01",
                    "nickname": "Hypervisor Proxmox VE",
                    "ip": "192.168.10.200",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "2.5 Gbps",
                    "connected_eero_id": "eero_office_gw",
                    "connected_eero_name": "Gateway Rack Ufficio",
                    "download_rate_mbps": 12.5,
                    "upload_rate_mbps": 18.2,
                    "rx_bytes": 85000200000,
                    "tx_bytes": 94000300000,
                    "paused": False,
                },
                {
                    "id": "dev_off_02",
                    "mac": "74:D4:35:12:34:56",
                    "hostname": "Workstation-Threadripper",
                    "nickname": "Dev Workstation Linux",
                    "ip": "192.168.10.150",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "6GHz",
                    "frequency_band": "6 GHz",
                    "channel": 85,
                    "signal_rssi": -42,
                    "rx_bitrate": "4320.0 MBit/s",
                    "phy_rate": "4320.0 MBit/s",
                    "connected_eero_id": "eero_office_lab",
                    "connected_eero_name": "Laboratorio & Workstation",
                    "download_rate_mbps": 65.4,
                    "upload_rate_mbps": 12.0,
                    "rx_bytes": 45000100000,
                    "tx_bytes": 12000400000,
                    "paused": False,
                },
                {
                    "id": "dev_off_03",
                    "mac": "00:25:90:88:99:AA",
                    "hostname": "TrueNAS-Enterprise",
                    "nickname": "Storage ZFS Primario",
                    "ip": "192.168.10.210",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "2.5 Gbps",
                    "connected_eero_id": "eero_office_gw",
                    "connected_eero_name": "Gateway Rack Ufficio",
                    "download_rate_mbps": 4.5,
                    "upload_rate_mbps": 8.0,
                    "rx_bytes": 62000400000,
                    "tx_bytes": 71000800000,
                    "paused": False,
                },
                {
                    "id": "dev_off_04",
                    "mac": "A4:83:E7:55:66:77",
                    "hostname": "iPad-Pro-M4",
                    "nickname": "iPad Pro Studio",
                    "ip": "192.168.10.122",
                    "connected": True,
                    "wireless": True,
                    "connection_type": "wireless",
                    "wireless_band": "6GHz",
                    "frequency_band": "6 GHz",
                    "channel": 85,
                    "signal_rssi": -46,
                    "rx_bitrate": "2400.0 MBit/s",
                    "phy_rate": "2400.0 MBit/s",
                    "connected_eero_id": "eero_office_lab",
                    "connected_eero_name": "Laboratorio & Workstation",
                    "download_rate_mbps": 18.2,
                    "upload_rate_mbps": 3.1,
                    "rx_bytes": 15000200000,
                    "tx_bytes": 3500100200,
                    "paused": False,
                },
                {
                    "id": "dev_off_05",
                    "mac": "00:08:E3:11:22:33",
                    "hostname": "Cisco-IP-Phone-8861",
                    "nickname": "VoIP Desk Phone",
                    "ip": "192.168.10.80",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "1.0 Gbps",
                    "connected_eero_id": "eero_office_gw",
                    "connected_eero_name": "Gateway Rack Ufficio",
                    "download_rate_mbps": 0.2,
                    "upload_rate_mbps": 0.2,
                    "rx_bytes": 850100200,
                    "tx_bytes": 820100400,
                    "paused": False,
                },
                {
                    "id": "dev_off_06",
                    "mac": "F0:9F:C2:77:88:99",
                    "hostname": "UniFi-Switch-Enterprise-8",
                    "nickname": "Switch PoE 2.5G Rack",
                    "ip": "192.168.10.2",
                    "connected": True,
                    "wireless": False,
                    "wired": True,
                    "connection_type": "wired",
                    "wireless_band": "Ethernet",
                    "frequency_band": "Ethernet",
                    "channel": None,
                    "signal_rssi": None,
                    "ethernet_speed": "2.5 Gbps",
                    "connected_eero_id": "eero_office_gw",
                    "connected_eero_name": "Gateway Rack Ufficio",
                    "download_rate_mbps": 0.1,
                    "upload_rate_mbps": 0.1,
                    "rx_bytes": 450100200,
                    "tx_bytes": 420100100,
                    "paused": False,
                }
            ],
            "reservations": [
                {"id": "res_off_01", "mac": "3C:22:FB:44:55:66", "ip": "192.168.10.200", "description": "Proxmox Cluster Primary"},
                {"id": "res_off_02", "mac": "00:25:90:88:99:AA", "ip": "192.168.10.210", "description": "TrueNAS Storage"},
            ],
            "forwards": [
                {"id": "fwd_off_01", "ip": "192.168.10.200", "port_from": 8006, "port_to": 8006, "protocol": "tcp", "description": "Proxmox WebUI"},
                {"id": "fwd_off_02", "ip": "192.168.10.210", "port_from": 443, "port_to": 443, "protocol": "tcp", "description": "TrueNAS HTTPS"},
            ],
            "profiles": [
                {
                    "id": "prof_off_01",
                    "url": "/2.2/profiles/prof_off_01",
                    "name": "Dev & DevOps",
                    "paused": False,
                    "devices": [
                        {"id": "dev_off_01", "url": "/2.2/devices/dev_off_01", "mac": "3c:22:fb:44:55:66", "nickname": "Hypervisor Proxmox VE", "hostname": "Proxmox-Cluster-01", "ip": "192.168.10.200", "connected": True, "paused": False},
                        {"id": "dev_off_02", "url": "/2.2/devices/dev_off_02", "mac": "74:d4:35:12:34:56", "nickname": "Dev Workstation Linux", "hostname": "Workstation-Threadripper", "ip": "192.168.10.150", "connected": True, "paused": False},
                    ]
                },
                {
                    "id": "prof_off_02",
                    "url": "/2.2/profiles/prof_off_02",
                    "name": "Enterprise Storage",
                    "paused": False,
                    "devices": [
                        {"id": "dev_off_03", "url": "/2.2/devices/dev_off_03", "mac": "00:25:90:88:99:aa", "nickname": "Storage ZFS Primario", "hostname": "TrueNAS-Enterprise", "ip": "192.168.10.210", "connected": True, "paused": False},
                    ]
                }
            ]
        }

        self._demo_networks_store = {
            "network_demo_mesh_01": net1,
            "network_demo_mesh_02": net2,
        }

        active_id = self.current_network_id if self.current_network_id in self._demo_networks_store else "network_demo_mesh_01"
        return self._demo_networks_store[active_id]

    def _get_demo_account(self) -> Dict[str, Any]:
        return {
            "name": self._demo_state["account"]["name"],
            "email": self._demo_state["account"]["email"],
            "phone": self._demo_state["account"]["phone"],
            "networks": {
                "data": [
                    {
                        "id": "network_demo_mesh_01",
                        "name": "Casa Rossi Mesh 6E",
                        "url": "/2.2/networks/network_demo_mesh_01",
                        "role": "owner",
                    },
                    {
                        "id": "network_demo_mesh_02",
                        "name": "Ufficio & Studio Pro Mesh",
                        "url": "/2.2/networks/network_demo_mesh_02",
                        "role": "admin",
                    }
                ]
            }
        }

    def _get_demo_network_details(self) -> Dict[str, Any]:
        # Modulazione casuale per rendere i grafici vivi e dinamici
        return {
            **self._demo_state["network"],
            "speedtest": self._demo_state["speedtest"],
            "guest_network": self._demo_state["guest_network"],
            "client_count": len([d for d in self._demo_state["devices"] if d["connected"]]),
            "eero_count": len(self._demo_state["eeros"]),
        }

    def _get_demo_eeros(self) -> List[Dict[str, Any]]:
        return self._demo_state["eeros"]

    def _get_demo_profiles(self) -> List[Dict[str, Any]]:
        raw_list = self._demo_state.get("profiles", [])
        return [self._normalize_profile(p) for p in raw_list]

    def _get_demo_devices(self) -> List[Dict[str, Any]]:
        # Varia leggermente i tassi di trasmissione attorno a un valore base fisso per simulare traffico live
        # (moltiplicare il valore del poll precedente produceva una crescita esponenziale senza limite)
        normalized_list = []
        for d in self._demo_state["devices"]:
            if d.get("connected"):
                base_down, base_up = self._demo_base_rates.setdefault(
                    str(d.get("id") or d.get("mac")),
                    (d.get("download_rate_mbps", 1.0), d.get("upload_rate_mbps", 0.5)),
                )
                jitter = random.uniform(0.85, 1.25)
                d["download_rate_mbps"] = round(base_down * jitter, 2)
                d["upload_rate_mbps"] = round(base_up * jitter, 2)
                d["rx_bytes"] = int(d.get("rx_bytes", 0)) + int(d["download_rate_mbps"] * 1024 * 1024 / 8 * 30)
                d["tx_bytes"] = int(d.get("tx_bytes", 0)) + int(d["upload_rate_mbps"] * 1024 * 1024 / 8 * 30)
            norm = self._normalize_device(d)
            normalized_list.append(norm)
        return normalized_list


    def _set_demo_eero_led(self, eero_id: str, led_on: bool) -> Dict[str, Any]:
        """Aggiorna lo stato simulato del LED per un nodo demo."""
        for eero in self._demo_state["eeros"]:
            if eero["id"] == eero_id or eero["serial"] == eero_id:
                eero["led_on"] = led_on
        return {"status": "success", "eero_id": eero_id, "led_on": led_on}

    def _update_demo_device(
        self,
        device_id: str,
        nickname: Optional[str] = None,
        paused: Optional[bool] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggiorna alias o stato pausa per un dispositivo demo."""
        for dev in self._demo_state["devices"]:
            if dev["id"] == device_id or dev["mac"] == device_id:
                if nickname is not None:
                    dev["nickname"] = nickname
                if paused is not None:
                    dev["paused"] = bool(paused)
                    dev["is_paused"] = bool(paused)
                return {"status": "success", "device": dev, "cloud_synced": True, "mode": "demo"}
        return {
            "status": "warning",
            "device_id": device_id,
            "updated": payload or {},
            "cloud_synced": False,
            "last_error": tr("eero.device_update_unavailable"),
        }

    def _set_demo_guest_network(
        self,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggiorna le impostazioni della rete ospiti demo."""
        self._demo_state["guest_network"]["enabled"] = enabled
        if name:
            self._demo_state["guest_network"]["name"] = name
        if password:
            self._demo_state["guest_network"]["password"] = password
        return {"status": "success", "guest_network": self._demo_state["guest_network"]}

    def _run_demo_speedtest(self) -> Dict[str, Any]:
        """Genera un risultato realistico per lo speedtest simulato."""
        dl = round(random.uniform(750.0, 940.0), 2)
        ul = round(random.uniform(250.0, 310.0), 2)
        p = round(random.uniform(8.0, 15.0), 1)
        j = round(random.uniform(0.8, 2.5), 1)
        self._demo_state["speedtest"] = {
            "download_mbps": dl,
            "upload_mbps": ul,
            "ping_ms": p,
            "jitter": j,
            "date": datetime.now(timezone.utc).isoformat(),
        }
        return {"status": "success", "result": self._demo_state["speedtest"]}

    def _get_demo_reservations_and_forwards(self) -> Dict[str, Any]:
        """Restituisce le prenotazioni IP e i port forward demo normalizzati."""
        raw_res = self._demo_state.get("reservations", [])
        raw_fwd = self._demo_state.get("forwards", [])
        return {
            "status": "success",
            "reservations": [self._normalize_reservation(r) for r in raw_res],
            "forwards": [self._normalize_forward(f) for f in raw_fwd],
        }

    def _add_demo_reservation(self, reservation: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiunge una prenotazione IP statica demo."""
        mac = reservation.get("mac") or ""
        ip = reservation.get("ip") or ""
        self._demo_state["reservations"] = [
            r for r in self._demo_state.get("reservations", [])
            if (r.get("mac") or "").lower() != mac.lower() and r.get("ip") != ip
        ]
        self._demo_state["reservations"].append(reservation)
        return {"status": "success", "reservation": self._normalize_reservation(reservation)}

    def _delete_demo_reservation(self, clean_id: str) -> Dict[str, Any]:
        """Rimuove una prenotazione IP demo."""
        self._demo_state["reservations"] = [
            r for r in self._demo_state.get("reservations", [])
            if r.get("id") != clean_id and (r.get("mac") or "").lower() != clean_id.lower() and r.get("ip") != clean_id
        ]
        return {"status": "success", "deleted": clean_id}

    def _add_demo_forward(self, rule_demo: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiunge una regola di port forwarding demo."""
        self._demo_state["forwards"].append(rule_demo)
        return {"status": "success", "forward": self._normalize_forward(rule_demo)}

    def _delete_demo_forward(self, clean_id: str) -> Dict[str, Any]:
        """Rimuove una regola di port forwarding demo."""
        self._demo_state["forwards"] = [f for f in self._demo_state["forwards"] if f.get("id") != clean_id]
        return {"status": "success", "deleted": clean_id}

    def _create_demo_profile(self, new_profile: Dict[str, Any], dev_ids: List[str]) -> Dict[str, Any]:
        """Crea un nuovo profilo utente nella rete demo."""
        for d in self._demo_state.get("devices", []):
            d_id = str(d.get("id"))
            d_mac = (d.get("mac") or "").lower()
            if d_id in dev_ids or d_mac in dev_ids:
                d["profile"] = {"id": new_profile["id"], "name": new_profile["name"]}
                new_profile["devices"].append({
                    "id": d.get("id"),
                    "url": d.get("url"),
                    "mac": d.get("mac"),
                    "nickname": d.get("nickname"),
                    "hostname": d.get("hostname"),
                    "ip": d.get("ip"),
                    "connected": d.get("connected"),
                    "paused": d.get("paused"),
                })
                for p in self._demo_state.get("profiles", []):
                    p["devices"] = [x for x in p.get("devices", []) if str(x.get("id")) != d_id and (x.get("mac") or "").lower() != d_mac]
        if "profiles" not in self._demo_state:
            self._demo_state["profiles"] = []
        self._demo_state["profiles"].append(new_profile)
        return {"status": "success", "profile": new_profile}

    def _update_demo_profile(self, clean_id: str, updates: Dict[str, Any], dev_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Aggiorna un profilo utente demo."""
        for p in self._demo_state.get("profiles", []):
            if p["id"] == clean_id or p.get("url", "").endswith(clean_id):
                p.update(updates)
                if dev_ids is not None:
                    p["devices"] = []
                    for d in self._demo_state.get("devices", []):
                        d_id = str(d.get("id"))
                        d_mac = (d.get("mac") or "").lower()
                        if d_id in dev_ids or d_mac in dev_ids:
                            d["profile"] = {"id": clean_id, "name": p.get("name")}
                            p["devices"].append({
                                "id": d.get("id"),
                                "url": d.get("url"),
                                "mac": d.get("mac"),
                                "nickname": d.get("nickname"),
                                "hostname": d.get("hostname"),
                                "ip": d.get("ip"),
                                "connected": d.get("connected"),
                                "paused": d.get("paused"),
                            })
                        elif d.get("profile") and (d["profile"].get("id") == clean_id or str(d["profile"].get("url", "")).endswith(clean_id)):
                            d["profile"] = None
                return {"status": "success", "profile": p}
        return {"status": "success"}

    def _delete_demo_profile(self, clean_id: str) -> Dict[str, Any]:
        """Elimina un profilo utente demo."""
        self._demo_state["profiles"] = [
            p for p in self._demo_state.get("profiles", [])
            if p["id"] != clean_id and not p.get("url", "").endswith(clean_id)
        ]
        for d in self._demo_state.get("devices", []):
            if d.get("profile") and (d["profile"].get("id") == clean_id or str(d["profile"].get("url", "")).endswith(clean_id)):
                d["profile"] = None
        return {"status": "success"}

    def _set_demo_device_profile(self, dev_key: str, clean_target_pid: Optional[str]) -> Dict[str, Any]:
        """Assegna un dispositivo demo a un profilo o lo rimuove dal profilo."""
        target_dev = None
        for d in self._demo_state.get("devices", []):
            if str(d.get("id")) == dev_key or (d.get("mac") or "").lower() == dev_key.lower():
                target_dev = d
                break
        if not target_dev:
            return {"status": "error", "message": "Device not found"}

        d_id = str(target_dev.get("id"))
        d_mac = (target_dev.get("mac") or "").lower()

        for p in self._demo_state.get("profiles", []):
            p["devices"] = [
                x for x in p.get("devices", [])
                if str(x.get("id")) != d_id and (x.get("mac") or "").lower() != d_mac
            ]

        target_dev["profile"] = None
        if clean_target_pid:
            for p in self._demo_state.get("profiles", []):
                if p["id"] == clean_target_pid or p.get("url", "").endswith(clean_target_pid):
                    target_dev["profile"] = {"id": p["id"], "name": p.get("name")}
                    p["devices"].append({
                        "id": target_dev.get("id"),
                        "url": target_dev.get("url"),
                        "mac": target_dev.get("mac"),
                        "nickname": target_dev.get("nickname"),
                        "hostname": target_dev.get("hostname"),
                        "ip": target_dev.get("ip"),
                        "connected": target_dev.get("connected"),
                        "paused": target_dev.get("paused"),
                    })
                    break
        return {"status": "success", "device": target_dev}

    def _get_demo_ipv6_firewall_rules(self) -> List[Dict[str, Any]]:
        """Restituisce le regole firewall IPv6 demo."""
        return list(self._demo_state.setdefault("ipv6_firewall_rules", [
            {
                "id": "fw6_demo_1",
                "device_name": "Proxmox-VE-Server",
                "mac": "bc:24:11:aa:bb:01",
                "protocol": "tcp",
                "ports": "443",
                "enabled": True,
            }
        ]))

    def _add_demo_ipv6_firewall_rule(self, device_name: str, mac: str, protocol: str, ports: str) -> Dict[str, Any]:
        """Aggiunge una regola firewall IPv6 demo."""
        rules = self._demo_state.setdefault("ipv6_firewall_rules", [])
        new_rule = {
            "id": f"fw6_{int(time.time() * 1000)}",
            "device_name": device_name,
            "mac": mac,
            "protocol": protocol,
            "ports": ports,
            "enabled": True,
        }
        rules.append(new_rule)
        return {"status": "success", "rule": new_rule}

    def _delete_demo_ipv6_firewall_rule(self, rule_id: str) -> Dict[str, Any]:
        """Rimuove una regola firewall IPv6 demo."""
        rules = self._demo_state.setdefault("ipv6_firewall_rules", [])
        self._demo_state["ipv6_firewall_rules"] = [r for r in rules if str(r.get("id")) != str(rule_id)]
        return {"status": "success", "deleted_id": rule_id}

    def _get_demo_guardian_vpn_status(self) -> Dict[str, Any]:
        """Restituisce lo stato simulato di Guardian VPN."""
        vpn_enabled = bool(self._demo_state.get("guardian_vpn_enabled", False))
        return {
            "status": "success",
            "supported": True,
            "enabled": vpn_enabled,
            "provider": "Guardian (eero Plus)",
        }

    def _set_demo_guardian_vpn_status(self, enabled: bool) -> Dict[str, Any]:
        """Imposta lo stato simulato di Guardian VPN."""
        self._demo_state["guardian_vpn_enabled"] = bool(enabled)
        return {"status": "success", "enabled": bool(enabled)}

    def _register_demo_eero_node(self, clean_serial: str, location: str) -> Dict[str, Any]:
        """Registra un nuovo nodo eero simulato nella rete demo."""
        new_node = {
            "id": f"eero_{clean_serial[-6:].lower()}",
            "serial": clean_serial,
            "name": location or "New eero Node",
            "location": location or "New eero Node",
            "model": "eero Max 7",
            "ip": f"192.168.4.{random.randint(20, 49)}",
            "mac_address": "b0:f1:ec:99:88:77",
            "status": "online",
            "is_gateway": False,
            "wired": False,
            "backhaul_type": "Wi-Fi 7 MLO (6 GHz)",
            "mesh_quality_bars": 5,
            "os_version": "v7.6.2-41",
            "connected_clients_count": 0,
        }
        self._demo_state["eeros"].append(new_node)
        return {"status": "success", "node": new_node}
