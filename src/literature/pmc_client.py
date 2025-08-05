"""
PubMed Central (PMC) API Client.

This module provides a client for accessing PubMed Central articles through
the NCBI E-utilities API with proper authentication, rate limiting, and
error handling.
"""

import os
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import aiohttp
from asyncio_throttle import Throttler
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

    def _validate_pmc_id(self, pmc_id: str) -> bool:
        """
        Validate PMC ID format.

        Args:
            pmc_id: PMC ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not pmc_id or not isinstance(pmc_id, str):
            return False

        # PMC IDs should start with 'PMC' followed by digits
        import re
        pattern = r'^PMC\d+$'
        return bool(re.match(pattern, pmc_id))

    def _validate_xml_content(self, content: bytes) -> bool:
        """
        Validate XML content format.

        Args:
            content: Content to validate

        Returns:
            True if valid XML, False otherwise
        """
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return True
        except ET.ParseError:
            return False
        except Exception:
            return False

    def download_articles(
        self,
        article_ids: List[str],
        progress_callback: Optional[callable] = None,
        validate_xml: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Download articles from PMC by their IDs.

        Args:
            article_ids: List of PMC IDs to download
            progress_callback: Optional callback function for progress updates
            validate_xml: Whether to validate XML content

        Returns:
            List of dictionaries containing download results

        Raises:
            ValueError: If authentication is required or invalid parameters
        """
        # Check authentication
        if not self.is_authenticated:
            raise ValueError("Authentication required. Call authenticate() first.")

        # Handle empty list
        if not article_ids:
            return []

        # Validate all PMC IDs first
        for pmc_id in article_ids:
            if pmc_id is None or pmc_id == '':
                raise ValueError("PMC ID cannot be None or empty")

            if not self._validate_pmc_id(pmc_id):
                raise ValueError(f"Invalid PMC ID format: {pmc_id}")

        results = []
        total_articles = len(article_ids)

        for index, pmc_id in enumerate(article_ids, 1):
            try:
                # Respect rate limiting
                self._respect_rate_limit()

                # Construct download URL
                download_url = f"{self.base_url}efetch.fcgi"
                params = {
                    'db': 'pmc',
                    'id': pmc_id,
                    'retmode': 'xml',
                    'api_key': self.config['api_key'],
                    'email': self.config['email']
                }

                # Make request
                response = self.session.get(
                    download_url,
                    params=params,
                    timeout=self.config.get('timeout', 30.0),
                    verify=self.config.get('verify_ssl', True)
                )

                # Process response
                if response.status_code == 200:
                    content = response.content

                    # Validate XML if requested
                    if validate_xml and not self._validate_xml_content(content):
                        results.append({
                            'pmc_id': pmc_id,
                            'status': 'error',
                            'error': 'Invalid XML content format'
                        })
                    else:
                        results.append({
                            'pmc_id': pmc_id,
                            'status': 'success',
                            'content': content,
                            'content_type': response.headers.get('content-type', 'application/xml'),
                            'size': len(content)
                        })
                else:
                    # Handle HTTP errors
                    error_message = f"HTTP {response.status_code}: {response.text}"
                    results.append({
                        'pmc_id': pmc_id,
                        'status': 'error',
                        'error': error_message
                    })

                    self.logger.warning(f"Failed to download {pmc_id}: {error_message}")

            except ConnectionError as e:
                error_message = f"Network error: {str(e)}"
                results.append({
                    'pmc_id': pmc_id,
                    'status': 'error',
                    'error': error_message
                })
                self.logger.error(f"Network error downloading {pmc_id}: {error_message}")

            except TimeoutError as e:
                error_message = f"Request timeout: {str(e)}"
                results.append({
                    'pmc_id': pmc_id,
                    'status': 'error',
                    'error': error_message
                })
                self.logger.error(f"Timeout downloading {pmc_id}: {error_message}")

            except Exception as e:
                error_message = f"Unexpected error: {str(e)}"
                results.append({
                    'pmc_id': pmc_id,
                    'status': 'error',
                    'error': error_message
                })
                self.logger.error(f"Unexpected error downloading {pmc_id}: {error_message}")

            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(index, total_articles, pmc_id)
                except Exception as e:
                    self.logger.warning(f"Progress callback error: {e}")

        self.logger.info(f"Downloaded {len(article_ids)} articles: "
                        f"{sum(1 for r in results if r['status'] == 'success')} successful, "
                        f"{sum(1 for r in results if r['status'] == 'error')} failed")

        return results

    async def download_articles_async(
        self,
        article_ids: List[str],
        progress_callback: Optional[callable] = None,
        validate_xml: bool = False,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Download articles from PMC asynchronously by their IDs.

        Args:
            article_ids: List of PMC IDs to download
            progress_callback: Optional callback function for progress updates
            validate_xml: Whether to validate XML content
            max_concurrent: Maximum number of concurrent requests

        Returns:
            List of dictionaries containing download results

        Raises:
            ValueError: If authentication is required or invalid parameters
        """
        # Check authentication
        if not self.is_authenticated:
            raise ValueError("Authentication required. Call authenticate() first.")

        # Handle empty list
        if not article_ids:
            return []

        # Validate all PMC IDs first
        for pmc_id in article_ids:
            if pmc_id is None or pmc_id == '':
                raise ValueError("PMC ID cannot be None or empty")

            if not self._validate_pmc_id(pmc_id):
                raise ValueError(f"Invalid PMC ID format: {pmc_id}")

        # Create throttler for rate limiting
        rate_limit_delay = self.config.get('rate_limit_delay', 0.34)
        throttler = Throttler(rate_limit=1/rate_limit_delay)

        # Create semaphore for concurrent request limiting
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create async session
        timeout = aiohttp.ClientTimeout(total=self.config.get('timeout', 30.0))
        connector = aiohttp.TCPConnector(verify_ssl=self.config.get('verify_ssl', True))

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': self.config.get('user_agent', 'C-Spirit PMC Client/1.0')}
        ) as session:
            # Create tasks for all downloads
            tasks = []
            for index, pmc_id in enumerate(article_ids, 1):
                task = self._download_single_article_async(
                    session, pmc_id, throttler, semaphore,
                    index, len(article_ids), progress_callback, validate_xml
                )
                tasks.append(task)

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle exceptions
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        'pmc_id': article_ids[i],
                        'status': 'error',
                        'error': f"Async execution error: {str(result)}"
                    })
                else:
                    processed_results.append(result)

        self.logger.info(f"Downloaded {len(article_ids)} articles asynchronously: "
                        f"{sum(1 for r in processed_results if r['status'] == 'success')} successful, "
                        f"{sum(1 for r in processed_results if r['status'] == 'error')} failed")

        return processed_results

    async def _download_single_article_async(
        self,
        session: aiohttp.ClientSession,
        pmc_id: str,
        throttler: Throttler,
        semaphore: asyncio.Semaphore,
        index: int,
        total: int,
        progress_callback: Optional[callable] = None,
        validate_xml: bool = False
    ) -> Dict[str, Any]:
        """
        Download a single article asynchronously.

        Args:
            session: aiohttp session
            pmc_id: PMC ID to download
            throttler: Rate limiting throttler
            semaphore: Concurrency limiting semaphore
            index: Current article index
            total: Total number of articles
            progress_callback: Optional progress callback
            validate_xml: Whether to validate XML content

        Returns:
            Dictionary containing download result
        """
        async with semaphore:
            async with throttler:
                try:
                    # Construct download URL
                    download_url = f"{self.base_url}efetch.fcgi"
                    params = {
                        'db': 'pmc',
                        'id': pmc_id,
                        'retmode': 'xml',
                        'api_key': self.config['api_key'],
                        'email': self.config['email']
                    }

                    # Make async request
                    async with session.get(download_url, params=params) as response:
                        if response.status == 200:
                            content = await response.read()

                            # Validate XML if requested
                            if validate_xml and not self._validate_xml_content(content):
                                result = {
                                    'pmc_id': pmc_id,
                                    'status': 'error',
                                    'error': 'Invalid XML content format'
                                }
                            else:
                                result = {
                                    'pmc_id': pmc_id,
                                    'status': 'success',
                                    'content': content,
                                    'content_type': response.headers.get('content-type', 'application/xml'),
                                    'size': len(content)
                                }
                        else:
                            # Handle HTTP errors
                            error_text = await response.text()
                            error_message = f"HTTP {response.status}: {error_text}"
                            result = {
                                'pmc_id': pmc_id,
                                'status': 'error',
                                'error': error_message
                            }
                            self.logger.warning(f"Failed to download {pmc_id}: {error_message}")

                except aiohttp.ClientError as e:
                    error_message = f"Client error: {str(e)}"
                    result = {
                        'pmc_id': pmc_id,
                        'status': 'error',
                        'error': error_message
                    }
                    self.logger.error(f"Client error downloading {pmc_id}: {error_message}")

                except asyncio.TimeoutError as e:
                    error_message = f"Request timeout: {str(e)}"
                    result = {
                        'pmc_id': pmc_id,
                        'status': 'error',
                        'error': error_message
                    }
                    self.logger.error(f"Timeout downloading {pmc_id}: {error_message}")

                except Exception as e:
                    error_message = f"Unexpected error: {str(e)}"
                    result = {
                        'pmc_id': pmc_id,
                        'status': 'error',
                        'error': error_message
                    }
                    self.logger.error(f"Unexpected error downloading {pmc_id}: {error_message}")

                # Call progress callback if provided
                if progress_callback:
                    try:
                        if asyncio.iscoroutinefunction(progress_callback):
                            await progress_callback(index, total, pmc_id)
                        else:
                            progress_callback(index, total, pmc_id)
                    except Exception as e:
                        self.logger.warning(f"Progress callback error: {e}")

                return result
