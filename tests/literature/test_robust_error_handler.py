"""
Tests for Robust Error Handler with Exponential Backoff.

This module contains tests for the error handling components including
exponential backoff, circuit breaker, and retry logic.
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from requests.exceptions import ConnectionError, Timeout, HTTPError

from src.literature.error_handler import (
    ExponentialBackoff, CircuitBreaker, ErrorClassifier, RobustErrorHandler,
    ErrorSeverity, CircuitBreakerState, RetryableError, NonRetryableError,
    retry_on_error
)


class TestExponentialBackoff:
    """Test cases for ExponentialBackoff class."""
    
    def test_initialization(self):
        """Test exponential backoff initialization."""
        backoff = ExponentialBackoff(
            base_delay=2.0,
            max_delay=30.0,
            multiplier=3.0,
            jitter=False
        )
        
        assert backoff.base_delay == 2.0
        assert backoff.max_delay == 30.0
        assert backoff.multiplier == 3.0
        assert backoff.jitter is False
        assert backoff.attempt == 0
    
    def test_delay_calculation_without_jitter(self):
        """Test delay calculation without jitter."""
        backoff = ExponentialBackoff(
            base_delay=1.0,
            max_delay=10.0,
            multiplier=2.0,
            jitter=False
        )
        
        # First attempt
        assert backoff.get_delay() == 1.0
        backoff.attempt += 1
        
        # Second attempt
        assert backoff.get_delay() == 2.0
        backoff.attempt += 1
        
        # Third attempt
        assert backoff.get_delay() == 4.0
        backoff.attempt += 1
        
        # Fourth attempt (should be capped at max_delay)
        assert backoff.get_delay() == 8.0
        backoff.attempt += 1
        
        # Fifth attempt (should be capped at max_delay)
        assert backoff.get_delay() == 10.0
    
    def test_delay_calculation_with_jitter(self):
        """Test delay calculation with jitter."""
        backoff = ExponentialBackoff(
            base_delay=1.0,
            max_delay=10.0,
            multiplier=2.0,
            jitter=True,
            max_jitter=0.1
        )
        
        # With jitter, delay should be slightly different each time
        delay1 = backoff.get_delay()
        delay2 = backoff.get_delay()
        
        # Both should be around 1.0 but slightly different due to jitter
        assert 1.0 <= delay1 <= 1.1
        assert 1.0 <= delay2 <= 1.1
    
    def test_reset(self):
        """Test backoff reset functionality."""
        backoff = ExponentialBackoff()
        
        # Advance attempts
        backoff.attempt = 5
        
        # Reset
        backoff.reset()
        
        assert backoff.attempt == 0
    
    @pytest.mark.asyncio
    async def test_async_sleep(self):
        """Test async sleep functionality."""
        backoff = ExponentialBackoff(base_delay=0.01, jitter=False)
        
        start_time = time.time()
        await backoff.async_sleep()
        end_time = time.time()
        
        # Should have slept for approximately base_delay
        assert 0.005 <= end_time - start_time <= 0.02
        assert backoff.attempt == 1


class TestCircuitBreaker:
    """Test cases for CircuitBreaker class."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            expected_exception=ValueError
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.expected_exception == ValueError
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    def test_successful_call(self):
        """Test successful function call through circuit breaker."""
        cb = CircuitBreaker()
        
        def successful_function():
            return "success"
        
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_opening(self):
        """Test circuit breaker opening after failures."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def failing_function():
            raise Exception("Test failure")
        
        # First failure
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 2
    
    def test_circuit_breaker_open_state(self):
        """Test circuit breaker behavior in open state."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger circuit breaker
        with pytest.raises(Exception):
            cb.call(failing_function)
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Should raise NonRetryableError when circuit is open
        with pytest.raises(NonRetryableError):
            cb.call(failing_function)
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        
        def failing_function():
            raise Exception("Test failure")
        
        def successful_function():
            return "success"
        
        # Trigger circuit breaker
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Should attempt recovery (half-open state)
        result = cb.call(successful_function)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
    
    def test_manual_reset(self):
        """Test manual circuit breaker reset."""
        cb = CircuitBreaker(failure_threshold=1)
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger circuit breaker
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitBreakerState.OPEN
        
        # Manual reset
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestErrorClassifier:
    """Test cases for ErrorClassifier class."""
    
    def test_connection_error_classification(self):
        """Test classification of connection errors."""
        error = ConnectionError("Connection failed")
        is_retryable, severity = ErrorClassifier.classify_exception(error)
        
        assert is_retryable is True
        assert severity == ErrorSeverity.MEDIUM
    
    def test_timeout_error_classification(self):
        """Test classification of timeout errors."""
        error = Timeout("Request timed out")
        is_retryable, severity = ErrorClassifier.classify_exception(error)
        
        assert is_retryable is True
        assert severity == ErrorSeverity.MEDIUM
    
    def test_http_error_classification_retryable(self):
        """Test classification of retryable HTTP errors."""
        # Mock response with 500 status
        mock_response = Mock()
        mock_response.status_code = 500
        
        error = HTTPError("Internal Server Error")
        error.response = mock_response
        
        is_retryable, severity = ErrorClassifier.classify_exception(error)
        
        assert is_retryable is True
        assert severity == ErrorSeverity.HIGH
    
    def test_http_error_classification_non_retryable(self):
        """Test classification of non-retryable HTTP errors."""
        # Mock response with 404 status
        mock_response = Mock()
        mock_response.status_code = 404
        
        error = HTTPError("Not Found")
        error.response = mock_response
        
        is_retryable, severity = ErrorClassifier.classify_exception(error)
        
        assert is_retryable is False
        assert severity == ErrorSeverity.HIGH
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        # Retryable error within attempt limit
        error = ConnectionError("Connection failed")
        assert ErrorClassifier.should_retry(error, 0, 3) is True
        assert ErrorClassifier.should_retry(error, 1, 3) is True
        assert ErrorClassifier.should_retry(error, 2, 3) is False  # Last attempt
        
        # Non-retryable error
        mock_response = Mock()
        mock_response.status_code = 404
        error = HTTPError("Not Found")
        error.response = mock_response
        assert ErrorClassifier.should_retry(error, 0, 3) is False


