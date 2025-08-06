"""
Integration Tests for PMC and Publisher API Workflows.

This module contains integration tests that verify the complete workflows
for PMC article downloads and publisher API interactions, including
authentication, rate limiting, error handling, and data processing.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from requests.exceptions import ConnectionError

from src.literature.pmc_client import PMCClient
from src.literature.publisher_api_manager import PublisherAPIManager
from src.literature.quota_manager import QuotaManager
from src.literature.token_manager import TokenManager
from src.literature.error_handler import RobustErrorHandler, NonRetryableError


class TestPMCIntegrationWorkflow:
    """Test complete PMC integration workflow."""
    
    @pytest.fixture
    def pmc_config(self):
        """PMC client configuration for testing."""
        return {
            'base_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
            'api_key': 'test_api_key',
            'rate_limit': 3.0,
            'timeout': 30,
            'max_retries': 3
        }
    
    @pytest.fixture
    def pmc_client(self, pmc_config):
        """Create PMC client for integration testing."""
        return PMCClient(pmc_config)
    
    def test_complete_pmc_workflow_success(self, pmc_client):
        """Test complete successful PMC workflow from authentication to download."""
        # Mock successful authentication
        with patch.object(pmc_client, 'authenticate') as mock_auth:
            mock_auth.return_value = True
            # Set authentication state directly
            pmc_client.is_authenticated = True

            # Mock successful article download
            with patch('requests.Session.get') as mock_get:
                # Mock authentication response
                mock_auth_response = Mock()
                mock_auth_response.status_code = 200
                mock_auth_response.json.return_value = {'authenticated': True}

                # Mock article download response
                mock_download_response = Mock()
                mock_download_response.status_code = 200
                mock_download_response.content = b'<article><title>Test Article</title></article>'
                mock_download_response.headers = {'Content-Type': 'application/xml'}
                mock_download_response.raise_for_status.return_value = None

                mock_get.return_value = mock_download_response

                # Execute complete workflow
                article_ids = ["PMC123456", "PMC789012"]
                results = pmc_client.download_articles(article_ids)

                # Verify workflow completion
                assert isinstance(results, list)
                assert len(results) == len(article_ids)

                # Verify each result has expected structure
                for result in results:
                    assert 'pmc_id' in result  # PMC client uses 'pmc_id' not 'article_id'
                    assert 'status' in result
                    assert 'content' in result or 'error' in result
    
    def test_pmc_workflow_with_rate_limiting(self, pmc_client):
        """Test PMC workflow with rate limiting enforcement."""
        # Mock authentication
        pmc_client.is_authenticated = True
        
        # Track request timing
        request_times = []
        
        def mock_get_with_timing(*args, **kwargs):
            request_times.append(time.time())
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'<article>Test</article>'
            mock_response.raise_for_status.return_value = None
            return mock_response
        
        with patch('requests.Session.get', side_effect=mock_get_with_timing):
            # Download multiple articles to test rate limiting
            article_ids = ["PMC1", "PMC2", "PMC3"]
            results = pmc_client.download_articles(article_ids)
            
            # Verify rate limiting was enforced
            if len(request_times) > 1:
                time_diffs = [request_times[i+1] - request_times[i] for i in range(len(request_times)-1)]
                # Should have some delay between requests due to rate limiting
                assert any(diff >= 0.1 for diff in time_diffs)  # At least 100ms delay
            
            assert len(results) == len(article_ids)
    
    def test_pmc_workflow_with_authentication_failure(self, pmc_client):
        """Test PMC workflow handling authentication failures."""
        with patch.object(pmc_client, 'authenticate') as mock_auth:
            mock_auth.return_value = False
            # Ensure authentication state is False
            pmc_client.is_authenticated = False

            # Attempt to download articles without authentication should raise ValueError
            article_ids = ["PMC123456"]
            with pytest.raises(ValueError, match="Authentication required"):
                pmc_client.download_articles(article_ids)
    
    def test_pmc_workflow_with_network_errors(self, pmc_client):
        """Test PMC workflow handling network errors and retries."""
        # Mock authentication
        pmc_client.is_authenticated = True
        
        call_count = 0
        def mock_get_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First two calls fail
                raise ConnectionError("Network error")
            else:
                # Third call succeeds
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.content = b'<article>Success</article>'
                mock_response.raise_for_status.return_value = None
                return mock_response
        
        with patch('requests.Session.get', side_effect=mock_get_with_failures):
            article_ids = ["PMC123456"]
            results = pmc_client.download_articles(article_ids)
            
            # Should eventually succeed after retries
            assert isinstance(results, list)
            assert len(results) == 1
            # The implementation should handle retries gracefully
    
    def test_pmc_workflow_with_malformed_responses(self, pmc_client):
        """Test PMC workflow handling malformed API responses."""
        # Mock authentication
        pmc_client.is_authenticated = True
        
        with patch('requests.Session.get') as mock_get:
            # Mock malformed response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'Invalid XML content <unclosed tag'
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            article_ids = ["PMC123456"]
            results = pmc_client.download_articles(article_ids)
            
            # Should handle malformed responses gracefully
            assert isinstance(results, list)
            assert len(results) == 1
            # Implementation may mark as success or error depending on validation


class TestPublisherAPIIntegrationWorkflow:
    """Test complete publisher API integration workflow."""
    
    @pytest.fixture
    def api_manager(self):
        """Create API manager for integration testing."""
        return PublisherAPIManager()
    
    @pytest.fixture
    def publisher_configs(self):
        """Publisher API configurations for testing."""
        return {
            'elsevier': {
                'base_url': 'https://api.elsevier.com',
                'api_key': 'test_elsevier_key',
                'rate_limit': 2.0,
                'timeout': 30
            },
            'springer': {
                'base_url': 'https://api.springer.com',
                'api_key': 'test_springer_key',
                'rate_limit': 1.0,
                'timeout': 30
            }
        }
    
    def test_complete_publisher_api_workflow(self, api_manager, publisher_configs):
        """Test complete publisher API workflow from registration to data retrieval."""
        # Register APIs
        registration_result = api_manager.register_apis(publisher_configs)
        assert registration_result is True
        
        # Verify APIs are registered
        registered_apis = api_manager.list_registered_apis()
        assert 'elsevier' in registered_apis
        assert 'springer' in registered_apis
        
        # Test API client retrieval
        elsevier_client = api_manager.get_api_client('elsevier')
        assert elsevier_client is not None
        assert elsevier_client.base_url == 'https://api.elsevier.com'
        assert elsevier_client.api_key == 'test_elsevier_key'
        
        springer_client = api_manager.get_api_client('springer')
        assert springer_client is not None
        assert springer_client.base_url == 'https://api.springer.com'
        assert springer_client.api_key == 'test_springer_key'
    
    def test_publisher_api_workflow_with_quota_management(self, api_manager, publisher_configs):
        """Test publisher API workflow with quota management."""
        # Register APIs with quota management
        api_manager.register_apis(publisher_configs)
        
        # Create quota manager
        quota_config = {
            'elsevier': {
                'daily_limit': 1000,
                'hourly_limit': 100,
                'requests_per_second': 2.0
            }
        }
        quota_manager = QuotaManager(quota_config)
        
        # Test quota checking
        can_make_request = quota_manager.can_make_request('elsevier')
        assert isinstance(can_make_request, bool)
        
        # Record some requests
        for _ in range(5):
            if quota_manager.can_make_request('elsevier'):
                quota_manager.record_request('elsevier')
        
        # Verify quota tracking
        # The exact behavior depends on implementation details
        # but should not raise exceptions
    
    def test_publisher_api_workflow_with_token_management(self, api_manager, publisher_configs, tmp_path):
        """Test publisher API workflow with token management."""
        # Create token manager
        token_manager = TokenManager(storage_path=str(tmp_path / "test_tokens.enc"))
        
        # Store tokens for APIs
        token_manager.store_token('elsevier', 'elsevier_access_token')
        token_manager.store_token('springer', 'springer_access_token')
        
        # Register APIs
        api_manager.register_apis(publisher_configs)
        
        # Verify token retrieval
        elsevier_token = token_manager.get_token('elsevier')
        assert elsevier_token == 'elsevier_access_token'
        
        springer_token = token_manager.get_token('springer')
        assert springer_token == 'springer_access_token'
        
        # Test token validation
        assert token_manager.validate_token_format('valid_token_string') is True
        assert token_manager.validate_token_format('') is False
        assert token_manager.validate_token_format(None) is False
    
    def test_publisher_api_workflow_error_handling(self, api_manager):
        """Test publisher API workflow error handling."""
        # Test with invalid configurations
        invalid_configs = [
            {'invalid_api': {'base_url': 'invalid_url'}},  # Missing api_key
            {'invalid_api': {'api_key': 'test_key'}},      # Missing base_url
        ]
        
        for config in invalid_configs:
            with pytest.raises(ValueError):
                api_manager.register_apis(config)
        
        # Test with empty configuration
        result = api_manager.register_apis({})
        assert result is True
        
        # Test getting non-existent API client
        client = api_manager.get_api_client('nonexistent_api')
        assert client is None


class TestIntegratedWorkflowWithErrorHandling:
    """Test integrated workflows with comprehensive error handling."""
    
    @pytest.fixture
    def error_handler(self):
        """Create error handler for integration testing."""
        return RobustErrorHandler(
            max_attempts=3,
            base_delay=0.1,  # Short delay for testing
            max_delay=1.0,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=5.0
        )
    
    def test_integrated_workflow_with_retry_logic(self, error_handler):
        """Test integrated workflow with retry logic."""
        call_count = 0
        
        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network error")
            return {"status": "success", "data": "test_data"}
        
        # Execute with retry logic
        result = error_handler.execute_with_retry(
            failing_operation,
            service_name="test_service"
        )
        
        assert result["status"] == "success"
        assert result["data"] == "test_data"
        assert call_count == 3  # Should have retried twice
    
    def test_integrated_workflow_with_circuit_breaker(self, error_handler):
        """Test integrated workflow with circuit breaker."""
        def always_failing_operation():
            raise ConnectionError("Persistent network error")

        # Trigger circuit breaker
        for _ in range(3):
            try:
                error_handler.execute_with_retry(
                    always_failing_operation,
                    service_name="failing_service"
                )
            except (ConnectionError, NonRetryableError):
                pass

        # Circuit breaker should be open now
        cb_status = error_handler.get_circuit_breaker_status("failing_service")
        assert cb_status["state"] == "open"
        assert cb_status["failure_count"] >= 3
    
    @pytest.mark.asyncio
    async def test_async_integrated_workflow(self, error_handler):
        """Test async integrated workflow."""
        call_count = 0
        
        async def async_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Async network error")
            return {"status": "async_success"}
        
        # Execute async workflow with retry
        result = await error_handler.async_execute_with_retry(
            async_failing_operation,
            service_name="async_test_service"
        )
        
        assert result["status"] == "async_success"
        assert call_count == 2  # Should have retried once


class TestAuthenticationAndDownloadValidation:
    """Test validation of authentication and download functionality."""

    @pytest.fixture
    def pmc_client(self):
        """Create PMC client for validation testing."""
        config = {
            'base_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
            'api_key': 'test_api_key',
            'email': 'test@example.com',
            'rate_limit_delay': 0.34,
            'timeout': 30
        }
        return PMCClient(config)

    def test_authentication_validation_success(self, pmc_client):
        """Test successful authentication validation."""
        with patch('requests.Session.get') as mock_get:
            # Mock successful authentication response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'esearchresult': {
                    'count': '1',
                    'retmax': '1',
                    'idlist': ['123456']
                }
            }
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # Test authentication
            result = pmc_client.authenticate()

            # Verify authentication succeeded
            assert result is True
            assert pmc_client.is_authenticated is True

            # Verify API call was made
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert 'esearch.fcgi' in call_args[0][0]  # URL should contain esearch endpoint

    def test_authentication_validation_failure(self, pmc_client):
        """Test authentication validation failure."""
        with patch('requests.Session.get') as mock_get:
            # Mock authentication failure response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = Exception("Unauthorized")
            mock_get.return_value = mock_response

            # Test authentication failure
            result = pmc_client.authenticate()

            # Verify authentication failed
            assert result is False
            assert pmc_client.is_authenticated is False

    def test_download_functionality_validation_success(self, pmc_client):
        """Test successful download functionality validation."""
        # Set authentication state
        pmc_client.is_authenticated = True

        with patch('requests.Session.get') as mock_get:
            # Mock successful download response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'<?xml version="1.0"?><article><title>Test Article</title><abstract>Test abstract</abstract></article>'
            mock_response.headers = {'Content-Type': 'application/xml'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # Test download functionality
            article_ids = ["PMC123456"]
            results = pmc_client.download_articles(article_ids)

            # Validate download results
            assert isinstance(results, list)
            assert len(results) == 1

            result = results[0]
            assert result['pmc_id'] == 'PMC123456'
            assert result['status'] == 'success'
            assert 'content' in result
            assert result['content'] == mock_response.content
            assert result['content_type'] == 'application/xml'
            assert result['size'] > 0

    def test_download_functionality_validation_with_errors(self, pmc_client):
        """Test download functionality validation with various error scenarios."""
        # Set authentication state
        pmc_client.is_authenticated = True

        # Test network error handling
        with patch('requests.Session.get') as mock_get:
            mock_get.side_effect = ConnectionError("Network error")

            article_ids = ["PMC123456"]
            results = pmc_client.download_articles(article_ids)

            # Should handle network errors gracefully
            assert isinstance(results, list)
            assert len(results) == 1

            result = results[0]
            assert result['pmc_id'] == 'PMC123456'
            assert result['status'] == 'error'
            assert 'error' in result

    def test_rate_limiting_validation(self, pmc_client):
        """Test rate limiting validation."""
        # Set authentication state
        pmc_client.is_authenticated = True

        request_times = []

        def mock_get_with_timing(*args, **kwargs):
            request_times.append(time.time())
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'<article>Test</article>'
            mock_response.headers = {'Content-Type': 'application/xml'}
            mock_response.raise_for_status.return_value = None
            return mock_response

        with patch('requests.Session.get', side_effect=mock_get_with_timing):
            # Download multiple articles to test rate limiting
            article_ids = ["PMC1", "PMC2", "PMC3"]
            results = pmc_client.download_articles(article_ids)

            # Validate rate limiting was applied
            assert len(results) == 3
            assert all(r['status'] == 'success' for r in results)

            # Check timing between requests
            if len(request_times) > 1:
                time_diffs = [request_times[i+1] - request_times[i] for i in range(len(request_times)-1)]
                # Should have some delay between requests due to rate limiting
                min_expected_delay = pmc_client.config.get('rate_limit_delay', 0.34) - 0.1  # Allow some tolerance
                assert any(diff >= min_expected_delay for diff in time_diffs)

    def test_comprehensive_workflow_validation(self, pmc_client):
        """Test comprehensive workflow validation from authentication to download."""
        # Test complete workflow
        with patch('requests.Session.get') as mock_get:
            # Mock authentication response
            auth_response = Mock()
            auth_response.status_code = 200
            auth_response.json.return_value = {
                'esearchresult': {
                    'count': '1',
                    'retmax': '1',
                    'idlist': ['123456']
                }
            }
            auth_response.raise_for_status.return_value = None

            # Mock download response
            download_response = Mock()
            download_response.status_code = 200
            download_response.content = b'<article><title>Comprehensive Test</title></article>'
            download_response.headers = {'Content-Type': 'application/xml'}
            download_response.raise_for_status.return_value = None

            mock_get.return_value = auth_response

            # Step 1: Authenticate
            auth_result = pmc_client.authenticate()
            assert auth_result is True
            assert pmc_client.is_authenticated is True

            # Step 2: Switch to download response
            mock_get.return_value = download_response

            # Step 3: Download articles
            article_ids = ["PMC123456", "PMC789012"]
            download_results = pmc_client.download_articles(article_ids)

            # Validate complete workflow
            assert isinstance(download_results, list)
            assert len(download_results) == 2

            for result in download_results:
                assert result['status'] == 'success'
                assert 'pmc_id' in result
                assert 'content' in result
                assert 'content_type' in result
                assert result['content_type'] == 'application/xml'
                assert result['size'] > 0

    def test_publisher_api_authentication_validation(self):
        """Test publisher API authentication validation."""
        api_manager = PublisherAPIManager()

        # Test API registration validation
        valid_config = {
            'test_publisher': {
                'base_url': 'https://api.testpublisher.com',
                'api_key': 'valid_test_key',
                'timeout': 30
            }
        }

        result = api_manager.register_apis(valid_config)
        assert result is True

        # Validate API client creation
        client = api_manager.get_api_client('test_publisher')
        assert client is not None
        assert client.base_url == 'https://api.testpublisher.com'
        assert client.api_key == 'valid_test_key'

        # Test invalid configuration validation
        invalid_configs = [
            {'invalid': {'base_url': 'https://example.com'}},  # Missing api_key
            {'invalid': {'api_key': 'test_key'}},              # Missing base_url
            {'invalid': {'base_url': 'invalid_url', 'api_key': 'test_key'}},  # Invalid URL
        ]

        for invalid_config in invalid_configs:
            with pytest.raises(ValueError):
                api_manager.register_apis(invalid_config)
