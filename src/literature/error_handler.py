"""
Robust Error Handling with Exponential Backoff.

This module provides comprehensive error handling mechanisms including
exponential backoff, circuit breaker patterns, and retry logic for
literature access operations.
"""

import time
import random
import asyncio
from typing import Any, Callable, Dict, List, Optional, Type, Union, Tuple
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
import requests
from requests.exceptions import (
    ConnectionError, Timeout, HTTPError, RequestException,
    SSLError, ProxyError, ChunkedEncodingError
)
from .structured_logger import structured_logger


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class RetryableError(Exception):
    """Base class for retryable errors."""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        super().__init__(message)
        self.severity = severity


class NonRetryableError(Exception):
    """Base class for non-retryable errors."""
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.HIGH):
        super().__init__(message)
        self.severity = severity


class ExponentialBackoff:
    """
    Exponential backoff implementation with jitter.
    
    Provides configurable exponential backoff with optional jitter
    to prevent thundering herd problems.
    """
    
    def __init__(self, 
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 multiplier: float = 2.0,
                 jitter: bool = True,
                 max_jitter: float = 0.1):
        """
        Initialize exponential backoff.
        
        Args:
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Backoff multiplier
            jitter: Whether to add random jitter
            max_jitter: Maximum jitter as fraction of delay
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.max_jitter = max_jitter
        self.attempt = 0
    
    def get_delay(self) -> float:
        """
        Calculate delay for current attempt.
        
        Returns:
            Delay in seconds
        """
        delay = min(self.base_delay * (self.multiplier ** self.attempt), self.max_delay)
        
        if self.jitter:
            jitter_amount = delay * self.max_jitter * random.random()
            delay += jitter_amount
        
        return delay
    
    def sleep(self) -> None:
        """Sleep for the calculated delay."""
        delay = self.get_delay()
        time.sleep(delay)
        self.attempt += 1
    
    async def async_sleep(self) -> None:
        """Async sleep for the calculated delay."""
        delay = self.get_delay()
        await asyncio.sleep(delay)
        self.attempt += 1
    
    def reset(self) -> None:
        """Reset the backoff attempt counter."""
        self.attempt = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    Prevents cascading failures by temporarily stopping requests
    to a failing service.
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

        self.logger = structured_logger
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        return (self.state == CircuitBreakerState.OPEN and
                self.last_failure_time and
                time.time() - self.last_failure_time >= self.recovery_timeout)
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.logger.info(
                    "Circuit breaker attempting reset",
                    operation="circuit_breaker_reset",
                    state="half_open",
                    failure_count=self.failure_count
                )
            else:
                raise NonRetryableError(
                    f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}",
                    ErrorSeverity.HIGH
                )
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset circuit breaker if it was half-open
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.logger.info(
                    "Circuit breaker reset to CLOSED",
                    operation="circuit_breaker_reset",
                    state="closed",
                    status="success"
                )
            
            return result
            
        except self.expected_exception as e:
            self._record_failure()
            raise
    
    def _record_failure(self) -> None:
        """Record a failure and update circuit breaker state."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning(
                "Circuit breaker opened due to failure threshold",
                operation="circuit_breaker_open",
                failure_count=self.failure_count,
                failure_threshold=self.failure_threshold,
                state="open",
                status="error"
            )
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.logger.info(
            "Circuit breaker manually reset",
            operation="circuit_breaker_manual_reset",
            state="closed",
            status="success"
        )