class TestRobustErrorHandler:
    """Test cases for RobustErrorHandler class."""
    
    def test_initialization(self):
        """Test error handler initialization."""
        handler = RobustErrorHandler(
            max_attempts=5,
            base_delay=2.0,
            max_delay=30.0,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=60.0
        )
        
        assert handler.max_attempts == 5
        assert handler.base_delay == 2.0
        assert handler.max_delay == 30.0
        assert handler.circuit_breaker_threshold == 3
        assert handler.circuit_breaker_timeout == 60.0
    
    def test_successful_execution(self):
        """Test successful function execution."""
        handler = RobustErrorHandler()
        
        def successful_function():
            return "success"
        
        result = handler.execute_with_retry(successful_function, "test_service")
        assert result == "success"
    
    def test_retry_on_retryable_error(self):
        """Test retry behavior on retryable errors."""
        handler = RobustErrorHandler(max_attempts=3, base_delay=0.01)
        
        call_count = 0
        
        def failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = handler.execute_with_retry(failing_then_succeeding_function, "test_service")
        assert result == "success"
        assert call_count == 3
    
    def test_no_retry_on_non_retryable_error(self):
        """Test no retry on non-retryable errors."""
        handler = RobustErrorHandler(max_attempts=3)
        
        call_count = 0
        
        def non_retryable_failing_function():
            nonlocal call_count
            call_count += 1
            # Create non-retryable HTTP error
            mock_response = Mock()
            mock_response.status_code = 404
            error = HTTPError("Not Found")
            error.response = mock_response
            raise error
        
        with pytest.raises(HTTPError):
            handler.execute_with_retry(non_retryable_failing_function, "test_service")
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    def test_max_attempts_exhausted(self):
        """Test behavior when max attempts are exhausted."""
        handler = RobustErrorHandler(max_attempts=2, base_delay=0.01)
        
        call_count = 0
        
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Connection failed")
        
        with pytest.raises(ConnectionError):
            handler.execute_with_retry(always_failing_function, "test_service")
        
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_async_execution(self):
        """Test async function execution."""
        handler = RobustErrorHandler()
        
        async def async_successful_function():
            return "async_success"
        
        result = await handler.async_execute_with_retry(async_successful_function, "test_service")
        assert result == "async_success"
    
    @pytest.mark.asyncio
    async def test_async_retry_on_error(self):
        """Test async retry behavior."""
        handler = RobustErrorHandler(max_attempts=3, base_delay=0.01)
        
        call_count = 0
        
        async def async_failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "async_success"
        
        result = await handler.async_execute_with_retry(
            async_failing_then_succeeding_function, "test_service"
        )
        assert result == "async_success"
        assert call_count == 3
    
    def test_circuit_breaker_status(self):
        """Test circuit breaker status reporting."""
        handler = RobustErrorHandler()
        
        # Initially no circuit breaker
        status = handler.get_circuit_breaker_status("test_service")
        assert status["state"] == "not_initialized"
        
        # Create circuit breaker by making a call
        def test_function():
            return "test"
        
        handler.execute_with_retry(test_function, "test_service")
        
        # Now should have status
        status = handler.get_circuit_breaker_status("test_service")
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
    
    def test_circuit_breaker_reset(self):
        """Test circuit breaker reset functionality."""
        handler = RobustErrorHandler(circuit_breaker_threshold=1)
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger circuit breaker
        with pytest.raises(Exception):
            handler.execute_with_retry(failing_function, "test_service")
        
        status = handler.get_circuit_breaker_status("test_service")
        assert status["state"] == "open"
        
        # Reset circuit breaker
        handler.reset_circuit_breaker("test_service")
        
        status = handler.get_circuit_breaker_status("test_service")
        assert status["state"] == "closed"


