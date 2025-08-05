"""
Tests for Authentication Token Manager.

This module contains comprehensive tests for the TokenManager class,
covering secure token storage, refresh mechanisms, and authentication management.
"""

import os
import json
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.literature.token_manager import TokenManager


class TestTokenManager:
    """Test cases for TokenManager class."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create temporary storage path for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir) / "test_tokens.enc"
    
    @pytest.fixture
    def token_manager(self, temp_storage_path):
        """Create TokenManager instance for testing."""
        return TokenManager(storage_path=str(temp_storage_path))
    
    @pytest.fixture
    def sample_token_data(self):
        """Sample token data for testing."""
        return {
            'api_name': 'test_api',
            'token': 'test_access_token_12345',
            'expires_in': 3600,
            'refresh_token': 'test_refresh_token_67890',
            'metadata': {'scope': 'read', 'user_id': '123'}
        }
    
    def test_token_manager_initialization(self, temp_storage_path):
        """Test TokenManager initialization."""
        manager = TokenManager(storage_path=str(temp_storage_path))
        
        assert manager.storage_path == temp_storage_path
        assert manager.tokens == {}
        assert manager.refresh_callbacks == {}
        assert manager.cipher is not None
    
    def test_encryption_key_generation(self, temp_storage_path):
        """Test encryption key generation and persistence."""
        manager1 = TokenManager(storage_path=str(temp_storage_path))
        key1 = manager1.encryption_key
        
        # Create another manager with same path - should use same key
        manager2 = TokenManager(storage_path=str(temp_storage_path))
        key2 = manager2.encryption_key
        
        assert key1 == key2
    
    def test_custom_encryption_key(self, temp_storage_path):
        """Test TokenManager with custom encryption key."""
        from cryptography.fernet import Fernet
        custom_key = Fernet.generate_key()
        manager = TokenManager(storage_path=str(temp_storage_path), encryption_key=custom_key)

        assert manager.encryption_key == custom_key
    
    def test_store_token_basic(self, token_manager, sample_token_data):
        """Test basic token storage."""
        token_manager.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token'],
            expires_in=sample_token_data['expires_in'],
            refresh_token=sample_token_data['refresh_token'],
            metadata=sample_token_data['metadata']
        )
        
        assert sample_token_data['api_name'] in token_manager.tokens
        stored_token = token_manager.tokens[sample_token_data['api_name']]
        
        assert stored_token['token'] == sample_token_data['token']
        assert stored_token['refresh_token'] == sample_token_data['refresh_token']
        assert stored_token['metadata'] == sample_token_data['metadata']
        assert 'created_at' in stored_token
        assert 'expires_at' in stored_token
    
    def test_store_token_without_expiration(self, token_manager):
        """Test storing token without expiration."""
        token_manager.store_token(
            api_name='test_api',
            token='test_token'
        )
        
        stored_token = token_manager.tokens['test_api']
        assert 'expires_at' not in stored_token
        assert 'expires_in' not in stored_token
    
    def test_get_token_valid(self, token_manager, sample_token_data):
        """Test getting a valid token."""
        token_manager.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token'],
            expires_in=sample_token_data['expires_in']
        )
        
        retrieved_token = token_manager.get_token(sample_token_data['api_name'])
        assert retrieved_token == sample_token_data['token']
    
    def test_get_token_nonexistent(self, token_manager):
        """Test getting a non-existent token."""
        retrieved_token = token_manager.get_token('nonexistent_api')
        assert retrieved_token is None
    
    def test_get_token_expired_no_refresh(self, token_manager):
        """Test getting an expired token without refresh capability."""
        # Store token that expires in the past
        past_time = datetime.now() - timedelta(hours=1)
        token_manager.tokens['test_api'] = {
            'token': 'expired_token',
            'created_at': past_time.isoformat(),
            'expires_at': past_time.isoformat()
        }
        
        retrieved_token = token_manager.get_token('test_api', auto_refresh=False)
        assert retrieved_token is None
    
    def test_token_expiration_check(self, token_manager):
        """Test token expiration checking."""
        # Non-expired token
        future_time = datetime.now() + timedelta(hours=1)
        non_expired_token = {
            'expires_at': future_time.isoformat()
        }
        assert not token_manager._is_token_expired(non_expired_token)
        
        # Expired token
        past_time = datetime.now() - timedelta(hours=1)
        expired_token = {
            'expires_at': past_time.isoformat()
        }
        assert token_manager._is_token_expired(expired_token)
        
        # Token without expiration
        no_expiry_token = {}
        assert not token_manager._is_token_expired(no_expiry_token)
    
    def test_register_refresh_callback(self, token_manager):
        """Test registering refresh callback."""
        def mock_refresh_callback(refresh_token):
            return {'access_token': 'new_token', 'expires_in': 3600}
        
        token_manager.register_refresh_callback('test_api', mock_refresh_callback)
        
        assert 'test_api' in token_manager.refresh_callbacks
        assert token_manager.refresh_callbacks['test_api'] == mock_refresh_callback
    
    def test_token_refresh_success(self, token_manager):
        """Test successful token refresh."""
        # Mock refresh callback
        def mock_refresh_callback(refresh_token):
            return {
                'access_token': 'new_access_token',
                'expires_in': 3600,
                'refresh_token': 'new_refresh_token'
            }
        
        # Store expired token with refresh token
        past_time = datetime.now() - timedelta(hours=1)
        token_manager.tokens['test_api'] = {
            'token': 'old_token',
            'refresh_token': 'refresh_token_123',
            'created_at': past_time.isoformat(),
            'expires_at': past_time.isoformat()
        }
        
        # Register refresh callback
        token_manager.register_refresh_callback('test_api', mock_refresh_callback)
        
        # Get token should trigger refresh
        retrieved_token = token_manager.get_token('test_api')
        assert retrieved_token == 'new_access_token'
        
        # Verify token was updated
        updated_token = token_manager.tokens['test_api']
        assert updated_token['token'] == 'new_access_token'
        assert updated_token['refresh_token'] == 'new_refresh_token'
    
    def test_token_refresh_failure(self, token_manager):
        """Test token refresh failure."""
        # Mock failing refresh callback
        def mock_failing_callback(refresh_token):
            raise Exception("Refresh failed")
        
        # Store expired token with refresh token
        past_time = datetime.now() - timedelta(hours=1)
        token_manager.tokens['test_api'] = {
            'token': 'old_token',
            'refresh_token': 'refresh_token_123',
            'created_at': past_time.isoformat(),
            'expires_at': past_time.isoformat()
        }
        
        # Register failing refresh callback
        token_manager.register_refresh_callback('test_api', mock_failing_callback)
        
        # Get token should fail
        retrieved_token = token_manager.get_token('test_api')
        assert retrieved_token is None
    
    def test_revoke_token(self, token_manager, sample_token_data):
        """Test token revocation."""
        # Store token
        token_manager.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token']
        )
        
        # Verify token exists
        assert sample_token_data['api_name'] in token_manager.tokens
        
        # Revoke token
        result = token_manager.revoke_token(sample_token_data['api_name'])
        assert result is True
        assert sample_token_data['api_name'] not in token_manager.tokens
        
        # Try to revoke non-existent token
        result = token_manager.revoke_token('nonexistent_api')
        assert result is False
    
    def test_list_tokens(self, token_manager, sample_token_data):
        """Test listing tokens with metadata."""
        token_manager.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token'],
            expires_in=sample_token_data['expires_in'],
            refresh_token=sample_token_data['refresh_token'],
            metadata=sample_token_data['metadata']
        )
        
        token_list = token_manager.list_tokens()
        
        assert sample_token_data['api_name'] in token_list
        token_info = token_list[sample_token_data['api_name']]
        
        # Verify sensitive data is not included
        assert 'token' not in token_info
        assert 'refresh_token' not in token_info
        
        # Verify metadata is included
        assert 'created_at' in token_info
        assert 'expires_at' in token_info
        assert 'has_refresh_token' in token_info
        assert 'is_expired' in token_info
        assert token_info['metadata'] == sample_token_data['metadata']
    
    def test_cleanup_expired_tokens(self, token_manager):
        """Test cleanup of expired tokens."""
        # Store expired token without refresh
        past_time = datetime.now() - timedelta(hours=1)
        token_manager.tokens['expired_api'] = {
            'token': 'expired_token',
            'created_at': past_time.isoformat(),
            'expires_at': past_time.isoformat()
        }
        
        # Store expired token with refresh (should not be cleaned)
        token_manager.tokens['expired_with_refresh'] = {
            'token': 'expired_token_with_refresh',
            'refresh_token': 'refresh_123',
            'created_at': past_time.isoformat(),
            'expires_at': past_time.isoformat()
        }
        
        # Store valid token
        future_time = datetime.now() + timedelta(hours=1)
        token_manager.tokens['valid_api'] = {
            'token': 'valid_token',
            'created_at': datetime.now().isoformat(),
            'expires_at': future_time.isoformat()
        }
        
        # Cleanup expired tokens
        cleaned_count = token_manager.cleanup_expired_tokens()
        
        assert cleaned_count == 1
        assert 'expired_api' not in token_manager.tokens
        assert 'expired_with_refresh' in token_manager.tokens  # Should remain
        assert 'valid_api' in token_manager.tokens  # Should remain
    
    def test_validate_token_format(self, token_manager):
        """Test token format validation."""
        # Valid tokens
        assert token_manager.validate_token_format('valid_token_12345')
        assert token_manager.validate_token_format('Bearer abc123def456')
        assert token_manager.validate_token_format('Token xyz789abcdef')
        assert token_manager.validate_token_format('API-Key secret123456')

        # Invalid tokens
        assert not token_manager.validate_token_format('')
        assert not token_manager.validate_token_format('short')
        assert not token_manager.validate_token_format(None)
        assert not token_manager.validate_token_format(123)
        assert not token_manager.validate_token_format('Bearer x')  # Too short after prefix
        assert not token_manager.validate_token_format('Token xyz')  # Too short after prefix
    
    @patch('src.literature.token_manager.os.chmod')
    def test_file_permissions(self, mock_chmod, token_manager, sample_token_data):
        """Test that files are created with secure permissions."""
        token_manager.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token']
        )
        
        # Verify chmod was called with restrictive permissions
        mock_chmod.assert_called()
        args, kwargs = mock_chmod.call_args_list[-1]
        assert args[1] == 0o600  # Owner read/write only
    
    def test_token_persistence(self, temp_storage_path, sample_token_data):
        """Test token persistence across manager instances."""
        # Store token with first manager
        manager1 = TokenManager(storage_path=str(temp_storage_path))
        manager1.store_token(
            api_name=sample_token_data['api_name'],
            token=sample_token_data['token'],
            expires_in=sample_token_data['expires_in']
        )
        
        # Create new manager and verify token is loaded
        manager2 = TokenManager(storage_path=str(temp_storage_path))
        retrieved_token = manager2.get_token(sample_token_data['api_name'])
        
        assert retrieved_token == sample_token_data['token']
    
    def test_corrupted_storage_handling(self, temp_storage_path):
        """Test handling of corrupted storage file."""
        # Create corrupted storage file (binary data that's not valid Fernet)
        with open(temp_storage_path, 'wb') as f:
            f.write(b"corrupted binary data that is not valid fernet encryption")

        # Manager should handle corruption gracefully
        manager = TokenManager(storage_path=str(temp_storage_path))
        assert manager.tokens == {}
    
    def test_concurrent_access_safety(self, token_manager, sample_token_data):
        """Test thread safety of token operations."""
        import threading
        import time
        
        results = []
        
        def store_and_retrieve():
            token_manager.store_token(
                api_name=f"api_{threading.current_thread().ident}",
                token=f"token_{threading.current_thread().ident}"
            )
            time.sleep(0.01)  # Small delay to increase chance of race condition
            token = token_manager.get_token(f"api_{threading.current_thread().ident}")
            results.append(token is not None)
        
        # Run multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=store_and_retrieve)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        assert all(results)
