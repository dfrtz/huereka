"""Utility for creating and maintaining WLAN connections."""

import binascii
import json
import logging
import os
import pathlib
import time
from typing import Callable
from typing import override

import network
from microdot import Request

from . import microdot_utils

logger = logging.getLogger(__name__)


class WLANConfigurationApp(microdot_utils.Microdot):
    """Microdot web server to configure new WLAN connections."""

    def __init__(
        self,
        wlan: network.WLAN,
        config_path: str,
        hostname: str | None = None,
        on_new_config: Callable | None = None,
    ) -> None:
        """Set up the initial application values.

        Args:
            wlan: Wireless interface in client mode (STA/Station) to configure and connect to a network.
            config_path: Path to file where WLAN configurations should be saved and loaded.
            hostname: Initial name to set on the device before connecting to the network.
                Can be updated by users through configuration portal.
            on_new_config: Callback to trigger after a new network configuration is created.
        """
        super().__init__(static_root=f"{pathlib.Path(__file__).parent}/static")
        self.wlan = wlan
        self.config_path = config_path
        self.hostname = hostname
        self.on_new_config = on_new_config
        self.get("/configure")(self._get_configure)
        self.post("/configure")(self._post_configure)
        self.get("/networks")(self._get_networks)
        self.get("/static/<string:path>")(self._static)

    @override
    def _after_request(self) -> None:
        """Monitor for connection updates and shutdown server when connected to an external network."""
        if self.wlan.isconnected():
            self.shutdown()
            self.server.close()

    def _get_configure(self, request: Request) -> tuple:
        """Serve the main configuration web page."""
        content, code, content_type = self._static(request, "configure.html")
        return content.replace('HOSTNAME="";', f'HOSTNAME="{self.hostname}";'), code, content_type

    def _get_networks(self, request: Request) -> tuple:
        """Serve the list of available networks."""
        logger.info("Scanning for available WLAN connections")
        self.wlan.active(True)
        if self.wlan.isconnected():
            logger.info("Disconnecting WLAN for scan")
            self.wlan.disconnect()
        options = []
        for ssid, bssid_raw, _, rssi, security, _ in self.wlan.scan():
            if security <= 0:
                continue
            options.append(
                {
                    "ssid": ssid.decode("utf-8"),
                    "bssid": binascii.hexlify(bssid_raw).decode("utf-8"),
                    "strength": rssi,
                    "security": security,
                }
            )
        self.wlan.active(False)
        logger.info(f"Found {len(options)} available WLAN connections")
        return json.dumps(options), 200, {"Content-Type": "application/json"}

    def _post_configure(self, request: Request) -> tuple:
        """Handle a request to update the network configuration."""
        form = request.form
        bssid = form.get("bssid")
        ssid = form.get("ssid")
        password = form.get("password")
        hostname = form.get("hostname") or self.hostname or network.hostname()
        logger.info(f"Received network setup request for {ssid} {bssid} as {hostname}")

        if not password or not ssid:
            return json.dumps({"error": f"Missing ssid or password"}), 422, {"Content-Type": "application/json"}

        wait = 10
        if connect(self.wlan, ssid, password, hostname=hostname, bssid=bssid, wait=wait):
            config = {
                "ssid": ssid,
                "bssid": bssid,
                "password": password,
                "hostname": hostname,
            }
            try:
                self._save_config(config)
            except Exception as error:
                logger.exception(f"Failed to save new config: {error}", exc_info=error)
                return (
                    json.dumps({"error": f"Failed to save configuration: {error}"}),
                    200,
                    {"Content-Type": "application/json"},
                )
            if self.on_new_config:
                try:
                    self.on_new_config(config)
                except Exception as error:
                    logger.exception(f"Failed to run new config callback: {error}", exc_info=error)
            return (
                json.dumps(
                    {
                        "ssid": ssid,
                        "bssid": bssid,
                        "hostname": hostname,
                        "ifconfig": list(self.wlan.ifconfig()),
                    }
                ),
                200,
                {"Content-Type": "application/JSON"},
            )
        else:
            return (
                json.dumps({"error": f"Unable to establish connection to {ssid} after {wait} seconds"}),
                200,
                {"Content-Type": "application/json"},
            )

    def _save_config(self, config: dict) -> None:
        """Save a new, or update an existing, WLAN configuration."""
        profiles = load_config(self.config_path) or []
        updated = False
        for profile in profiles:
            if profile["ssid"] == config["ssid"] and profile.get("bssid") == config.get("bssid"):
                logger.info(f"Update WLAN configuration for {profile['ssid']}")
                updated = True
                profile["password"] = config["password"]
                profile["hostname"] = config["hostname"]
                save_config(self.config_path, profiles)
                break
        if not updated:
            logger.info(f"Added new WLAN configuration for {config['ssid']}")
            profiles.append(config)
            save_config(self.config_path, profiles)


