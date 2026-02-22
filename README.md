# ipmi-to-mqtt

Tiny Python script to poll `ipmitool sensor` and publish readings to MQTT using Home Assistant MQTT discovery.

## Install

```bash
python3 -m pip install paho-mqtt
```

## Run

```bash
python3 ipmi_to_mqtt.py \
  --mqtt-host 192.168.1.10 \
  --mqtt-username mqttuser \
  --mqtt-password mqttpass \
  --node-id server-r720 \
  --verbose \
  --ipmitool-cmd "ipmitool -I lanplus -H 192.168.1.50 -U ADMIN -P PASSWORD sensor"
```

Use `--verbose` to enable detailed debug logs for command execution, parsing, and MQTT publish topics/payloads.

## Home Assistant configuration

This script uses **MQTT Discovery**, so Home Assistant can auto-create entities.

### 1) Add/configure the MQTT integration

In Home Assistant:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Select **MQTT**.
3. Enter your broker host/port/credentials (must match `--mqtt-*` options used by this script).

If you configure MQTT in `configuration.yaml`, make sure discovery is enabled:

```yaml
mqtt:
  - broker: 192.168.1.10
    username: mqttuser
    password: mqttpass
    discovery: true
    discovery_prefix: homeassistant
```

> If your system already uses UI-based MQTT config, prefer that and do not duplicate YAML broker settings.

### 2) Ensure discovery prefix matches

- Script default: `--topic-prefix homeassistant`
- Home Assistant default discovery prefix: `homeassistant`

If you change one side, change the other to match.

### 3) Start the script and verify messages

Use an MQTT client to verify discovery/state topics are appearing:

```bash
mosquitto_sub -h 192.168.1.10 -u mqttuser -P mqttpass -t 'homeassistant/sensor/server-r720/#' -v
```

You should see:
- `.../config` retained JSON payloads (discovery)
- `.../state` numeric values (sensor readings)

### 4) Find entities in Home Assistant

After the first publish, entities should appear under:
- **Settings → Devices & Services → MQTT**
- Device name similar to `IPMI server-r720`
- Entities named like `IPMI CPU1 Temp`, etc.

## Troubleshooting

- **No entities appear**:
  - Confirm MQTT integration is connected.
  - Confirm discovery is enabled.
  - Confirm prefix matches script `--topic-prefix`.
- **Entities appear but no updates**:
  - Check script logs for `ipmitool` errors.
  - Verify `ipmitool` command works manually.
- **Old/stale entities**:
  - Discovery topics are retained by design; change `--node-id` to isolate a host, or clean retained config topics in broker.

## Notes

- The script publishes discovery payloads to `homeassistant/sensor/.../config` (retained).
- State payloads are published as numeric values to `homeassistant/sensor/.../state`.
- Supported common units: `degrees C`, `Volts`, `Amps`, `Watts`, `RPM`, and `%`.
