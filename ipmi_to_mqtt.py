#!/usr/bin/env python3
"""Publish IPMI sensor data to MQTT using Home Assistant MQTT discovery."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Iterable

import paho.mqtt.client as mqtt


VALUE_RE = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(.*)\s*$")


@dataclass(frozen=True)
class SensorReading:
    name: str
    value: float
    unit: str

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", self.name.lower()).strip("_")


def parse_ipmitool_output(text: str) -> list[SensorReading]:
    """Parse output from `ipmitool sensor` into numeric readings."""
    readings: list[SensorReading] = []

    for line in text.splitlines():
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue

        name, raw_value, status = parts[0], parts[1], parts[2].lower()
        if not name or raw_value.lower() in {"na", "no reading", "disabled"}:
            continue
        if status not in {"ok", "ns", "nr", "nc", "cr"}:
            continue

        match = VALUE_RE.match(raw_value)
        if not match:
            continue

        value = float(match.group(1))
        unit = match.group(2).strip()
        readings.append(SensorReading(name=name, value=value, unit=unit))

    return readings


def unit_metadata(unit: str) -> dict[str, str]:
    u = unit.lower()
    if "degrees c" in u or u == "c":
        return {"unit_of_measurement": "°C", "device_class": "temperature", "state_class": "measurement"}
    if "volts" in u or u == "v":
        return {"unit_of_measurement": "V", "device_class": "voltage", "state_class": "measurement"}
    if "amps" in u or u == "a":
        return {"unit_of_measurement": "A", "device_class": "current", "state_class": "measurement"}
    if "watts" in u or u == "w":
        return {"unit_of_measurement": "W", "device_class": "power", "state_class": "measurement"}
    if "rpm" in u:
        return {"unit_of_measurement": "RPM", "state_class": "measurement"}
    if "percent" in u or u == "%":
        return {"unit_of_measurement": "%", "state_class": "measurement"}
    return {"unit_of_measurement": unit, "state_class": "measurement"} if unit else {"state_class": "measurement"}


def run_ipmitool(command: str) -> str:
    proc = subprocess.run(shlex.split(command), check=True, capture_output=True, text=True)
    return proc.stdout


def publish_discovery(client: mqtt.Client, sensor: SensorReading, prefix: str, node_id: str) -> None:
    object_id = f"{node_id}_{sensor.slug}"
    config_topic = f"{prefix}/sensor/{node_id}/{object_id}/config"
    state_topic = f"{prefix}/sensor/{node_id}/{object_id}/state"

    payload = {
        "name": f"IPMI {sensor.name}",
        "uniq_id": object_id,
        "stat_t": state_topic,
        "dev": {
            "ids": [node_id],
            "name": f"IPMI {node_id}",
            "mf": "IPMI",
            "mdl": "BMC",
        },
    }
    payload.update(unit_metadata(sensor.unit))

    client.publish(config_topic, json.dumps(payload), qos=1, retain=True)


def publish_states(client: mqtt.Client, sensors: Iterable[SensorReading], prefix: str, node_id: str) -> None:
    for sensor in sensors:
        object_id = f"{node_id}_{sensor.slug}"
        state_topic = f"{prefix}/sensor/{node_id}/{object_id}/state"
        client.publish(state_topic, payload=sensor.value, qos=1, retain=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mqtt-host", required=True, help="MQTT broker host")
    p.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    p.add_argument("--mqtt-username", help="MQTT username")
    p.add_argument("--mqtt-password", help="MQTT password")
    p.add_argument("--topic-prefix", default="homeassistant", help="Home Assistant discovery prefix")
    p.add_argument("--node-id", default="ipmi", help="Node identifier for Home Assistant discovery")
    p.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")
    p.add_argument(
        "--ipmitool-cmd",
        default="ipmitool sensor",
        help="Command to run for sensor output (example: \"ipmitool -I lanplus -H 10.0.0.2 -U user -P pass sensor\")",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if args.mqtt_username:
        client.username_pw_set(args.mqtt_username, args.mqtt_password)

    client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    client.loop_start()

    published_discovery: set[str] = set()

    while True:
        try:
            output = run_ipmitool(args.ipmitool_cmd)
            sensors = parse_ipmitool_output(output)
            for sensor in sensors:
                if sensor.slug not in published_discovery:
                    publish_discovery(client, sensor, args.topic_prefix, args.node_id)
                    published_discovery.add(sensor.slug)
            publish_states(client, sensors, args.topic_prefix, args.node_id)
        except subprocess.CalledProcessError as exc:
            print(f"ipmitool command failed ({exc.returncode}): {exc.stderr.strip()}")
        except Exception as exc:  # keep service alive
            print(f"Unexpected error: {exc}")

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
