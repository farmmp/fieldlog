# fieldlog

Lightweight structured logging library optimized for edge devices in low-connectivity environments.

---

## Installation

```bash
pip install fieldlog
```

Or install from source:

```bash
git clone https://github.com/yourusername/fieldlog.git && cd fieldlog && pip install .
```

---

## Usage

```python
import fieldlog

logger = fieldlog.Logger(
    output="logs/device.log",
    format="json",
    buffer_size=50,        # batch writes to reduce I/O
    flush_on_error=True    # always flush on critical events
)

logger.info("sensor_reading", value=42.7, unit="celsius", device_id="node-03")
logger.warning("low_battery", level=12, device_id="node-03")
logger.error("connection_failed", retries=5, device_id="node-03")
```

**Example output:**

```json
{"ts": "2024-05-10T08:32:11Z", "level": "INFO", "event": "sensor_reading", "value": 42.7, "unit": "celsius", "device_id": "node-03"}
{"ts": "2024-05-10T08:32:14Z", "level": "WARNING", "event": "low_battery", "level_pct": 12, "device_id": "node-03"}
```

Logs are buffered locally and flushed based on size or interval, making `fieldlog` resilient to intermittent connectivity and suitable for resource-constrained hardware.

---

## Features

- Structured JSON logging with arbitrary key-value fields
- Configurable write buffering to minimize disk I/O
- Automatic log rotation for storage-limited devices
- Zero heavy dependencies — stdlib only

---

## License

MIT © 2024 fieldlog contributors