class ErrorClassifier:
    """
    Classifies errors for retry decisions.
    
    Determines whether an error is retryable and its severity level.
    """
    
    # Retryable HTTP status codes
    RETRYABLE_STATUS_CODES = {
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }
    
    # Non-retryable HTTP status codes
    NON_RETRYABLE_STATUS_CODES = {
        400,  # Bad Request
        401,  # Unauthorized
        403,  # Forbidden
        404,  # Not Found
        405,  # Method Not Allowed
        406,  # Not Acceptable
        409,  # Conflict
        410,  # Gone
        422,  # Unprocessable Entity
    }
    
    @classmethod
    def classify_exception(cls, exception: Exception) -> Tuple[bool, ErrorSeverity]:
        """
        Classify an exception for retry decisions.
        
        Args:
            exception: Exception to classify
            
        Returns:
            Tuple of (is_retryable, severity)
        """
        # Network-related errors - usually retryable
        if isinstance(exception, (ConnectionError, Timeout)):
            return True, ErrorSeverity.MEDIUM
        
        # SSL errors - usually not retryable
        if isinstance(exception, SSLError):
            return False, ErrorSeverity.HIGH
        
        # Proxy errors - may be retryable
        if isinstance(exception, ProxyError):
            return True, ErrorSeverity.MEDIUM
        
        # Chunked encoding errors - usually retryable
        if isinstance(exception, ChunkedEncodingError):
            return True, ErrorSeverity.LOW
        
        # HTTP errors - depends on status code
        if isinstance(exception, HTTPError):
            if hasattr(exception, 'response') and exception.response:
                status_code = exception.response.status_code
                
                if status_code in cls.RETRYABLE_STATUS_CODES:
                    severity = ErrorSeverity.HIGH if status_code >= 500 else ErrorSeverity.MEDIUM
                    return True, severity
                elif status_code in cls.NON_RETRYABLE_STATUS_CODES:
                    severity = ErrorSeverity.CRITICAL if status_code == 401 else ErrorSeverity.HIGH
                    return False, severity
            
            # Unknown HTTP error - be conservative
            return False, ErrorSeverity.HIGH
        
        # Generic request exceptions - may be retryable
        if isinstance(exception, RequestException):
            return True, ErrorSeverity.MEDIUM
        
        # Unknown exceptions - not retryable by default
        return False, ErrorSeverity.CRITICAL
    
    @classmethod
    def should_retry(cls, exception: Exception, attempt: int, max_attempts: int) -> bool:
        """
        Determine if an operation should be retried.
        
        Args:
            exception: Exception that occurred
            attempt: Current attempt number (0-based)
            max_attempts: Maximum number of attempts
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_attempts - 1:
            return False
        
        is_retryable, severity = cls.classify_exception(exception)
        
        # Don't retry critical errors
        if severity == ErrorSeverity.CRITICAL:
            return False
        
        return is_retryable


class RobustErrorHandler:
    """
    Comprehensive error handler with retry logic and circuit breaker.
    
    Combines exponential backoff, circuit breaker, and error classification
    for robust error handling in literature access operations.
    """
    
    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 circuit_breaker_threshold: int = 5,
                 circuit_breaker_timeout: float = 300.0):
        """
        Initialize robust error handler.
        
        Args:
            max_attempts: Maximum retry attempts
            base_delay: Initial backoff delay
            max_delay: Maximum backoff delay
            circuit_breaker_threshold: Circuit breaker failure threshold
            circuit_breaker_timeout: Circuit breaker recovery timeout
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        
        self.circuit_breakers = {}
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        self.logger = structured_logger
    
    def _get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                failure_threshold=self.circuit_breaker_threshold,
                recovery_timeout=self.circuit_breaker_timeout
            )
        return self.circuit_breakers[service_name]
    
    def execute_with_retry(self,
                          func: Callable,
                          service_name: str = "default",
                          *args,
                          **kwargs) -> Any:
        """
        Execute function with retry logic and circuit breaker.
        
        Args:
            func: Function to execute
            service_name: Service name for circuit breaker
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail or circuit breaker is open
        """
        circuit_breaker = self._get_circuit_breaker(service_name)
        backoff = ExponentialBackoff(
            base_delay=self.base_delay,
            max_delay=self.max_delay
        )
        
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                # Execute with circuit breaker protection
                result = circuit_breaker.call(func, *args, **kwargs)
                
                # Success - reset backoff
                backoff.reset()
                return result
                
            except Exception as e:
                last_exception = e
                
                # Log the error with structured data
                is_retryable, severity = ErrorClassifier.classify_exception(e)
                self.logger.warning(
                    "Operation attempt failed",
                    operation="retry_attempt",
                    service=service_name,
                    attempt=attempt + 1,
                    max_attempts=self.max_attempts,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    is_retryable=is_retryable,
                    severity=severity.value,
                    status="error"
                )
                
                # Check if we should retry
                if not ErrorClassifier.should_retry(e, attempt, self.max_attempts):
                    self.logger.error(
                        "Non-retryable error encountered",
                        operation="retry_failed",
                        service=service_name,
                        error_message=str(e),
                        error_type=type(e).__name__,
                        attempt=attempt + 1,
                        status="error"
                    )
                    raise
                
                # Don't sleep on the last attempt
                if attempt < self.max_attempts - 1:
                    backoff.sleep()
        
        # All retries exhausted
        self.logger.error(
            "All retry attempts exhausted",
            operation="retry_exhausted",
            service=service_name,
            max_attempts=self.max_attempts,
            final_error=str(last_exception) if last_exception else None,
            final_error_type=type(last_exception).__name__ if last_exception else None,
            status="error"
        )
        raise last_exception
    
    async def async_execute_with_retry(self,
                                     func: Callable,
                                     service_name: str = "default",
                                     *args,
                                     **kwargs) -> Any:
        """
        Async version of execute_with_retry.
        
        Args:
            func: Async function to execute
            service_name: Service name for circuit breaker
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries fail or circuit breaker is open
        """
        circuit_breaker = self._get_circuit_breaker(service_name)
        backoff = ExponentialBackoff(
            base_delay=self.base_delay,
            max_delay=self.max_delay
        )
        
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                # For async, we need to handle circuit breaker manually
                if circuit_breaker.state == CircuitBreakerState.OPEN:
                    if circuit_breaker._should_attempt_reset():
                        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
                    else:
                        raise NonRetryableError(
                            f"Circuit breaker is OPEN for {service_name}",
                            ErrorSeverity.HIGH
                        )
                
                result = await func(*args, **kwargs)
                
                # Success - reset circuit breaker if half-open
                if circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
                    circuit_breaker.state = CircuitBreakerState.CLOSED
                    circuit_breaker.failure_count = 0
                
                backoff.reset()
                return result
                
            except Exception as e:
                last_exception = e
                circuit_breaker._record_failure()
                
                is_retryable, severity = ErrorClassifier.classify_exception(e)
                self.logger.warning(
                    "Async operation attempt failed",
                    operation="async_retry_attempt",
                    service=service_name,
                    attempt=attempt + 1,
                    max_attempts=self.max_attempts,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    is_retryable=is_retryable,
                    severity=severity.value,
                    status="error"
                )
                
                if not ErrorClassifier.should_retry(e, attempt, self.max_attempts):
                    self.logger.error(
                        "Non-retryable async error encountered",
                        operation="async_retry_failed",
                        service=service_name,
                        error_message=str(e),
                        error_type=type(e).__name__,
                        attempt=attempt + 1,
                        status="error"
                    )
                    raise
                
                if attempt < self.max_attempts - 1:
                    await backoff.async_sleep()
        
        self.logger.error(
            "All async retry attempts exhausted",
            operation="async_retry_exhausted",
            service=service_name,
            max_attempts=self.max_attempts,
            final_error=str(last_exception) if last_exception else None,
            final_error_type=type(last_exception).__name__ if last_exception else None,
            status="error"
        )
        raise last_exception
    
    def reset_circuit_breaker(self, service_name: str) -> None:
        """Reset circuit breaker for a specific service."""
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name].reset()
    
    def get_circuit_breaker_status(self, service_name: str) -> Dict[str, Any]:
        """Get circuit breaker status for a service."""
        if service_name not in self.circuit_breakers:
            return {"state": "not_initialized"}
        
        cb = self.circuit_breakers[service_name]
        return {
            "state": cb.state.value,
            "failure_count": cb.failure_count,
            "last_failure_time": cb.last_failure_time,
            "failure_threshold": cb.failure_threshold,
            "recovery_timeout": cb.recovery_timeout
        }


def retry_on_error(max_attempts: int = 3,
                  base_delay: float = 1.0,
                  max_delay: float = 60.0,
                  service_name: str = "default"):
    """
    Decorator for adding retry logic to functions.
    
    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial backoff delay
        max_delay: Maximum backoff delay
        service_name: Service name for circuit breaker
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = RobustErrorHandler(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay
            )
            return handler.execute_with_retry(func, service_name, *args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = RobustErrorHandler(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay
            )
            return await handler.async_execute_with_retry(func, service_name, *args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator
