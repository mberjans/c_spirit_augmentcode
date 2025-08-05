"""
PubMed Central (PMC) API Client.

This module provides a client for accessing PubMed Central articles through
the NCBI E-utilities API with proper authentication, rate limiting, and
error handling.
"""

import os
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger
import yaml
from pathlib import Path


class PMCClient:
    """
    Client for accessing PubMed Central (PMC) articles via NCBI E-utilities API.
    
    This client handles authentication, rate limiting, retry logic, and provides
    methods for searching and downloading articles from PMC.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the PMC client.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # Load default configuration
        self._load_default_config()

        # Load configuration from file if available
        self._load_config_file()

        # Load credentials from environment variables
        self._load_environment_credentials()

        # Override with provided config (this should take precedence)
        if config:
            for key, value in config.items():
                self.config[key] = value
        
        # Initialize client state
        self.is_authenticated = False
        self.last_auth_check = None
        self.last_error = None
        self.last_request_time = 0
        
        # Set up HTTP session with retry strategy
        self.session = self._create_session()
        
        # Set base URL
        self.base_url = self.config.get('base_url', 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/')
    
    def _load_default_config(self):
        """Load default configuration values."""
        self.default_config = {
            'api_key': None,
            'email': None,
            'base_url': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
            'rate_limit_delay': 0.34,  # NCBI allows 3 requests per second
            'max_retries': 3,
            'timeout': 30.0,
            'auth_cache_duration': 3600,  # 1 hour
            'user_agent': 'C-Spirit PMC Client/1.0',
            'verify_ssl': True
        }
        
        # Initialize config with defaults
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def _load_config_file(self):
        """Load configuration from YAML file if available."""
        config_path = Path('config/api_config.yaml')
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                # Extract PMC-specific configuration
                if 'pmc' in file_config:
                    pmc_config = file_config['pmc']
                    
                    # Map YAML config to client config
                    config_mapping = {
                        'api_key': 'api_key',
                        'email': 'email',
                        'base_url': 'base_url',
                        'rate_limit': {
                            'delay_between_requests': 'rate_limit_delay'
                        },
                        'retry': {
                            'max_attempts': 'max_retries'
                        },
                        'timeout': {
                            'total': 'timeout'
                        }
                    }
                    
                    self._apply_config_mapping(pmc_config, config_mapping)
                    
            except Exception as e:
                self.logger.warning(f"Could not load config file: {e}")
    
    def _apply_config_mapping(self, source_config: Dict, mapping: Dict):
        """Apply configuration mapping from YAML to client config."""
        for key, value in mapping.items():
            if key in source_config:
                if isinstance(value, dict):
                    # Nested configuration
                    self._apply_config_mapping(source_config[key], value)
                else:
                    # Direct mapping - skip environment variable placeholders
                    config_value = source_config[key]
                    if isinstance(config_value, str) and config_value.startswith('${') and config_value.endswith('}'):
                        # Skip environment variable placeholders in YAML
                        continue
                    self.config[value] = config_value
    
    def _load_environment_credentials(self):
        """Load API credentials from environment variables."""
        env_api_key = os.getenv('PMC_API_KEY')
        env_email = os.getenv('PMC_EMAIL')

        # Only use environment variables if not already set
        if env_api_key and not self.config.get('api_key'):
            self.config['api_key'] = env_api_key

        if env_email and not self.config.get('email'):
            self.config['email'] = env_email
    
    def _create_session(self):
        """Create HTTP session with retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.get('max_retries', 3),
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            'User-Agent': self.config.get('user_agent', 'C-Spirit PMC Client/1.0')
        })
        
        return session
    
    def _validate_credentials(self) -> bool:
        """Validate API credentials."""
        api_key = self.config.get('api_key')
        email = self.config.get('email')
        
        if not api_key or api_key.strip() == '':
            self.last_error = "API key is required"
            return False
        
        if not email or email.strip() == '':
            self.last_error = "Email address is required"
            return False
        
        # Basic email validation (more permissive)
        if '@' not in email or '.' not in email.split('@')[-1]:
            self.last_error = "Invalid email format"
            return False
        
        return True
    
    def _respect_rate_limit(self):
        """Ensure rate limiting is respected."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        rate_limit_delay = self.config.get('rate_limit_delay', 0.34)
        
        if time_since_last_request < rate_limit_delay:
            sleep_time = rate_limit_delay - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _is_auth_cache_valid(self) -> bool:
        """Check if authentication cache is still valid."""
        if not self.last_auth_check:
            return False
        
        cache_duration = self.config.get('auth_cache_duration', 3600)
        cache_expiry = self.last_auth_check + timedelta(seconds=cache_duration)
        
        return datetime.now() < cache_expiry
    
    def authenticate(self) -> bool:
        """
        Authenticate with the PMC API.
        
        Returns:
            True if authentication successful, False otherwise
        """
        # Check if we have a valid cached authentication
        if self.is_authenticated and self._is_auth_cache_valid():
            return True
        
        # Validate credentials
        if not self._validate_credentials():
            self.logger.error(f"Authentication failed: {self.last_error}")
            return False
        
        try:
            # Respect rate limiting
            self._respect_rate_limit()
            
            # Test authentication with a simple search
            test_url = f"{self.base_url}esearch.fcgi"
            params = {
                'db': 'pmc',
                'term': 'test',
                'retmax': 1,
                'retmode': 'json',
                'api_key': self.config['api_key'],
                'email': self.config['email']
            }
            
            response = self.session.get(
                test_url,
                params=params,
                timeout=self.config.get('timeout', 30.0),
                verify=self.config.get('verify_ssl', True)
            )
            
            if response.status_code == 200:
                # Check if response contains expected structure
                data = response.json()
                if 'esearchresult' in data:
                    self.is_authenticated = True
                    self.last_auth_check = datetime.now()
                    self.last_error = None
                    self.logger.info("PMC authentication successful")
                    return True
                else:
                    self.last_error = "Invalid response format from PMC API"
                    self.logger.error(f"Authentication failed: {self.last_error}")
                    return False
            else:
                # Handle HTTP errors
                try:
                    error_data = response.json()
                    self.last_error = error_data.get('error', f'HTTP {response.status_code}')
                except:
                    self.last_error = f'HTTP {response.status_code}: {response.text}'
                
                self.logger.error(f"Authentication failed: {self.last_error}")
                return False
                
        except ConnectionError as e:
            self.last_error = f"Network error: {str(e)}"
            self.logger.error(f"Authentication failed: {self.last_error}")
            return False
        
        except TimeoutError as e:
            self.last_error = f"Request timeout: {str(e)}"
            self.logger.error(f"Authentication failed: {self.last_error}")
            return False
        
        except Exception as e:
            self.last_error = f"Unexpected error: {str(e)}"
            self.logger.error(f"Authentication failed: {self.last_error}")
            return False
        
        finally:
            # Reset authentication state on failure
            if not self.is_authenticated:
                self.last_auth_check = None
