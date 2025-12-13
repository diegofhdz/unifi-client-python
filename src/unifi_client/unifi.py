import requests
from typing import Optional, Any
import logging
from datetime import datetime, timedelta
from threading import Lock
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


class UniFiApiError(Exception):
    """Custom exception for UniFi API errors"""

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

