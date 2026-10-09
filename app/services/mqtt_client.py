import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.db import db_service

logger = logging.getLogger(__name__)

# Check if aiomqtt is available
try:
    import aiomqtt
    AIOMQTT_AVAILABLE = True
except ImportError:
    try:
        import asyncio_mqtt as aiomqtt
        AIOMQTT_AVAILABLE = True
    except ImportError:
        aiomqtt = None
        AIOMQTT_AVAILABLE = False


class MQTTService:
    """Manages MQTT publishing and Home Assistant Auto-Discovery for eero telemetry."""

    def __init__(self):
        self._enabled: bool = settings.mqtt_enabled
        self._broker_host: str = settings.mqtt_broker_host
        self._broker_port: int = settings.mqtt_broker_port
        self._username: str = settings.mqtt_username
        self._password: str = settings.mqtt_password
        self._base_topic: str = settings.mqtt_base_topic
        self._ha_prefix: str = settings.mqtt_ha_discovery_prefix
        self._discovery_enabled: bool = settings.mqtt_discovery_enabled
        self._publish_interval: int = settings.mqtt_publish_interval

        self._connected: bool = False
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._discovery_published: bool = False
        self._stats: Dict[str, Any] = {
            "messages_published": 0,
            "discovery_topics_published": 0,
            "last_published_at": None,
            "last_error": None,
            "connected": False,
        }

    @property
    def is_available(self) -> bool:
        """Returns True if the required MQTT library is installed."""
        return AIOMQTT_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Returns True if currently connected to MQTT broker."""
        return self._connected

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    async def load_settings(self):
        """Loads runtime MQTT settings from SQLite database or falls back to env."""
        try:
            all_s = await db_service.get_all_settings()
            self._enabled = all_s.get("mqtt_enabled", str(settings.mqtt_enabled)).lower() in ("true", "1", "yes")
            self._broker_host = all_s.get("mqtt_broker_host", settings.mqtt_broker_host)
            self._broker_port = int(all_s.get("mqtt_broker_port", settings.mqtt_broker_port))
            self._username = all_s.get("mqtt_username", settings.mqtt_username)
            self._password = all_s.get("mqtt_password", settings.mqtt_password)
            self._base_topic = all_s.get("mqtt_base_topic", settings.mqtt_base_topic)
            self._ha_prefix = all_s.get("mqtt_ha_discovery_prefix", settings.mqtt_ha_discovery_prefix)
            self._discovery_enabled = all_s.get("mqtt_discovery_enabled", str(settings.mqtt_discovery_enabled)).lower() in ("true", "1", "yes")
            self._publish_interval = int(all_s.get("mqtt_publish_interval", settings.mqtt_publish_interval))
        except Exception as e:
            logger.debug(f"Unable to load MQTT settings from db: {e}")

    async def get_config(self) -> Dict[str, Any]:
        """Returns current MQTT configuration and connection status."""
        return {
            "enabled": self._enabled,
            "available": self.is_available,
            "connected": self._connected,
            "broker_host": self._broker_host,
            "broker_port": self._broker_port,
            "username": self._username,
            "has_password": bool(self._password),
            "base_topic": self._base_topic,
            "ha_discovery_prefix": self._ha_prefix,
            "discovery_enabled": self._discovery_enabled,
            "publish_interval": self._publish_interval,
            "stats": self._stats,
        }

    async def update_config(self, config_data: Dict[str, Any]):
        """Updates configuration and restarts connection if enabled."""
        if "enabled" in config_data:
            self._enabled = bool(config_data["enabled"])
            await db_service.set_setting("mqtt_enabled", "true" if self._enabled else "false")

        if "broker_host" in config_data and config_data["broker_host"]:
            self._broker_host = str(config_data["broker_host"]).strip()
            await db_service.set_setting("mqtt_broker_host", self._broker_host)

        if "broker_port" in config_data and config_data["broker_port"]:
            self._broker_port = int(config_data["broker_port"])
            await db_service.set_setting("mqtt_broker_port", str(self._broker_port))

        if "username" in config_data:
            self._username = str(config_data["username"] or "").strip()
            await db_service.set_setting("mqtt_username", self._username)

        if "password" in config_data and config_data["password"] is not None:
            self._password = str(config_data["password"])
            await db_service.set_setting("mqtt_password", self._password)

        if "base_topic" in config_data and config_data["base_topic"]:
            self._base_topic = str(config_data["base_topic"]).strip().strip("/")
            await db_service.set_setting("mqtt_base_topic", self._base_topic)

        if "ha_discovery_prefix" in config_data and config_data["ha_discovery_prefix"]:
            self._ha_prefix = str(config_data["ha_discovery_prefix"]).strip().strip("/")
            await db_service.set_setting("mqtt_ha_discovery_prefix", self._ha_prefix)

        if "discovery_enabled" in config_data:
            self._discovery_enabled = bool(config_data["discovery_enabled"])
            await db_service.set_setting("mqtt_discovery_enabled", "true" if self._discovery_enabled else "false")

        if "publish_interval" in config_data and config_data["publish_interval"]:
            self._publish_interval = max(5, int(config_data["publish_interval"]))
            await db_service.set_setting("mqtt_publish_interval", str(self._publish_interval))

        # Restart worker if running
        await self.stop()
        if self._enabled:
            await self.start()

    def _get_device_dict(self) -> Dict[str, Any]:
        """Generates standard Home Assistant device block."""
        return {
            "identifiers": ["eero_mesh_network"],
            "name": "eero Mesh System",
            "model": "eero Gateway & Mesh",
            "manufacturer": "eero / Amazon",
            "sw_version": settings.app_version,
            "configuration_url": "http://localhost:8000"
        }

    def _get_discovery_payloads(self) -> List[Dict[str, Any]]:
        """Returns the list of Home Assistant auto-discovery configs."""
        dev = self._get_device_dict()
        base = self._base_topic
        
        entities = [
            # WAN Download
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/wan_download/config",
                "payload": {
                    "name": "eero WAN Download",
                    "unique_id": "eero_wan_download_speed",
                    "state_topic": f"{base}/sensor/wan_download/state",
                    "unit_of_measurement": "Mbps",
                    "device_class": "data_rate",
                    "state_class": "measurement",
                    "icon": "mdi:download-network",
                    "device": dev
                }
            },
            # WAN Upload
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/wan_upload/config",
                "payload": {
                    "name": "eero WAN Upload",
                    "unique_id": "eero_wan_upload_speed",
                    "state_topic": f"{base}/sensor/wan_upload/state",
                    "unit_of_measurement": "Mbps",
                    "device_class": "data_rate",
                    "state_class": "measurement",
                    "icon": "mdi:upload-network",
                    "device": dev
                }
            },
            # Health Score
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/health_score/config",
                "payload": {
                    "name": "eero Network Health",
                    "unique_id": "eero_network_health_score",
                    "state_topic": f"{base}/sensor/health_score/state",
                    "unit_of_measurement": "%",
                    "icon": "mdi:heart-pulse",
                    "device": dev
                }
            },
            # Connected Clients Count
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/clients_count/config",
                "payload": {
                    "name": "eero Connected Clients",
                    "unique_id": "eero_connected_clients_count",
                    "state_topic": f"{base}/sensor/clients_count/state",
                    "unit_of_measurement": "clients",
                    "state_class": "measurement",
                    "icon": "mdi:devices",
                    "device": dev
                }
            },
            # Mesh Nodes Online
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/nodes_online/config",
                "payload": {
                    "name": "eero Mesh Nodes Online",
                    "unique_id": "eero_mesh_nodes_online_count",
                    "state_topic": f"{base}/sensor/nodes_online/state",
                    "unit_of_measurement": "nodes",
                    "icon": "mdi:router-wireless",
                    "device": dev
                }
            },
            # Bufferbloat Grade
            {
                "topic": f"{self._ha_prefix}/sensor/{base}/bufferbloat_grade/config",
                "payload": {
                    "name": "eero Bufferbloat Grade",
                    "unique_id": "eero_bufferbloat_grade",
                    "state_topic": f"{base}/sensor/bufferbloat_grade/state",
                    "icon": "mdi:speedometer",
                    "device": dev
                }
            },
            # Internet Binary Sensor
            {
                "topic": f"{self._ha_prefix}/binary_sensor/{base}/internet/config",
                "payload": {
                    "name": "eero Internet Status",
                    "unique_id": "eero_internet_status_sensor",
                    "state_topic": f"{base}/binary_sensor/internet/state",
                    "payload_on": "ONLINE",
                    "payload_off": "OFFLINE",
                    "device_class": "connectivity",
                    "device": dev
                }
            },
            # Cloud Binary Sensor
            {
                "topic": f"{self._ha_prefix}/binary_sensor/{base}/cloud/config",
                "payload": {
                    "name": "eero Cloud Status",
                    "unique_id": "eero_cloud_status_sensor",
                    "state_topic": f"{base}/binary_sensor/cloud/state",
                    "payload_on": "CONNECTED",
                    "payload_off": "DISCONNECTED",
                    "device_class": "connectivity",
                    "device": dev
                }
            },
        ]
        return entities

    async def _publish_message(self, client: Any, topic: str, payload: Any, retain: bool = False):
        """Helper to publish string or JSON message."""
        if not isinstance(payload, str):
            payload_str = json.dumps(payload, default=str)
        else:
            payload_str = payload

        if client and hasattr(client, "publish"):
            await client.publish(topic, payload_str, qos=1, retain=retain)
            self._stats["messages_published"] += 1
            self._stats["last_published_at"] = datetime.now(timezone.utc).isoformat()

    async def publish_discovery_configs(self, client: Any):
        """Publishes all Home Assistant auto-discovery entities."""
        if not self._discovery_enabled:
            return

        payloads = self._get_discovery_payloads()
        for item in payloads:
            await self._publish_message(client, item["topic"], item["payload"], retain=True)
            self._stats["discovery_topics_published"] += 1

        self._discovery_published = True
        logger.info(f"[MQTT] Pubblicati {len(payloads)} topic di Home Assistant Auto-Discovery.")

    async def publish_telemetry(self, client: Any, telemetry_data: Optional[Dict[str, Any]] = None):
        """Publishes current network telemetry and device tracker states."""
        from app.services.poller import background_poller
        from app.services.eero_client import eero_client

        state = telemetry_data or background_poller.get_cached_state()
        devices = state.get("devices", [])
        connected_devs = [d for d in devices if d.get("connected")]
        
        # Calculate speeds & health
        total_dl = sum(float(d.get("download_rate_mbps", 0)) for d in connected_devs)
        total_ul = sum(float(d.get("upload_rate_mbps", 0)) for d in connected_devs)
        health = state.get("health_score", 100)
        nodes = state.get("eeros", [])
        nodes_online = sum(1 for n in nodes if n.get("status") in ("online", "active")) if nodes else 1

        # Bufferbloat
        bb_grade = state.get("bufferbloat_grade", "A")

        base = self._base_topic

        # Publish sensor states
        await self._publish_message(client, f"{base}/sensor/wan_download/state", round(total_dl, 2))
        await self._publish_message(client, f"{base}/sensor/wan_upload/state", round(total_ul, 2))
        await self._publish_message(client, f"{base}/sensor/health_score/state", health)
        await self._publish_message(client, f"{base}/sensor/clients_count/state", len(connected_devs))
        await self._publish_message(client, f"{base}/sensor/nodes_online/state", max(1, nodes_online))
        await self._publish_message(client, f"{base}/sensor/bufferbloat_grade/state", bb_grade)
        await self._publish_message(client, f"{base}/binary_sensor/internet/state", "ONLINE" if health > 20 else "OFFLINE")
        await self._publish_message(client, f"{base}/binary_sensor/cloud/state", "CONNECTED" if not getattr(eero_client, "is_cloud_unreachable", False) else "DISCONNECTED")

        # Full state payload
        full_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "download_mbps": round(total_dl, 2),
            "upload_mbps": round(total_ul, 2),
            "health_score": health,
            "connected_clients": len(connected_devs),
            "mesh_nodes_online": nodes_online,
            "bufferbloat_grade": bb_grade,
        }
        await self._publish_message(client, f"{base}/state", full_payload, retain=False)

        # Device Trackers for Home Assistant
        if self._discovery_enabled:
            for dev in connected_devs[:50]:  # limit to 50 active to avoid broker flood
                mac = str(dev.get("mac") or dev.get("mac_address") or "").replace(":", "").lower()
                if not mac:
                    continue

                hostname = dev.get("hostname") or dev.get("nickname") or f"eero_device_{mac[-4:]}"
                tracker_config_topic = f"{self._ha_prefix}/device_tracker/{base}_{mac}/config"
                tracker_state_topic = f"{base}/device/{mac}/state"
                tracker_attr_topic = f"{base}/device/{mac}/attributes"

                cfg = {
                    "name": hostname,
                    "unique_id": f"eero_tracker_{mac}",
                    "state_topic": tracker_state_topic,
                    "json_attributes_topic": tracker_attr_topic,
                    "payload_home": "home",
                    "payload_not_home": "not_home",
                    "source_type": "router",
                    "icon": "mdi:lan-connect" if dev.get("wireless") is False else "mdi:wifi",
                    "device": self._get_device_dict()
                }
                await self._publish_message(client, tracker_config_topic, cfg, retain=True)
                await self._publish_message(client, tracker_state_topic, "home", retain=False)
                await self._publish_message(client, tracker_attr_topic, {
                    "ip": dev.get("ip"),
                    "mac": dev.get("mac"),
                    "connected_eero": dev.get("connected_eero_name", "Gateway"),
                    "wireless": dev.get("wireless", True),
                    "band": dev.get("wireless_band", "5 GHz")
                }, retain=False)

    async def _worker_loop(self):
        """Background asynchronous MQTT client loop with auto-reconnect."""
        from app.services.eero_client import eero_client
        logger.info(f"[MQTT] Avvio worker MQTT (Broker: {self._broker_host}:{self._broker_port}, Base Topic: {self._base_topic})")

        while not self._stop_event.is_set():
            if not self._enabled:
                await asyncio.sleep(2)
                continue

            if not self.is_available:
                logger.warning("[MQTT] Modulo aiomqtt non disponibile. Installare aiomqtt per abilitare la pubblicazione MQTT.")
                await asyncio.sleep(60)
                continue

            # In Demo mode, simulate MQTT connectivity without network socket failures
            if getattr(eero_client, "is_demo_mode", False) and self._broker_host in ("localhost", "127.0.0.1", "demo"):
                self._connected = True
                self._stats["connected"] = True
                self._stats["messages_published"] += 1
                self._stats["last_published_at"] = datetime.now(timezone.utc).isoformat()
                await asyncio.sleep(self._publish_interval)
                continue

            try:
                auth = None
                if self._username:
                    auth = {"username": self._username, "password": self._password}

                client_kwargs = {
                    "hostname": self._broker_host,
                    "port": self._broker_port,
                    "timeout": 10.0,
                }
                if self._username:
                    client_kwargs["username"] = self._username
                    client_kwargs["password"] = self._password

                async with aiomqtt.Client(**client_kwargs) as client:
                    self._connected = True
                    self._stats["connected"] = True
                    self._stats["last_error"] = None
                    logger.info(f"[MQTT] Connesso con successo al broker {self._broker_host}:{self._broker_port}")

                    # Publish Home Assistant Discovery
                    await self.publish_discovery_configs(client)

                    # Periodic Telemetry Publishing
                    while not self._stop_event.is_set():
                        await self.publish_telemetry(client)
                        await asyncio.sleep(self._publish_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._stats["connected"] = False
                self._stats["last_error"] = str(e)
                logger.warning(f"[MQTT] Errore connessione broker {self._broker_host}:{self._broker_port} ({e}). Riprovo tra 15s...")
                await asyncio.sleep(15)

        self._connected = False
        self._stats["connected"] = False
        logger.info("[MQTT] Worker MQTT terminato.")

    async def start(self):
        """Starts the background MQTT client worker."""
        await self.load_settings()
        if not self._enabled:
            logger.info("[MQTT] Servizio MQTT disabilitato da configurazione.")
            return

        if self._task and not self._task.done():
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """Stops the background MQTT client worker."""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._connected = False
        self._stats["connected"] = False


mqtt_service = MQTTService()
