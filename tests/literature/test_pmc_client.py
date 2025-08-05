"""
Tests for the PMCClient class.

This module contains comprehensive tests for PubMed Central (PMC) API client
functionality including authentication, article download, and rate limiting.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import Dict, List, Any
import json
import tempfile
from pathlib import Path

from tests.literature.test_base import LiteratureTestBase


class TestPMCClient(LiteratureTestBase):
    """Test cases for PMCClient class."""
    
    def test_pmc_client_initialization(self):
        """Test PMCClient initialization with default and custom config."""
        from src.literature.pmc_client import PMCClient

        # Test default initialization
        client = PMCClient()

        assert client.config is not None
        assert hasattr(client, 'logger')
        assert hasattr(client, 'session')
        assert client.base_url is not None

        # Test with custom config - mock the config file loading to avoid interference
        custom_config = {
            'api_key': 'test_key',
            'email': 'test@example.com',
            'rate_limit_delay': 2.0,
            'max_retries': 5
        }

        with patch('pathlib.Path.exists', return_value=False):  # Disable YAML config loading
            client_custom = PMCClient(custom_config)

        assert client_custom.config['api_key'] == 'test_key'
        assert client_custom.config['email'] == 'test@example.com'
        assert client_custom.config['rate_limit_delay'] == 2.0
        assert client_custom.config['max_retries'] == 5
    
    def test_authenticate_success(self):
        """Test successful PMC authentication."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'valid_test_key',
            'email': 'test@example.com'
        })
        
        # Mock successful authentication response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.authenticate()
        
        assert result is True
        assert client.is_authenticated is True
        assert client.last_auth_check is not None
    
    def test_authenticate_invalid_api_key(self):
        """Test authentication with invalid API key."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'invalid_key',
            'email': 'test@example.com'
        })
        
        # Mock authentication failure response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'Invalid API key'
        }
        
        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.authenticate()
        
        assert result is False
        assert client.is_authenticated is False
        assert 'Invalid API key' in str(client.last_error)
    
    def test_authenticate_missing_email(self):
        """Test authentication with missing email."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': None
        })
        
        result = client.authenticate()
        
        assert result is False
        assert client.is_authenticated is False
        assert 'email' in str(client.last_error).lower()
    
    def test_authenticate_network_error(self):
        """Test authentication with network error."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })
        
        # Mock network error
        with patch.object(client.session, 'get', side_effect=ConnectionError("Network error")):
            result = client.authenticate()
        
        assert result is False
        assert client.is_authenticated is False
        assert 'network' in str(client.last_error).lower()
    
    def test_authenticate_timeout(self):
        """Test authentication with timeout."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'timeout': 1.0
        })
        
        # Mock timeout error
        with patch.object(client.session, 'get', side_effect=TimeoutError("Request timeout")):
            result = client.authenticate()
        
        assert result is False
        assert client.is_authenticated is False
        assert 'timeout' in str(client.last_error).lower()
    
    def test_authenticate_with_retry(self):
        """Test authentication with retry logic."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'max_retries': 3
        })

        # Mock successful response (the session handles retries automatically)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.authenticate()

        assert result is True
        assert client.is_authenticated is True
    
    def test_authenticate_rate_limiting(self):
        """Test authentication respects rate limiting."""
        from src.literature.pmc_client import PMCClient
        import time
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'rate_limit_delay': 0.1  # Short delay for testing
        })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response):
            start_time = time.time()

            # Make two authentication calls - disable caching for this test
            client.is_authenticated = False
            client.last_auth_check = None
            client.authenticate()

            client.is_authenticated = False
            client.last_auth_check = None
            client.authenticate()

            elapsed_time = time.time() - start_time

            # Should have waited at least the rate limit delay
            assert elapsed_time >= 0.1
    
    def test_authenticate_caching(self):
        """Test authentication result caching."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'auth_cache_duration': 300  # 5 minutes
        })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            # First authentication
            result1 = client.authenticate()
            
            # Second authentication (should use cache)
            result2 = client.authenticate()
            
            assert result1 is True
            assert result2 is True
            
            # Should only make one actual API call due to caching
            assert mock_get.call_count == 1
    
    def test_authenticate_cache_expiry(self):
        """Test authentication cache expiry."""
        from src.literature.pmc_client import PMCClient
        import time
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'auth_cache_duration': 0.1  # Very short cache for testing
        })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            # First authentication
            client.authenticate()
            
            # Wait for cache to expire
            time.sleep(0.2)
            
            # Second authentication (should make new API call)
            client.authenticate()
            
            # Should make two API calls due to cache expiry
            assert mock_get.call_count == 2
    
    def test_authenticate_validation_parameters(self):
        """Test authentication parameter validation."""
        from src.literature.pmc_client import PMCClient
        
        # Test with empty API key
        client = PMCClient({
            'api_key': '',
            'email': 'test@example.com'
        })
        
        result = client.authenticate()
        assert result is False
        assert 'api key' in str(client.last_error).lower()
        
        # Test with invalid email format
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'invalid_email'
        })
        
        result = client.authenticate()
        assert result is False
        assert 'email' in str(client.last_error).lower()
    
    def test_authenticate_environment_variables(self):
        """Test authentication using environment variables."""
        from src.literature.pmc_client import PMCClient
        
        # Test with environment variables
        with patch.dict('os.environ', {
            'PMC_API_KEY': 'env_test_key',
            'PMC_EMAIL': 'env_test@example.com'
        }):
            client = PMCClient()
            
            # Should load credentials from environment
            assert client.config['api_key'] == 'env_test_key'
            assert client.config['email'] == 'env_test@example.com'
    
    def test_authenticate_logging(self):
        """Test authentication logging."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response):
            with patch.object(client.logger, 'info') as mock_log_info:
                with patch.object(client.logger, 'error') as mock_log_error:
                    result = client.authenticate()

                    assert result is True
                    mock_log_info.assert_called()
                    mock_log_error.assert_not_called()
    
    def test_is_authenticated_property(self):
        """Test is_authenticated property behavior."""
        from src.literature.pmc_client import PMCClient
        
        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })
        
        # Initially not authenticated
        assert client.is_authenticated is False
        
        # Mock successful authentication
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'esearchresult': {
                'count': '1',
                'idlist': ['test']
            }
        }
        
        with patch.object(client.session, 'get', return_value=mock_response):
            client.authenticate()
            assert client.is_authenticated is True

    def test_download_articles_success(self):
        """Test successful article download."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'rate_limit_delay': 0.1
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock successful download response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<article>Test article content</article>'
        mock_response.headers = {'content-type': 'application/xml'}

        article_ids = ['PMC123456', 'PMC789012']

        with patch.object(client.session, 'get', return_value=mock_response):
            results = client.download_articles(article_ids)

        assert len(results) == 2
        assert all('content' in result for result in results)
        assert all('pmc_id' in result for result in results)
        assert all('status' in result for result in results)
        assert all(result['status'] == 'success' for result in results)

    def test_download_articles_with_rate_limiting(self):
        """Test article download respects rate limiting."""
        from src.literature.pmc_client import PMCClient
        import time

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'rate_limit_delay': 0.2  # 200ms delay for testing
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock successful download response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<article>Test article content</article>'
        mock_response.headers = {'content-type': 'application/xml'}

        article_ids = ['PMC123456', 'PMC789012', 'PMC345678']

        with patch.object(client.session, 'get', return_value=mock_response):
            start_time = time.time()
            results = client.download_articles(article_ids)
            elapsed_time = time.time() - start_time

        # Should have waited for rate limiting between requests
        # With 3 articles and 0.2s delay, should take at least 0.4s (2 delays)
        assert elapsed_time >= 0.4
        assert len(results) == 3

    def test_download_articles_authentication_required(self):
        """Test download articles requires authentication."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Not authenticated
        client.is_authenticated = False

        article_ids = ['PMC123456']

        with pytest.raises(ValueError, match="Authentication required"):
            client.download_articles(article_ids)

    def test_download_articles_empty_list(self):
        """Test download articles with empty list."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        results = client.download_articles([])
        assert results == []

    def test_download_articles_invalid_ids(self):
        """Test download articles with invalid PMC IDs."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Test with invalid ID format
        with pytest.raises(ValueError, match="Invalid PMC ID format"):
            client.download_articles(['invalid_id'])

        # Test with None in list
        with pytest.raises(ValueError, match="PMC ID cannot be None or empty"):
            client.download_articles([None])

        # Test with empty string
        with pytest.raises(ValueError, match="PMC ID cannot be None or empty"):
            client.download_articles([''])

    def test_download_articles_http_error(self):
        """Test download articles with HTTP error."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Article not found'

        article_ids = ['PMC123456']

        with patch.object(client.session, 'get', return_value=mock_response):
            results = client.download_articles(article_ids)

        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert 'error' in results[0]
        assert '404' in results[0]['error']

    def test_download_articles_network_error(self):
        """Test download articles with network error."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        article_ids = ['PMC123456']

        with patch.object(client.session, 'get', side_effect=ConnectionError("Network error")):
            results = client.download_articles(article_ids)

        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert 'network error' in results[0]['error'].lower()

    def test_download_articles_timeout(self):
        """Test download articles with timeout."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'timeout': 1.0
        })

        # Mock authentication
        client.is_authenticated = True

        article_ids = ['PMC123456']

        with patch.object(client.session, 'get', side_effect=TimeoutError("Request timeout")):
            results = client.download_articles(article_ids)

        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert 'timeout' in results[0]['error'].lower()

    def test_download_articles_with_retry_logic(self):
        """Test download articles with retry logic for failed requests."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com',
            'max_retries': 3
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock response that succeeds after retries (handled by session)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<article>Test article content</article>'
        mock_response.headers = {'content-type': 'application/xml'}

        article_ids = ['PMC123456']

        with patch.object(client.session, 'get', return_value=mock_response):
            results = client.download_articles(article_ids)

        assert len(results) == 1
        assert results[0]['status'] == 'success'

    def test_download_articles_mixed_results(self):
        """Test download articles with mixed success and failure results."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock responses - success for first, error for second
        success_response = Mock()
        success_response.status_code = 200
        success_response.content = b'<article>Test article content</article>'
        success_response.headers = {'content-type': 'application/xml'}

        error_response = Mock()
        error_response.status_code = 404
        error_response.text = 'Article not found'

        article_ids = ['PMC123456', 'PMC789012']

        with patch.object(client.session, 'get', side_effect=[success_response, error_response]):
            results = client.download_articles(article_ids)

        assert len(results) == 2
        assert results[0]['status'] == 'success'
        assert results[1]['status'] == 'error'

    def test_download_articles_progress_callback(self):
        """Test download articles with progress callback."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock successful download response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<article>Test article content</article>'
        mock_response.headers = {'content-type': 'application/xml'}

        article_ids = ['PMC123456', 'PMC789012']
        progress_calls = []

        def progress_callback(current, total, pmc_id):
            progress_calls.append((current, total, pmc_id))

        with patch.object(client.session, 'get', return_value=mock_response):
            results = client.download_articles(article_ids, progress_callback=progress_callback)

        assert len(results) == 2
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2, 'PMC123456')
        assert progress_calls[1] == (2, 2, 'PMC789012')

    def test_download_articles_content_validation(self):
        """Test download articles validates content format."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Mock response with invalid XML content
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'Invalid XML content'
        mock_response.headers = {'content-type': 'text/html'}

        article_ids = ['PMC123456']

        with patch.object(client.session, 'get', return_value=mock_response):
            results = client.download_articles(article_ids, validate_xml=True)

        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert 'validation' in results[0]['error'].lower() or 'xml' in results[0]['error'].lower()

    @pytest.mark.asyncio
    async def test_download_articles_async_method_exists(self):
        """Test that async download method exists and has correct signature."""
        from src.literature.pmc_client import PMCClient
        import inspect

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Check that the async method exists
        assert hasattr(client, 'download_articles_async')

        # Check that it's a coroutine function
        assert inspect.iscoroutinefunction(client.download_articles_async)

        # Check method signature
        sig = inspect.signature(client.download_articles_async)
        expected_params = ['article_ids', 'progress_callback', 'validate_xml', 'max_concurrent']
        actual_params = list(sig.parameters.keys())

        for param in expected_params:
            assert param in actual_params

    @pytest.mark.asyncio
    async def test_download_articles_async_authentication_required(self):
        """Test async download articles requires authentication."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Not authenticated
        client.is_authenticated = False

        article_ids = ['PMC123456']

        with pytest.raises(ValueError, match="Authentication required"):
            await client.download_articles_async(article_ids)

    @pytest.mark.asyncio
    async def test_download_articles_async_empty_list(self):
        """Test async download articles with empty list."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        results = await client.download_articles_async([])
        assert results == []

    @pytest.mark.asyncio
    async def test_download_articles_async_invalid_ids(self):
        """Test async download articles with invalid PMC IDs."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Mock authentication
        client.is_authenticated = True

        # Test with invalid ID format
        with pytest.raises(ValueError, match="Invalid PMC ID format"):
            await client.download_articles_async(['invalid_id'])

    def test_async_method_integration_with_sync(self):
        """Test that async method integrates well with sync methods."""
        from src.literature.pmc_client import PMCClient

        client = PMCClient({
            'api_key': 'test_key',
            'email': 'test@example.com'
        })

        # Both sync and async methods should exist
        assert hasattr(client, 'download_articles')
        assert hasattr(client, 'download_articles_async')

        # They should have similar parameter signatures
        import inspect
        sync_sig = inspect.signature(client.download_articles)
        async_sig = inspect.signature(client.download_articles_async)

        # Both should have article_ids parameter
        assert 'article_ids' in sync_sig.parameters
        assert 'article_ids' in async_sig.parameters

        # Both should have progress_callback parameter
        assert 'progress_callback' in sync_sig.parameters
        assert 'progress_callback' in async_sig.parameters
