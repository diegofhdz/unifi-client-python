# UniFi Client Python

A Python client library for the [UniFi Site Manager API](https://developer.ui.com/site-manager-api/gettingstarted).

## Features

- 🔐 Automatic session management with configurable TTL
- 🔄 Automatic retry on authentication failures
- 🧵 Thread-safe session handling
- ✅ Comprehensive input validation
- 📝 Type hints for better IDE support
- 🐍 Context manager support for proper resource cleanup
- 🎯 Clean, intuitive API

## Installation

```bash
pip install unifi-client-python
```

### Development Installation

```bash
git clone https://github.com/yourusername/unifi-client-python.git
cd unifi-client-python
pip install -e ".[dev]"
```

## Quick Start

```python
from unifi_client import UniFiApiClient

# Initialize the client
client = UniFiApiClient(api_key="your-api-key-here")

# List all hosts
hosts = client.list_hosts(page_size=20)
print(hosts)

# Get a specific host
host = client.get_host_by_id("host-id")
print(host)

# List sites
sites = client.list_sites()
print(sites)

# Always close the client when done
client.close()
```

### Using Context Manager (Recommended)

```python
from unifi_client import UniFiApiClient

with UniFiApiClient(api_key="your-api-key-here") as client:
    hosts = client.list_hosts()
    print(hosts)
# Client is automatically closed
```

## API Reference

### Initialization

```python
client = UniFiApiClient(
    api_key="your-api-key",
    api_version="v1",          # Optional, default: "v1"
    timeout=30,                # Optional, default: 30 seconds
    session_ttl_minutes=55     # Optional, default: 55 minutes
)
```

### Available Methods

#### Hosts

```python
# List hosts with pagination
hosts = client.list_hosts(page_size=10, next_token=None)

# Get host by ID
host = client.get_host_by_id("host-id")
```

#### Sites

```python
# List sites
sites = client.list_sites(page_size=10, next_token=None)
```

#### Devices

```python
# List devices with optional filters
devices = client.list_devices(
    time="2024-03-15T14:30:45.123Z",  # Optional RFC3339 timestamp
    host_ids=["host1", "host2"],       # Optional list of host IDs
    page_size=10,
    next_token=None
)
```

#### ISP Metrics

```python
# Get ISP metrics with duration
metrics = client.get_isp_metrics(
    type="5m",           # "5m" or "1h"
    duration="24h"       # "24h", "7d", or "30d"
)

# Get ISP metrics with timestamp range
metrics = client.get_isp_metrics(
    type="1h",
    begin_timestamp="2024-03-15T00:00:00.000Z",
    end_timestamp="2024-03-15T23:59:59.999Z"
)

# Query ISP metrics with filters
metrics = client.query_isp_metrics(
    type="5m",
    site_ids=["site1", "site2"],
    host_ids=["host1"],
    duration="24h"
)
```

#### SD-WAN Configurations

```python
# List SD-WAN configurations
configs = client.list_sd_wan_configs()

# Get SD-WAN configuration by ID
config = client.get_sd_wan_config_by_id("config-id")

# Get SD-WAN configuration status
status = client.get_sd_wan_config_status("config-id")
```

## Error Handling

The client raises `UniFiApiError` for API-related errors:

```python
from unifi_client import UniFiApiClient, UniFiApiError

try:
    with UniFiApiClient(api_key="your-api-key") as client:
        hosts = client.list_hosts()
except UniFiApiError as e:
    print(f"API Error: {e}")
except ValueError as e:
    print(f"Validation Error: {e}")
```

## Advanced Features

### Session Management

The client automatically manages sessions with configurable TTL:

```python
client = UniFiApiClient(
    api_key="your-api-key",
    session_ttl_minutes=30  # Sessions refresh after 30 minutes
)

# Manually refresh session if needed
client.refresh_session()
```

### Automatic Retry

The client automatically retries requests once on 401/403 authentication errors after refreshing the session.

### Thread Safety

Session access is thread-safe using locks, making it safe to use the same client instance across multiple threads.

## Testing

Run tests with pytest:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=unifi_client --cov-report=html

# Run specific test file
pytest tests/test_unifi.py

# Run specific test
pytest tests/test_unifi.py::TestListHosts::test_list_hosts_default_params
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/unifi-client-python.git
cd unifi-client-python

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### Code Formatting

```bash
# Format code with black
black src/ tests/

# Check code style with flake8
flake8 src/ tests/

# Type checking with mypy
mypy src/
```

### Building the Package

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the distribution
twine check dist/*
```

### Publishing to PyPI

```bash
# Test PyPI (recommended first)
twine upload --repository testpypi dist/*

# Production PyPI
twine upload dist/*
```

## Requirements

- Python >= 3.8
- requests >= 2.31.0

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Changelog

### 0.1.0 (2024-XX-XX)

- Initial release
- Support for Hosts, Sites, Devices, ISP Metrics, and SD-WAN endpoints
- Automatic session management
- Thread-safe implementation
- Comprehensive test coverage

## Links

- [UniFi Site Manager API Documentation](https://developer.ui.com/site-manager-api/gettingstarted)
- [GitHub Repository](https://github.com/yourusername/unifi-client-python)
- [Issue Tracker](https://github.com/yourusername/unifi-client-python/issues)

## Support

For bugs, feature requests, or questions, please [open an issue](https://github.com/yourusername/unifi-client-python/issues) on GitHub.
