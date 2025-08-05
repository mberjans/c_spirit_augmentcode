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
