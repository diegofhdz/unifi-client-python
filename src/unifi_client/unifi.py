import requests
import logging
from datetime import datetime, timedelta
from threading import Lock
from requests.adapters import HTTPAdapter
from typing import Optional, Any

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

    def list_hosts(
        self, page_size: int = 10, next_token: Optional[str] = None
    ) -> dict[str, str]:
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
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        url = f"{self.base_url}/hosts"
        params = {"pageSize": str(page_size)}

        if next_token:
            params["nextToken"] = next_token

        try:
            response = self.session.get(
                url=url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            # If 401/403, might be auth issue - try refresh once
            if e.response.status_code in (401, 403):
                logger.warning("Authentication error, attempting session refresh")
                self.refresh_session()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}")

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError("Request timed out")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API")
        
    def get_host_by_id(self, host_id: str) -> dict[str, str]:
        """
        Retrieves detailed information about a specific host by ID.
        
        Args:
            host_id: Unique identifier of the host

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        if len(host_id) == 0:
            raise ValueError("Please enter a valid host_id")
        
        url = f"{self.base_url}/{host_id}"
        
        try:
            response = self.session.get(
                url=url, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            # If 401/403, might be auth issue - try refresh once
            if e.response.status_code in (401, 403):
                logger.warning("Authentication error, attempting session refresh")
                self.refresh_session()
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}")

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError("Request timed out")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API")
        
    def list_sites(
        self, page_size: int = 10, next_token: Optional[str] = None
    ) -> dict[str, str]:
        """
        Retrieves a list of all sites (from hosts running the UniFi Network application) associated with the UI account making the API call.

        Args:
            page_size: Number of results per page (1-100)
            next_token: Token for pagination

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        url = f"{self.base_url}/sites"
        params = {"pageSize": str(page_size)}

        if next_token:
            params["nextToken"] = next_token

        try:
            response = self.session.get(
                url=url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            # If 401/403, might be auth issue - try refresh once
            if e.response.status_code in (401, 403):
                logger.warning("Authentication error, attempting session refresh")
                self.refresh_session()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}")

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError("Request timed out")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API")

    def list_devices(
        self, time: Optional[str] = None, host_ids: Optional[list[str]] = None , page_size: int = 10, next_token: Optional[str] = None
    ) -> dict[str, str]:
        """
        Retrieves a list of UniFi devices managed by hosts where the UI account making the API call is the owner or a super admin.

        Args:
            page_size: Number of results per page (1-100)
            next_token: Token for pagination
            time: Last processed timestamp of devices in RFC3339 format. Example: 2025-06-17T02:45:58Z
            host_ids: List of host IDs to filter the results

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        
        # TODO: Do String -> Datetime format check

        url = f"{self.base_url}/sites"
        params = {"pageSize": str(page_size)}

        if next_token:
            params["nextToken"] = next_token

        try:
            response = self.session.get(
                url=url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            # If 401/403, might be auth issue - try refresh once
            if e.response.status_code in (401, 403):
                logger.warning("Authentication error, attempting session refresh")
                self.refresh_session()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}")

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError("Request timed out")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API")
    
    def get_isp_metrics(
        self, type: str = "5m", begin_timestamp: Optional[str] = None, end_timestamp: Optional[str] = None, duration: Optional[str] = None 
    ) -> dict[str, str]:
        """
        Retrieves ISP metrics data for all sites linked to the UI account's API key. 
        5-minute interval metrics are available for at least 24 hours, and 1-hour interval metrics are available for at least 30 days.

        Args:
            type: Specifies whether metrics are returned using 5m or 1h intervals.
            begin_timestamp: The earliest timestamp to retrieve data from (RFC3339 format)
            end_timestamp: The latest timestamp to retrieve data up to (RFC3339 format)
            duration: Specifies the time range of metrics to retrieve, starting from when the request is made. 
            Supports 24h for 5-minute metrics, and 7d or 30d for 1-hour metrics. 
            This parameter cannot be used with beginTimestamp or endTimestamp.

        Returns:
            Parsed JSON response as dictionary

        Raises:
            UniFiApiError: If the API request fails
            ValueError: If page_size is invalid
        """
        if type not in ("5m", "1h"):
            raise ValueError("type parameter must be either '5m' or '1h'")
        
        if duration and (begin_timestamp or end_timestamp):
            raise ValueError("Duration parameter cannot be used with begin_timestamp or end_timestamp.")
        
        if (begin_timestamp and end_timestamp):
            pass
            # Assert Begin timestamp < end_timestamp

        # TODO: Do String -> Datetime format check

        base_url = f"{self.base_url.split('/')[-2]}/ea"
        url = f"{base_url}/isp-metrics/{type}"

        params = {}

        if duration:
            params["duration"] = duration

        if begin_timestamp:
            params["beginTimestamp"] = begin_timestamp
        
        if end_timestamp: 
            params["endTimestaml"] = end_timestamp

        try:
            response = self.session.get(
                url=url, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            # If 401/403, might be auth issue - try refresh once
            if e.response.status_code in (401, 403):
                logger.warning("Authentication error, attempting session refresh")
                self.refresh_session()
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise UniFiApiError(f"API request failed: {e.response.status_code}")

        except requests.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            raise UniFiApiError("Request timed out")
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise UniFiApiError(f"Request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise UniFiApiError("Invalid JSON response from API")

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

