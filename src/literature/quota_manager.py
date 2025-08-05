"""
Quota Management and Rate Limiting for Literature APIs.

This module provides quota tracking and rate limiting functionality for
managing API usage across multiple publisher APIs with configurable
limits and automatic enforcement.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from loguru import logger


class QuotaTracker:
    """
    Tracks API usage quotas for daily, hourly, and minute limits.
    
    This class maintains usage counters and provides methods to check
    if requests are within configured quota limits.
    """
    
    def __init__(self, api_name: str, config: Dict[str, Any]):
        """
        Initialize the quota tracker.
        
        Args:
            api_name: Name of the API
            config: Configuration dictionary with quota limits
        """
        self.api_name = api_name
        self.daily_limit = config.get('daily_limit', float('inf'))
        self.hourly_limit = config.get('hourly_limit', float('inf'))
        self.minute_limit = config.get('minute_limit', float('inf'))
        
        # Current usage counters
        self.current_usage = {
            'daily': 0,
            'hourly': 0,
            'minute': 0
        }
        
        # Timestamps for quota reset
        self.last_reset = {
            'daily': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            'hourly': datetime.now().replace(minute=0, second=0, microsecond=0),
            'minute': datetime.now().replace(second=0, microsecond=0)
        }
        
        self.lock = threading.Lock()
        self.logger = logger
    
    def _check_and_reset_quotas(self):
        """Check if quotas need to be reset based on time periods."""
        now = datetime.now()
        
        # Check daily reset
        if now.date() > self.last_reset['daily'].date():
            self.current_usage['daily'] = 0
            self.last_reset['daily'] = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Check hourly reset
        if now.replace(minute=0, second=0, microsecond=0) > self.last_reset['hourly']:
            self.current_usage['hourly'] = 0
            self.last_reset['hourly'] = now.replace(minute=0, second=0, microsecond=0)
        
        # Check minute reset
        if now.replace(second=0, microsecond=0) > self.last_reset['minute']:
            self.current_usage['minute'] = 0
            self.last_reset['minute'] = now.replace(second=0, microsecond=0)
    
    def increment_usage(self) -> bool:
        """
        Increment usage counters.
        
        Returns:
            True if increment successful, False if would exceed limits
        """
        with self.lock:
            self._check_and_reset_quotas()
            
            # Check if incrementing would exceed any limit
            if (self.current_usage['daily'] + 1 > self.daily_limit or
                self.current_usage['hourly'] + 1 > self.hourly_limit or
                self.current_usage['minute'] + 1 > self.minute_limit):
                return False
            
            # Increment all counters
            self.current_usage['daily'] += 1
            self.current_usage['hourly'] += 1
            self.current_usage['minute'] += 1
            
            return True
    
    def is_under_limit(self) -> bool:
        """
        Check if current usage is under all quota limits.
        
        Returns:
            True if under all limits, False otherwise
        """
        with self.lock:
            self._check_and_reset_quotas()
            
            return (self.current_usage['daily'] < self.daily_limit and
                    self.current_usage['hourly'] < self.hourly_limit and
                    self.current_usage['minute'] < self.minute_limit)
    
    def get_limiting_quota(self) -> Optional[str]:
        """
        Get which quota is currently limiting requests.
        
        Returns:
            Name of limiting quota ('daily', 'hourly', 'minute') or None
        """
        with self.lock:
            self._check_and_reset_quotas()
            
            if self.current_usage['minute'] >= self.minute_limit:
                return 'minute'
            elif self.current_usage['hourly'] >= self.hourly_limit:
                return 'hourly'
            elif self.current_usage['daily'] >= self.daily_limit:
                return 'daily'
            
            return None
    
    def reset_quota(self, quota_type: str):
        """
        Reset a specific quota counter.
        
        Args:
            quota_type: Type of quota to reset ('daily', 'hourly', 'minute')
        """
        with self.lock:
            if quota_type in self.current_usage:
                self.current_usage[quota_type] = 0
                self.last_reset[quota_type] = datetime.now()
    
    def reset_all_quotas(self):
        """Reset all quota counters."""
        with self.lock:
            now = datetime.now()
            for quota_type in self.current_usage:
                self.current_usage[quota_type] = 0
                self.last_reset[quota_type] = now


class RateLimiter:
    """
    Token bucket rate limiter for API requests.
    
    This class implements a token bucket algorithm to enforce
    rate limits with burst capacity.
    """
    
    def __init__(self, api_name: str, config: Dict[str, Any]):
        """
        Initialize the rate limiter.
        
        Args:
            api_name: Name of the API
            config: Configuration dictionary with rate limiting settings
        """
        self.api_name = api_name
        self.requests_per_second = config.get('requests_per_second', 1.0)
        self.burst_limit = config.get('burst_limit', 1)
        
        # Token bucket state
        self.tokens = self.burst_limit
        self.last_refill = time.time()
        
        self.lock = threading.Lock()
        self.logger = logger
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Calculate tokens to add
        tokens_to_add = elapsed * self.requests_per_second
        
        # Add tokens up to burst limit
        self.tokens = min(self.burst_limit, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def can_make_request(self) -> bool:
        """
        Check if a request can be made (has available tokens).
        
        Returns:
            True if request can be made, False otherwise
        """
        with self.lock:
            self._refill_tokens()
            return self.tokens >= 1
    
    def consume_token(self) -> bool:
        """
        Consume a token for making a request.
        
        Returns:
            True if token consumed successfully, False if no tokens available
        """
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            
            return False
    
    def get_wait_time(self) -> float:
        """
        Get time to wait before next request can be made.
        
        Returns:
            Wait time in seconds
        """
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= 1:
                return 0.0
            
            # Calculate time needed to get one token
            return (1.0 - self.tokens) / self.requests_per_second


class QuotaManager:
    """
    Centralized manager for quota tracking and rate limiting.
    
    This class coordinates quota tracking and rate limiting for
    multiple APIs with unified interface and management.
    """
    
    def __init__(self, config: Dict[str, Dict[str, Any]]):
        """
        Initialize the quota manager.
        
        Args:
            config: Dictionary mapping API names to their configurations
        """
        self.config = config
        self.quota_trackers = {}
        self.rate_limiters = {}
        self.logger = logger
        
        # Initialize trackers and limiters for each API
        for api_name, api_config in config.items():
            self.quota_trackers[api_name] = QuotaTracker(api_name, api_config)
            self.rate_limiters[api_name] = RateLimiter(api_name, api_config)
    
    def can_make_request(self, api_name: str) -> bool:
        """
        Check if a request can be made for the specified API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            True if request can be made, False otherwise
        """
        if api_name not in self.quota_trackers:
            self.logger.warning(f"Unknown API: {api_name}")
            return False
        
        quota_tracker = self.quota_trackers[api_name]
        rate_limiter = self.rate_limiters[api_name]
        
        return quota_tracker.is_under_limit() and rate_limiter.can_make_request()
    
    def record_request(self, api_name: str) -> bool:
        """
        Record a request for the specified API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            True if request recorded successfully, False otherwise
        """
        if api_name not in self.quota_trackers:
            self.logger.warning(f"Unknown API: {api_name}")
            return False
        
        quota_tracker = self.quota_trackers[api_name]
        rate_limiter = self.rate_limiters[api_name]
        
        # Consume rate limit token and increment quota
        if rate_limiter.consume_token() and quota_tracker.increment_usage():
            return True
        
        return False
    
    def get_wait_time(self, api_name: str) -> Optional[float]:
        """
        Get wait time before next request can be made.
        
        Args:
            api_name: Name of the API
            
        Returns:
            Wait time in seconds or None if API unknown
        """
        if api_name not in self.rate_limiters:
            return None
        
        return self.rate_limiters[api_name].get_wait_time()
    
    def get_limiting_quota(self, api_name: str) -> Optional[str]:
        """
        Get which quota is limiting requests for the API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            Limiting quota type or None
        """
        if api_name not in self.quota_trackers:
            return None
        
        return self.quota_trackers[api_name].get_limiting_quota()
    
    def reset_quotas(self, api_name: str):
        """
        Reset quotas for the specified API.
        
        Args:
            api_name: Name of the API
        """
        if api_name in self.quota_trackers:
            self.quota_trackers[api_name].reset_all_quotas()


class QuotaMiddleware:
    """
    Middleware for intercepting and managing API requests with quota enforcement.
    
    This class provides a decorator-like interface for wrapping API calls
    with automatic quota and rate limit enforcement.
    """
    
    def __init__(self, config: Dict[str, Dict[str, Any]]):
        """
        Initialize the quota middleware.
        
        Args:
            config: Dictionary mapping API names to their configurations
        """
        self.quota_manager = QuotaManager(config)
        self.logger = logger
    
    def intercept_request(self, api_name: str, request_func: Callable) -> Any:
        """
        Intercept and manage an API request.
        
        Args:
            api_name: Name of the API
            request_func: Function to execute for the request
            
        Returns:
            Result of the request function
            
        Raises:
            Exception: If quota or rate limits are exceeded
        """
        # Check if request can be made
        if not self.quota_manager.can_make_request(api_name):
            limiting_quota = self.quota_manager.get_limiting_quota(api_name)
            wait_time = self.quota_manager.get_wait_time(api_name)
            
            if limiting_quota:
                raise Exception(f"Quota limit exceeded for {api_name}: {limiting_quota}")
            elif wait_time and wait_time > 0:
                raise Exception(f"Rate limit exceeded for {api_name}: wait {wait_time:.2f}s")
        
        # Record the request
        if not self.quota_manager.record_request(api_name):
            raise Exception(f"Failed to record request for {api_name}")
        
        # Execute the request
        try:
            result = request_func()
            self.logger.debug(f"Request completed for {api_name}")
            return result
        except Exception as e:
            self.logger.error(f"Request failed for {api_name}: {str(e)}")
            raise
