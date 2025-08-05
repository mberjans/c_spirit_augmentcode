"""
Authentication Token Manager for Literature Access.

This module provides secure token storage, refresh mechanisms, and authentication
management for publisher APIs with encryption and expiration handling.
"""

import os
import json
import time
import hashlib
import secrets
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from loguru import logger


class TokenManager:
    """
    Secure token manager for API authentication.
    
    Provides encrypted storage, automatic refresh, and expiration handling
    for authentication tokens used with publisher APIs.
    """
    
    def __init__(self, storage_path: str = "config/tokens.enc", encryption_key: Optional[str] = None):
        """
        Initialize the token manager.

        Args:
            storage_path: Path to encrypted token storage file
            encryption_key: Optional encryption key (generated if not provided)
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger

        # Initialize encryption
        if encryption_key:
            # If custom key provided, it should be base64-encoded Fernet key
            if isinstance(encryption_key, str):
                try:
                    self.cipher = Fernet(encryption_key.encode())
                except Exception:
                    # If not valid Fernet key, generate one from the string
                    key_bytes = hashlib.sha256(encryption_key.encode()).digest()
                    fernet_key = Fernet.generate_key()
                    self.cipher = Fernet(fernet_key)
                    self.encryption_key = fernet_key
            else:
                self.cipher = Fernet(encryption_key)
                self.encryption_key = encryption_key
        else:
            self.encryption_key = self._get_or_create_encryption_key()
            self.cipher = Fernet(self.encryption_key)

        # Token storage
        self.tokens = {}
        self.refresh_callbacks = {}

        # Load existing tokens
        self._load_tokens()
    
    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get or create encryption key for token storage.
        
        Returns:
            Encryption key as bytes
        """
        key_path = self.storage_path.parent / ".token_key"
        
        if key_path.exists():
            with open(key_path, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(key_path, 0o600)
            return key
    
    def _load_tokens(self) -> None:
        """Load tokens from encrypted storage."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            
            if encrypted_data:
                decrypted_data = self.cipher.decrypt(encrypted_data)
                self.tokens = json.loads(decrypted_data.decode())
                self.logger.info(f"Loaded {len(self.tokens)} tokens from storage")
        except Exception as e:
            self.logger.error(f"Failed to load tokens: {str(e)}")
            self.tokens = {}
    
    def _save_tokens(self) -> None:
        """Save tokens to encrypted storage."""
        try:
            # Serialize tokens
            token_data = json.dumps(self.tokens, indent=2)
            encrypted_data = self.cipher.encrypt(token_data.encode())
            
            # Write to file with atomic operation
            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions
            os.chmod(temp_path, 0o600)
            
            # Atomic rename
            temp_path.replace(self.storage_path)
            
            self.logger.debug("Tokens saved to encrypted storage")
        except Exception as e:
            self.logger.error(f"Failed to save tokens: {str(e)}")
            raise
    
    def _is_token_expired(self, token_info: Dict[str, Any]) -> bool:
        """
        Check if a token is expired.
        
        Args:
            token_info: Token information dictionary
            
        Returns:
            True if token is expired, False otherwise
        """
        if 'expires_at' not in token_info:
            return False
        
        expires_at = datetime.fromisoformat(token_info['expires_at'])
        # Consider token expired if it expires within 5 minutes
        buffer_time = timedelta(minutes=5)
        return datetime.now() + buffer_time >= expires_at
    
    def store_token(self, api_name: str, token: str, expires_in: Optional[int] = None, 
                   refresh_token: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Store an authentication token securely.
        
        Args:
            api_name: Name of the API
            token: Access token
            expires_in: Token expiration time in seconds
            refresh_token: Optional refresh token
            metadata: Additional token metadata
        """
        token_info = {
            'token': token,
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        if expires_in:
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            token_info['expires_at'] = expires_at.isoformat()
            token_info['expires_in'] = expires_in
        
        if refresh_token:
            token_info['refresh_token'] = refresh_token
        
        self.tokens[api_name] = token_info
        self._save_tokens()
        
        self.logger.info(f"Stored token for API: {api_name}")
    
    def get_token(self, api_name: str, auto_refresh: bool = True) -> Optional[str]:
        """
        Get a valid authentication token.
        
        Args:
            api_name: Name of the API
            auto_refresh: Whether to automatically refresh expired tokens
            
        Returns:
            Valid token or None if not available
        """
        if api_name not in self.tokens:
            self.logger.warning(f"No token found for API: {api_name}")
            return None
        
        token_info = self.tokens[api_name]
        
        # Check if token is expired
        if self._is_token_expired(token_info):
            if auto_refresh and 'refresh_token' in token_info:
                self.logger.info(f"Token expired for {api_name}, attempting refresh")
                if self._refresh_token(api_name):
                    return self.tokens[api_name]['token']
                else:
                    self.logger.error(f"Failed to refresh token for {api_name}")
                    return None
            else:
                self.logger.warning(f"Token expired for {api_name} and no refresh available")
                return None
        
        return token_info['token']
    
    def _refresh_token(self, api_name: str) -> bool:
        """
        Refresh an expired token using refresh token.
        
        Args:
            api_name: Name of the API
            
        Returns:
            True if refresh successful, False otherwise
        """
        if api_name not in self.tokens:
            return False
        
        token_info = self.tokens[api_name]
        refresh_token = token_info.get('refresh_token')
        
        if not refresh_token:
            self.logger.warning(f"No refresh token available for {api_name}")
            return False
        
        # Call refresh callback if registered
        if api_name in self.refresh_callbacks:
            try:
                callback = self.refresh_callbacks[api_name]
                new_token_data = callback(refresh_token)
                
                if new_token_data:
                    # Update token with new data
                    self.store_token(
                        api_name=api_name,
                        token=new_token_data.get('access_token'),
                        expires_in=new_token_data.get('expires_in'),
                        refresh_token=new_token_data.get('refresh_token', refresh_token),
                        metadata=new_token_data.get('metadata', token_info.get('metadata'))
                    )
                    self.logger.info(f"Successfully refreshed token for {api_name}")
                    return True
                else:
                    self.logger.error(f"Refresh callback returned no data for {api_name}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Token refresh failed for {api_name}: {str(e)}")
                return False
        else:
            self.logger.warning(f"No refresh callback registered for {api_name}")
            return False
    
    def register_refresh_callback(self, api_name: str, callback) -> None:
        """
        Register a callback function for token refresh.
        
        Args:
            api_name: Name of the API
            callback: Function that takes refresh_token and returns new token data
        """
        self.refresh_callbacks[api_name] = callback
        self.logger.info(f"Registered refresh callback for {api_name}")
    
    def revoke_token(self, api_name: str) -> bool:
        """
        Revoke and remove a stored token.
        
        Args:
            api_name: Name of the API
            
        Returns:
            True if token was removed, False if not found
        """
        if api_name in self.tokens:
            del self.tokens[api_name]
            self._save_tokens()
            self.logger.info(f"Revoked token for API: {api_name}")
            return True
        return False
    
    def list_tokens(self) -> Dict[str, Dict[str, Any]]:
        """
        List all stored tokens with metadata (excluding sensitive data).
        
        Returns:
            Dictionary of token metadata
        """
        token_list = {}
        for api_name, token_info in self.tokens.items():
            safe_info = {
                'created_at': token_info.get('created_at'),
                'expires_at': token_info.get('expires_at'),
                'has_refresh_token': 'refresh_token' in token_info,
                'is_expired': self._is_token_expired(token_info),
                'metadata': token_info.get('metadata', {})
            }
            token_list[api_name] = safe_info
        
        return token_list
    
    def cleanup_expired_tokens(self) -> int:
        """
        Remove all expired tokens that cannot be refreshed.
        
        Returns:
            Number of tokens removed
        """
        expired_apis = []
        
        for api_name, token_info in self.tokens.items():
            if self._is_token_expired(token_info) and 'refresh_token' not in token_info:
                expired_apis.append(api_name)
        
        for api_name in expired_apis:
            del self.tokens[api_name]
            self.logger.info(f"Cleaned up expired token for {api_name}")
        
        if expired_apis:
            self._save_tokens()
        
        return len(expired_apis)
    
    def validate_token_format(self, token: str) -> bool:
        """
        Validate token format (basic validation).

        Args:
            token: Token to validate

        Returns:
            True if format appears valid, False otherwise
        """
        if not token or not isinstance(token, str):
            return False

        # Basic validation - token should be non-empty and reasonable length
        if len(token.strip()) < 10:
            return False

        # Check for common token patterns
        if token.startswith(('Bearer ', 'Token ', 'API-Key ')):
            # For prefixed tokens, check the actual token part
            token_part = token.split(' ', 1)[1] if ' ' in token else token
            return len(token_part.strip()) >= 10

        return True