def connect(
    wlan: network.WLAN,
    ssid: str,
    password: str,
    hostname: str | None = None,
    bssid: bytes | str | None = None,
    wait: int = 10,
) -> bool:
    """Connect a wireless interface to a network.

    Args:
        wlan: Wireless interface in client mode (STA/Station) to connect to a network.
        ssid: Name of the network to connect to.
        password: Password to use to establish a connection.
        hostname: Name to set on the device before connecting to the network.
        bssid: Optional hardware address of an access point to force only a connection to that device.
        wait: How long to wait for a connection to be established before aborting.

    Returns:
        Whether the connection was successful..
    """
    if isinstance(bssid, str):
        bssid = binascii.unhexlify(bssid.replace(":", ""))

    wlan.active(True)
    if wlan.isconnected():
        wlan.disconnect()

    logger.info(f"Attempting WLAN connection to {ssid}, max wait {wait} seconds")
    if hostname:
        network.hostname(hostname)
    else:
        hostname = network.hostname()
    wlan.connect(ssid, password, bssid=bssid)
    connected = False
    for retry in range(wait * 15):
        connected = wlan.isconnected()
        if connected:
            break
        time.sleep(0.1)
    if connected:
        logger.info(f"WLAN connection succeeded to {ssid} as {hostname} with {wlan.ifconfig()}")
    else:
        wlan.active(False)
        logger.warning(f"WLAN connection failed to {ssid} as {hostname}")
    return connected


def connect_from_profiles(
    wlan: network.WLAN,
    profiles: list[dict],
    min_security_level: int = 1,
    force_reconnect: bool = False,
) -> bool:
    """Connect to the best available WLAN using saved profiles.

    The strongest connection available will be preferred based on the following rules:
        1. If a profile has a BSSID, only connect to that specific network by BSSID (max security).
        2. If a profile has a SSID and no BSSID, connect to the best network with that SSID (minimal security).

    Args:
        wlan: Wireless interface in client mode (STA/Station) to connect to a network.
        profiles: List of WLAN connection profiles.
        min_security_level: Minimum security level required to connect to a network.
        force_reconnect: Force disconnect from current network before attempting to connect.
            If False and already connected, will return current connection.

    Returns:
        Whether the WLAN connection was successful.
    """
    if wlan.isconnected():
        if force_reconnect:
            wlan.disconnect()
        else:
            return wlan

    bssid_map = {}
    ssid_map = {}
    for profile in profiles:
        if profile.get("bssid"):
            bssid_map[profile["bssid"].upper()] = profile
        elif profile.get("ssid"):
            ssid_map[profile["ssid"]] = profile

    connected = False
    if bssid_map or ssid_map:
        wlan.active(True)
        # Networks are stored as: (ssid, bssid, channel, RSSI, security, hidden)
        for ssid_raw, bssid_raw, _, _, security, _ in sorted(wlan.scan(), key=lambda network: network[3], reverse=True):
            bssid = binascii.hexlify(bssid_raw, ":").decode("utf-8").upper()
            ssid = ssid_raw.decode("utf-8")
            if security >= min_security_level:
                profile = None
                if bssid in bssid_map:
                    profile = bssid_map[bssid]
                elif ssid in ssid_map and not ssid_map[ssid].get("bssid"):
                    # Only allow connection by SSID if no BSSID is provided.
                    profile = ssid_map[ssid]
                if profile:
                    connected = connect(
                        wlan,
                        ssid,
                        profile.get("password"),
                        hostname=profile.get("hostname"),
                        bssid=bssid_raw,
                    )
            if connected:
                break

    return connected


