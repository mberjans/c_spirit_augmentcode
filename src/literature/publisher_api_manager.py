"""
Publisher API Manager for Literature Access.

This module provides a centralized manager for registering and managing
multiple publisher API clients with configuration, authentication, and
rate limiting capabilities.
"""

import os
import re
from typing import Dict, List, Any, Optional, Type
from urllib.parse import urlparse
from loguru import logger


class PublisherAPIClient:
    """
    Base class for publisher API clients.
    
    This class provides a common interface for all publisher API clients
    with basic configuration and rate limiting support.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the publisher API client.
        
        Args:
            config: Configuration dictionary containing API settings
        """
        self.config = config
        self.base_url = config.get('base_url')
        self.api_key = config.get('api_key')
        self.rate_limit = config.get('rate_limit', 1.0)
        self.timeout = config.get('timeout', 30)
        self.logger = logger


class PublisherAPIManager:
    """
    Manager for registering and managing multiple publisher API clients.
    
    This class provides centralized management of publisher API configurations,
    authentication, and client instantiation with validation and error handling.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the publisher API manager.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.registered_apis = {}
        self.logger = logger
        
        # Default client class for publisher APIs
        self.default_client_class = PublisherAPIClient
    
    def _validate_url(self, url: str) -> bool:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _resolve_environment_variables(self, value: str) -> str:
        """
        Resolve environment variable placeholders in configuration values.
        
        Args:
            value: Configuration value that may contain environment variable placeholders
            
        Returns:
            Resolved value with environment variables substituted
        """
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var_name = value[2:-1]  # Remove ${ and }
            return os.getenv(env_var_name, value)
        return value
    
    def _validate_api_config(self, api_name: str, config: Dict[str, Any]) -> None:
        """
        Validate API configuration.
        
        Args:
            api_name: Name of the API
            config: Configuration dictionary to validate
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Check required fields
        required_fields = ['base_url', 'api_key']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field '{field}' for API '{api_name}'")
        
        # Validate URL format
        base_url = self._resolve_environment_variables(config['base_url'])
        if not self._validate_url(base_url):
            raise ValueError(f"Invalid URL format for API '{api_name}': {base_url}")
        
        # Validate API key
        api_key = self._resolve_environment_variables(config['api_key'])
        if not api_key or api_key.strip() == '':
            raise ValueError(f"API key cannot be empty for API '{api_name}'")
    
    def _create_api_client(self, api_name: str, config: Dict[str, Any]) -> Any:
        """
        Create an API client instance.
        
        Args:
            api_name: Name of the API
            config: Configuration dictionary
            
        Returns:
            API client instance
        """
        # Resolve environment variables in configuration
        resolved_config = {}
        for key, value in config.items():
            if key == 'client_class':
                resolved_config[key] = value  # Don't resolve class references
            else:
                resolved_config[key] = self._resolve_environment_variables(value)
        
        # Get client class (use custom class if provided, otherwise default)
        client_class = config.get('client_class', self.default_client_class)
        
        # Create and return client instance
        return client_class(resolved_config)
    
    def register_apis(self, api_configs: Dict[str, Dict[str, Any]]) -> bool:
        """
        Register multiple publisher APIs.
        
        Args:
            api_configs: Dictionary mapping API names to their configurations
            
        Returns:
            True if registration successful, False otherwise
            
        Raises:
            ValueError: If any API configuration is invalid
        """
        try:
            # Handle empty configuration
            if not api_configs:
                self.logger.info("No APIs to register")
                return True
            
            # Validate all configurations first
            for api_name, config in api_configs.items():
                self._validate_api_config(api_name, config)
            
            # Register all APIs
            for api_name, config in api_configs.items():
                try:
                    # Create API client
                    api_client = self._create_api_client(api_name, config)
                    
                    # Register the client
                    self.registered_apis[api_name] = api_client
                    
                    # Log registration (without sensitive information)
                    self.logger.info(f"Successfully registered API: {api_name}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to register API '{api_name}': {str(e)}")
                    raise ValueError(f"Failed to register API '{api_name}': {str(e)}")
            
            self.logger.info(f"Successfully registered {len(api_configs)} publisher APIs")
            return True
            
        except Exception as e:
            self.logger.error(f"API registration failed: {str(e)}")
            raise
    
    def get_api_client(self, api_name: str) -> Optional[Any]:
        """
        Get a registered API client by name.
        
        Args:
            api_name: Name of the API
            
        Returns:
            API client instance or None if not found
        """
        return self.registered_apis.get(api_name)
    
    def list_registered_apis(self) -> List[str]:
        """
        Get list of registered API names.
        
        Returns:
            List of registered API names
        """
        return list(self.registered_apis.keys())
    
    def unregister_api(self, api_name: str) -> bool:
        """
        Unregister an API client.
        
        Args:
            api_name: Name of the API to unregister
            
        Returns:
            True if unregistered successfully, False if not found
        """
        if api_name in self.registered_apis:
            del self.registered_apis[api_name]
            self.logger.info(f"Unregistered API: {api_name}")
            return True
        return False
    
    def clear_all_apis(self) -> None:
        """Clear all registered APIs."""
        self.registered_apis.clear()
        self.logger.info("Cleared all registered APIs")
