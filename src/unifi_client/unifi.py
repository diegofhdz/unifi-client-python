import requests
import logging
from datetime import datetime, timedelta
from threading import Lock
from requests.adapters import HTTPAdapter
from typing import Optional, Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class UniFiApiError(Exception):
    """
    Custom exception for UniFi API errors
    """
    pass


class UniFiApiClient:
    def __init__(
        self,
        api_key: str,
        api_version: str = "v1",
        timeout: int = 30,
        session_ttl_minutes: int = 55,
    ) -> None:
        if not api_key:
            raise ValueError("API key cannot be empty")

        self.api_key = api_key
        self.api_version = api_version
        self.base_url = f"https://api.ui.com/{self.api_version}"
        self.timeout = timeout
        self.session_ttl = timedelta(minutes=session_ttl_minutes)

        self._session: Optional[requests.Session] = None
        self._session_created_at: Optional[datetime] = None
        self._lock = Lock()

    @property
    def session(self) -> requests.Session:
        """Get or create session with automatic refresh"""
        with self._lock:
            now = datetime.now()

            # Create new session if doesn't exist or expired
            if (
                self._session is None
                or self._session_created_at is None
                or now - self._session_created_at > self.session_ttl
            ):
                if self._session:
                    logger.info("Session expired, creating new session")
                    self._session.close()

                self._session = self._create_session()
                self._session_created_at = now
                logger.debug(f"New session created at {now}")

            return self._session

    def _create_session(self) -> requests.Session:
        """Create a new configured session"""
        session = requests.Session()
        session.headers.update(
            {
                "Accept": "application/json",
                "X-API-Key": self.api_key,
                "User-Agent": "UniFiApiClient/1.0",
            }
        )

        adapter = HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=3, pool_block=False
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def refresh_session(self) -> None:
        """Manually force session refresh"""
        with self._lock:
            if self._session:
                self._session.close()
            self._session = None
            self._session_created_at = None
        logger.info("Session manually refreshed")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Centralized request handler with automatic retry on auth failures.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            **kwargs: Additional arguments to pass to requests

        Returns:
            Parsed JSON response

        Raises:
            UniFiApiError: If the API request fails
        """
        url = f"{self.base_url}/{endpoint}"

        def _attempt_request():
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()

        try:
            return _attempt_request()

        except requests.HTTPError as e:
            # Retry once on auth errors
            if e.response.status_code in (401, 403):
                logger.warning(f"Authentication error (HTTP {e.response.status_code}), refreshing session")
                self.refresh_session()
                try:
                    return _attempt_request()
                except requests.HTTPError as retry_error:
                    logger.error(f"Retry failed: {retry_error.response.status_code} - {retry_error.response.text}")
                    raise UniFiApiError(f"API request failed after retry: {retry_error.response.status_code}") from retry_error

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}") from e

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError(f"Request timed out after {self.timeout} seconds")

        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}") from e

        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API") from e

    @staticmethod
    def _validate_page_size(func: Callable) -> Callable:
        """Decorator to validate page_size parameter"""
        @wraps(func)
        def wrapper(self, *args, page_size: int = 10, **kwargs):
            if not 1 <= page_size <= 100:
                raise ValueError("page_size must be between 1 and 100")
            return func(self, *args, page_size=page_size, **kwargs)
        return wrapper

    def _validate_rfc3339(self, timestamp: str) -> datetime:
        """
        Validate and parse RFC3339 timestamp.

        Args:
            timestamp: RFC3339 formatted timestamp string

        Returns:
            Parsed datetime object

        Raises:
            ValueError: If timestamp format is invalid
        """
        try:
            # Handle both Z and timezone offset formats
            if timestamp.endswith('Z'):
                return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                # Remove colon from timezone for strptime
                timestamp_clean = timestamp[:-3] + timestamp[-2:]
                return datetime.strptime(timestamp_clean, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError as e:
            raise ValueError(f"Invalid RFC3339 timestamp format: {timestamp}. Expected format: YYYY-MM-DDTHH:MM:SS.sssZ or YYYY-MM-DDTHH:MM:SS.sss±HH:MM") from e

    def _validate_timestamp_range(
        self,
        begin_timestamp: Optional[str],
        end_timestamp: Optional[str]
    ) -> None:
        """
        Validate that end_timestamp > begin_timestamp.

        Args:
            begin_timestamp: Start timestamp in RFC3339 format
            end_timestamp: End timestamp in RFC3339 format

        Raises:
            ValueError: If end_timestamp is not greater than begin_timestamp
        """
        if not (begin_timestamp and end_timestamp):
            return

        begin_dt = self._validate_rfc3339(begin_timestamp)
        end_dt = self._validate_rfc3339(end_timestamp)

        if end_dt <= begin_dt:
            raise ValueError("'end_timestamp' must be strictly greater than 'begin_timestamp'")

    @_validate_page_size
    def list_hosts(
        self,
        page_size: int = 10,
        next_token: Optional[str] = None
    ) -> dict[str, Any]:
        """
        List UniFi hosts with pagination support.

        Args:
            page_size: Number of results per page (1-100)
            next_token: Token for pagination

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        params = {"pageSize": str(page_size)}
        if next_token:
            params["nextToken"] = next_token

        return self._make_request("GET", "hosts", params=params)

    def get_host_by_id(self, host_id: str) -> dict[str, Any]:
        """
        Retrieves detailed information about a specific host by ID.

        Args:
            host_id: Unique identifier of the host

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If host_id is empty
        """
        if not host_id:
            raise ValueError("host_id cannot be empty")

        return self._make_request("GET", f"hosts/{host_id}")

    @_validate_page_size
    def list_sites(
        self,
        page_size: int = 10,
        next_token: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Retrieves a list of all sites (from hosts running the UniFi Network application)
        associated with the UI account making the API call.

        Args:
            page_size: Number of results per page (1-100)
            next_token: Token for pagination

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        params = {"pageSize": str(page_size)}
        if next_token:
            params["nextToken"] = next_token

        return self._make_request("GET", "sites", params=params)

    @_validate_page_size
    def list_devices(
        self,
        time: Optional[str] = None,
        host_ids: Optional[list[str]] = None,
        page_size: int = 10,
        next_token: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Retrieves a list of UniFi devices managed by hosts where the UI account
        making the API call is the owner or a super admin.

        Args:
            time: Last processed timestamp of devices in RFC3339 format. Example: 2025-06-17T02:45:58Z
            host_ids: List of host IDs to filter the results
            page_size: Number of results per page (1-100)
            next_token: Token for pagination

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid or time format is invalid
        """
        if time:
            self._validate_rfc3339(time)

        params = {"pageSize": str(page_size)}
        if next_token:
            params["nextToken"] = next_token
        if time:
            params["time"] = time
        if host_ids:
            # Adjust format based on actual API specification
            params["hostIds"] = ",".join(host_ids)

        return self._make_request("GET", "devices", params=params)

    def get_isp_metrics(
        self,
        type: str = "5m",
        begin_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        duration: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Retrieves ISP metrics data for all sites linked to the UI account's API key.
        5-minute interval metrics are available for at least 24 hours, and 1-hour
        interval metrics are available for at least 30 days.

        Args:
            type: Specifies whether metrics are returned using 5m or 1h intervals
            begin_timestamp: The earliest timestamp to retrieve data from (RFC3339 format)
            end_timestamp: The latest timestamp to retrieve data up to (RFC3339 format)
            duration: Specifies the time range of metrics to retrieve, starting from when
                     the request is made. Supports 24h for 5-minute metrics, and 7d or 30d
                     for 1-hour metrics. Cannot be used with beginTimestamp or endTimestamp.

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If parameters are invalid
        """
        # Validation
        if type not in ("5m", "1h"):
            raise ValueError("'type' parameter must be either '5m' or '1h'")

        if duration and (begin_timestamp or end_timestamp):
            raise ValueError("'duration' cannot be used with begin_timestamp or end_timestamp")

        # Validate and compare timestamps
        if begin_timestamp or end_timestamp:
            self._validate_timestamp_range(begin_timestamp, end_timestamp)

        # Build params
        params = {}
        if duration:
            params["duration"] = duration
        if begin_timestamp:
            params["beginTimestamp"] = begin_timestamp
        if end_timestamp:
            params["endTimestamp"] = end_timestamp

        return self._make_request("GET", f"ea/isp-metrics/{type}", params=params)

    def query_isp_metrics(
        self,
        type: str = "5m",
        begin_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
        duration: Optional[str] = None,
        site_ids: Optional[list[str]] = None,
        host_ids: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Retrieves ISP metrics data based on specific query parameters.
        5-minute interval metrics are available for at least 24 hours, and 1-hour
        interval metrics are available for at least 30 days.

        Note: If the UI account lacks access to all requested sites, a 502 error is returned.
        If partial access is granted, the response will include status: partialSuccess.

        Args:
            type: Specifies whether metrics are returned using 5m or 1h intervals
            begin_timestamp: The earliest timestamp to retrieve data from (RFC3339 format)
            end_timestamp: The latest timestamp to retrieve data up to (RFC3339 format)
            duration: Specifies the time range of metrics to retrieve, starting from when
                     the request is made. Supports 24h for 5-minute metrics, and 7d or 30d
                     for 1-hour metrics. Cannot be used with beginTimestamp or endTimestamp.
            site_ids: List of site IDs to filter the results
            host_ids: List of host IDs to filter the results

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If parameters are invalid
        """
        # Validation
        if type not in ("5m", "1h"):
            raise ValueError("'type' parameter must be either '5m' or '1h'")

        if duration and (begin_timestamp or end_timestamp):
            raise ValueError("'duration' cannot be used with begin_timestamp or end_timestamp")

        # Validate and compare timestamps
        if begin_timestamp or end_timestamp:
            self._validate_timestamp_range(begin_timestamp, end_timestamp)

        # Build request body
        body = {}
        if duration:
            body["duration"] = duration
        if begin_timestamp:
            body["beginTimestamp"] = begin_timestamp
        if end_timestamp:
            body["endTimestamp"] = end_timestamp
        if site_ids:
            body["siteIds"] = site_ids
        if host_ids:
            body["hostIds"] = host_ids

        return self._make_request("POST", f"ea/isp-metrics/{type}/query", json=body)

    def list_sd_wan_configs(self) -> dict[str, Any]:
        """
        Retrieves a list of all SD-WAN configurations associated with the UI account
        making the API call.

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
        """
        return self._make_request("GET", "ea/sd-wan-configs")

    def get_sd_wan_config_by_id(self, config_id: str) -> dict[str, Any]:
        """
        Retrieves detailed information about a specific SD-WAN configuration by ID.

        Args:
            config_id: Unique identifier of the SD-WAN configuration

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If config_id is empty
        """
        if not config_id:
            raise ValueError("config_id cannot be empty")

        return self._make_request("GET", f"ea/sd-wan-configs/{config_id}")

    def get_sd_wan_config_status(self, config_id: str) -> dict[str, Any]:
        """
        Retrieves the status of a specific SD-WAN configuration, including deployment
        progress, errors, and associated hubs.

        Args:
            config_id: Unique identifier of the SD-WAN configuration

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If config_id is empty
        """
        if not config_id:
            raise ValueError("config_id cannot be empty")

        return self._make_request("GET", f"ea/sd-wan-configs/{config_id}/status")

    def close(self) -> None:
        """Close the session"""
        with self._lock:
            if self._session:
                self._session.close()
                self._session = None
                self._session_created_at = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()