def _gen_id(size, chars: str | None = None) -> str:
    """Generate a new unique ID value for use in hostnames, AP SSIDs, etc."""
    new_id = ""
    chars = chars or "abcdefghijklmnopqrstuvwxyz0123456789"
    for _ in range(size):
        new_id += chars[int.from_bytes(os.urandom(1), "big") % len(chars)]
    return new_id


def get_wlan_or_configure(
    config_path: str | None = None,
    hostname: str | None = None,
    ap_ssid: str | None = None,
    ap_password: str | None = None,
    ap_security: int = 0,
    min_security_level: int = 1,
    on_new_config: Callable | None = None,
) -> network.WLAN:
    """Connect to WLAN using saved profiles, or turn on the setup application to allow initial configuration.

    Args:
        config_path: Path to file containing WLAN configuration.
        hostname: Initial name to set on the device before connecting to new networks.
            Can be updated by users through configuration portal.
        ap_ssid: Name of the network to create if not profiles are found, and initial setup is required.
            Defaults to hostname + "-setup".
        ap_password: Password to use on the temporary network during initial configuration.
        ap_security: Security level to use on the temporary network during initial configuration.
        min_security_level: Minimum security level required to connect to a network from saved profiles.
        on_new_config: Callback to trigger after a new network configuration is created.

    Returns:
        The wireless networking interface with the established connection.
    """
    profiles = load_config(config_path)
    if profiles:
        logger.info(f"Loaded {len(profiles)} WLAN profiles")
    else:
        logger.info(f"No WLAN profiles found")

    wlan_sta = network.WLAN(network.STA_IF)
    if profiles:
        connect_from_profiles(wlan_sta, profiles, min_security_level=min_security_level)
    elif profiles is None:
        if not hostname:
            hostname = f"uhuereka-{_gen_id(8)}"
        if not ap_ssid:
            ap_ssid = f"{hostname}-setup"
        # Start temporary web server to perform initial setup for the device.
        _start_configurator(
            wlan_sta,
            config_path,
            ap_ssid,
            ap_password,
            security=ap_security,
            hostname=hostname,
            on_new_config=on_new_config,
        )
    return wlan_sta


def load_config(path: str) -> list[dict] | None:
    """Load WLAN configuration from a file.

    Args:
        path: Path to file containing WLAN configuration.

    Returns:
        List of WLAN connection profiles, or None if there are no WLAN profiles.

    Raises:
        Exception on failure to load if the file was found.
    """
    profiles = None
    config_file = pathlib.Path(path)
    if config_file.exists():
        profiles = json.loads(pathlib.Path(path).read_text() or "null")
    return profiles


def save_config(path: str, profiles: list[dict]) -> None:
    """Save WLAN configuration to a file.

    Args:
        path: Path to file where WLAN profiles should be saved.
        profiles: WLAN profiles to save to the file.

    Raises:
        Exception on failure to save.
    """
    tmp = pathlib.Path(f"{path}.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(profiles))
    tmp.rename(path)


def _start_configurator(
    wlan: network.WLAN,
    config_path: str,
    ssid: str,
    password: str,
    security: int = 0,
    host: str = "0.0.0.0",
    port: int = 80,
    hostname: str | None = None,
    on_new_config: Callable | None = None,
) -> network.WLAN:
    """Start WLAN configuration application, and shutdown when a new connection is successfully configured."""
    wlan_ap = network.WLAN(network.AP_IF)
    wlan_ap.config(essid=ssid)
    if password and security:
        wlan_ap.config(password=password, security=security)
    wlan_ap.active(True)
    logger.info(f"Started WLAN AP for device configuration on: {host}:{port} SSID: {ssid} Password: {password}")
    logger.info(f"Connect to WLAN configuration page via browser at: http://{wlan_ap.ifconfig()[0]}:{port}/configure")
    wlan_ap_app = WLANConfigurationApp(wlan, config_path, hostname=hostname, on_new_config=on_new_config)
    wlan_ap_app.run(host=host, port=port)
    wlan_ap.active(False)
    logger.info(f"Shutdown WLAN AP due to successful connection to: {wlan.config('ssid')}")
