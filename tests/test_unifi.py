import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import requests
from unifi_client.unifi import UniFiApiClient, UniFiApiError


class TestUniFiApiClientInit:
    """Test client initialization"""

    def test_init_with_valid_api_key(self):
        client = UniFiApiClient(api_key="test-api-key")
        assert client.api_key == "test-api-key"
        assert client.api_version == "v1"
        assert client.base_url == "https://api.ui.com/v1"
        assert client.timeout == 30

    def test_init_with_custom_params(self):
        client = UniFiApiClient(
            api_key="test-key",
            api_version="v2",
            timeout=60,
            session_ttl_minutes=30
        )
        assert client.api_version == "v2"
        assert client.timeout == 60
        assert client.session_ttl == timedelta(minutes=30)

    def test_init_with_empty_api_key_raises_error(self):
        with pytest.raises(ValueError, match="API key cannot be empty"):
            UniFiApiClient(api_key="")

    def test_init_with_none_api_key_raises_error(self):
        with pytest.raises(ValueError, match="API key cannot be empty"):
            UniFiApiClient(api_key=None)


class TestSessionManagement:
    """Test session creation and management"""

    def test_session_creates_new_session(self):
        client = UniFiApiClient(api_key="test-key")
        session = client.session
        assert session is not None
        assert isinstance(session, requests.Session)
        assert session.headers["X-API-Key"] == "test-key"
        assert session.headers["Accept"] == "application/json"

    def test_session_reuses_existing_session(self):
        client = UniFiApiClient(api_key="test-key")
        session1 = client.session
        session2 = client.session
        assert session1 is session2

    def test_session_refreshes_after_ttl(self):
        client = UniFiApiClient(api_key="test-key", session_ttl_minutes=0)
        session1 = client.session
        # Force time to pass
        client._session_created_at = datetime.now() - timedelta(minutes=1)
        session2 = client.session
        assert session1 is not session2

    def test_refresh_session_closes_old_session(self):
        client = UniFiApiClient(api_key="test-key")
        old_session = client.session
        old_session.close = Mock()
        
        client.refresh_session()
        
        old_session.close.assert_called_once()
        assert client._session is None

    def test_context_manager_closes_session(self):
        with UniFiApiClient(api_key="test-key") as client:
            session = client.session
            session.close = Mock()
        
        session.close.assert_called()


class TestValidation:
    """Test validation helper methods"""

    def test_validate_rfc3339_with_z_suffix(self):
        client = UniFiApiClient(api_key="test-key")
        timestamp = "2024-03-15T14:30:45.123Z"
        result = client._validate_rfc3339(timestamp)
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

    def test_validate_rfc3339_with_timezone_offset(self):
        client = UniFiApiClient(api_key="test-key")
        timestamp = "2024-03-15T14:30:45.123+05:30"
        result = client._validate_rfc3339(timestamp)
        assert isinstance(result, datetime)

    def test_validate_rfc3339_with_invalid_format_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="Invalid RFC3339 timestamp format"):
            client._validate_rfc3339("2024-03-15")

    def test_validate_timestamp_range_valid(self):
        client = UniFiApiClient(api_key="test-key")
        begin = "2024-03-15T10:00:00.000Z"
        end = "2024-03-15T14:00:00.000Z"
        # Should not raise
        client._validate_timestamp_range(begin, end)

    def test_validate_timestamp_range_invalid_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        begin = "2024-03-15T14:00:00.000Z"
        end = "2024-03-15T10:00:00.000Z"
        with pytest.raises(ValueError, match="must be strictly greater"):
            client._validate_timestamp_range(begin, end)

    def test_validate_timestamp_range_with_none_values(self):
        client = UniFiApiClient(api_key="test-key")
        # Should not raise
        client._validate_timestamp_range(None, None)
        client._validate_timestamp_range("2024-03-15T10:00:00.000Z", None)
        client._validate_timestamp_range(None, "2024-03-15T14:00:00.000Z")


class TestMakeRequest:
    """Test centralized request handling"""

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_success(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = UniFiApiClient(api_key="test-key")
        result = client._make_request("GET", "hosts")

        assert result == {"data": "test"}
        mock_request.assert_called_once()

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_with_params(self, mock_request):
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = UniFiApiClient(api_key="test-key")
        params = {"pageSize": "10"}
        client._make_request("GET", "hosts", params=params)

        call_args = mock_request.call_args
        assert call_args.kwargs["params"] == params

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_retries_on_401(self, mock_request):
        # First call returns 401, second call succeeds
        error_response = Mock()
        error_response.status_code = 401
        error_response.text = "Unauthorized"
        
        success_response = Mock()
        success_response.json.return_value = {"data": "test"}
        success_response.raise_for_status = Mock()

        mock_request.side_effect = [
            requests.HTTPError(response=error_response),
            success_response
        ]

        client = UniFiApiClient(api_key="test-key")
        with patch.object(client, 'refresh_session'):
            result = client._make_request("GET", "hosts")
        
        assert result == {"data": "test"}
        assert mock_request.call_count == 2

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_timeout_raises_error(self, mock_request):
        mock_request.side_effect = requests.Timeout()

        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(UniFiApiError, match="timed out"):
            client._make_request("GET", "hosts")

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_http_error_raises_unified_error(self, mock_request):
        error_response = Mock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        mock_request.side_effect = requests.HTTPError(response=error_response)

        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(UniFiApiError, match="API request failed: 500"):
            client._make_request("GET", "hosts")

    @patch('unifi_client.unifi.requests.Session.request')
    def test_make_request_invalid_json_raises_error(self, mock_request):
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response

        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(UniFiApiError, match="Invalid JSON response"):
            client._make_request("GET", "hosts")


class TestListHosts:
    """Test list_hosts endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_hosts_default_params(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.list_hosts()

        mock_request.assert_called_once_with(
            "GET", "hosts", params={"pageSize": "10"}
        )
        assert result == {"data": []}

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_hosts_with_custom_page_size(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        client.list_hosts(page_size=50)

        call_args = mock_request.call_args
        assert call_args[1]["params"]["pageSize"] == "50"

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_hosts_with_next_token(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        client.list_hosts(next_token="token123")

        call_args = mock_request.call_args
        assert call_args[1]["params"]["nextToken"] == "token123"

    def test_list_hosts_invalid_page_size_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="page_size must be between 1 and 100"):
            client.list_hosts(page_size=101)

        with pytest.raises(ValueError, match="page_size must be between 1 and 100"):
            client.list_hosts(page_size=0)


class TestGetHostById:
    """Test get_host_by_id endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_get_host_by_id_success(self, mock_request):
        mock_request.return_value = {"id": "host123", "name": "Test Host"}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.get_host_by_id("host123")

        mock_request.assert_called_once_with("GET", "hosts/host123")
        assert result["id"] == "host123"

    def test_get_host_by_id_empty_id_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="host_id cannot be empty"):
            client.get_host_by_id("")


