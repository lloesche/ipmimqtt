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
  --ipmitool-cmd "ipmitool -I lanplus -H 192.168.1.50 -U ADMIN -P PASSWORD sensor"
```

## Notes

- The script publishes discovery payloads to `homeassistant/sensor/.../config` (retained).
- State payloads are published as numeric values to `homeassistant/sensor/.../state`.
- Supported common units: `degrees C`, `Volts`, `Amps`, `Watts`, `RPM`, and `%`.