class TestRetryDecorator:
    """Test cases for retry decorator."""
    
    def test_decorator_on_successful_function(self):
        """Test decorator on successful function."""
        @retry_on_error(max_attempts=3, base_delay=0.01)
        def successful_function():
            return "decorated_success"
        
        result = successful_function()
        assert result == "decorated_success"
    
    def test_decorator_on_failing_function(self):
        """Test decorator on failing function."""
        call_count = 0
        
        @retry_on_error(max_attempts=3, base_delay=0.01)
        def failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "decorated_success"
        
        result = failing_then_succeeding_function()
        assert result == "decorated_success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_decorator_on_async_function(self):
        """Test decorator on async function."""
        call_count = 0
        
        @retry_on_error(max_attempts=3, base_delay=0.01)
        async def async_failing_then_succeeding_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "async_decorated_success"
        
        result = await async_failing_then_succeeding_function()
        assert result == "async_decorated_success"
        assert call_count == 2


class TestIntegrationScenarios:
    """Integration test scenarios."""
    
    def test_real_world_api_failure_scenario(self):
        """Test realistic API failure scenario."""
        handler = RobustErrorHandler(
            max_attempts=4,
            base_delay=0.01,
            circuit_breaker_threshold=5  # Higher threshold to allow retries
        )
        
        call_count = 0
        
        def simulated_api_call():
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call: connection error
                raise ConnectionError("DNS resolution failed")
            elif call_count == 2:
                # Second call: timeout
                raise Timeout("Request timed out")
            elif call_count == 3:
                # Third call: server error
                mock_response = Mock()
                mock_response.status_code = 503
                error = HTTPError("Service Unavailable")
                error.response = mock_response
                raise error
            else:
                # Fourth call: success
                return {"data": "api_response"}
        
        result = handler.execute_with_retry(simulated_api_call, "api_service")
        assert result == {"data": "api_response"}
        assert call_count == 4
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with retry logic."""
        handler = RobustErrorHandler(
            max_attempts=2,
            base_delay=0.01,
            circuit_breaker_threshold=2
        )
        
        def always_failing_function():
            raise Exception("Always fails")
        
        # First set of attempts - should exhaust retries and open circuit
        with pytest.raises(Exception):
            handler.execute_with_retry(always_failing_function, "failing_service")
        
        # Second set of attempts - should open circuit breaker
        with pytest.raises(Exception):
            handler.execute_with_retry(always_failing_function, "failing_service")
        
        # Third attempt - circuit should be open
        with pytest.raises(NonRetryableError):
            handler.execute_with_retry(always_failing_function, "failing_service")
        
        status = handler.get_circuit_breaker_status("failing_service")
        assert status["state"] == "open"