class TestListSites:
    """Test list_sites endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_sites_success(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.list_sites()

        mock_request.assert_called_once_with(
            "GET", "sites", params={"pageSize": "10"}
        )


class TestListDevices:
    """Test list_devices endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_devices_with_time_filter(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        timestamp = "2024-03-15T14:30:45.123Z"
        client.list_devices(time=timestamp)

        call_args = mock_request.call_args
        assert call_args[1]["params"]["time"] == timestamp

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_devices_with_host_ids(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        client.list_devices(host_ids=["host1", "host2"])

        call_args = mock_request.call_args
        assert call_args[1]["params"]["hostIds"] == "host1,host2"

    def test_list_devices_with_invalid_time_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="Invalid RFC3339 timestamp"):
            client.list_devices(time="invalid-timestamp")


class TestGetIspMetrics:
    """Test get_isp_metrics endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_get_isp_metrics_with_duration(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        client.get_isp_metrics(type="5m", duration="24h")

        call_args = mock_request.call_args
        assert call_args[1]["params"]["duration"] == "24h"

    @patch.object(UniFiApiClient, '_make_request')
    def test_get_isp_metrics_with_timestamps(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        begin = "2024-03-15T10:00:00.000Z"
        end = "2024-03-15T14:00:00.000Z"
        client.get_isp_metrics(begin_timestamp=begin, end_timestamp=end)

        call_args = mock_request.call_args
        assert call_args[1]["params"]["beginTimestamp"] == begin
        assert call_args[1]["params"]["endTimestamp"] == end

    def test_get_isp_metrics_invalid_type_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="must be either '5m' or '1h'"):
            client.get_isp_metrics(type="10m")

    def test_get_isp_metrics_duration_with_timestamps_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="cannot be used with"):
            client.get_isp_metrics(
                duration="24h",
                begin_timestamp="2024-03-15T10:00:00.000Z"
            )


class TestQueryIspMetrics:
    """Test query_isp_metrics endpoint"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_query_isp_metrics_with_filters(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        client.query_isp_metrics(
            type="5m",
            site_ids=["site1", "site2"],
            host_ids=["host1"]
        )

        call_args = mock_request.call_args
        assert call_args[0] == ("POST", "ea/isp-metrics/5m/query")
        assert "siteIds" in call_args[1]["json"]
        assert "hostIds" in call_args[1]["json"]


class TestSdWanMethods:
    """Test SD-WAN related endpoints"""

    @patch.object(UniFiApiClient, '_make_request')
    def test_list_sd_wan_configs(self, mock_request):
        mock_request.return_value = {"data": []}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.list_sd_wan_configs()

        mock_request.assert_called_once_with("GET", "ea/sd-wan-configs")

    @patch.object(UniFiApiClient, '_make_request')
    def test_get_sd_wan_config_by_id(self, mock_request):
        mock_request.return_value = {"id": "config123"}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.get_sd_wan_config_by_id("config123")

        mock_request.assert_called_once_with("GET", "ea/sd-wan-configs/config123")

    def test_get_sd_wan_config_by_id_empty_raises_error(self):
        client = UniFiApiClient(api_key="test-key")
        with pytest.raises(ValueError, match="config_id cannot be empty"):
            client.get_sd_wan_config_by_id("")

    @patch.object(UniFiApiClient, '_make_request')
    def test_get_sd_wan_config_status(self, mock_request):
        mock_request.return_value = {"status": "active"}
        
        client = UniFiApiClient(api_key="test-key")
        result = client.get_sd_wan_config_status("config123")

        mock_request.assert_called_once_with("GET", "ea/sd-wan-configs/config123/status")


class TestCleanup:
    """Test resource cleanup"""

    def test_close_closes_session(self):
        client = UniFiApiClient(api_key="test-key")
        session = client.session
        session.close = Mock()
        
        client.close()
        
        session.close.assert_called_once()
        assert client._session is None

    def test_del_closes_session(self):
        client = UniFiApiClient(api_key="test-key")
        session = client.session
        session.close = Mock()
        
        del client
        
        session.close.assert_called()
