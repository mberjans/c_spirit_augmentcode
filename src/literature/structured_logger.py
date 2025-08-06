"""
Structured Logging System with Correlation IDs and Metrics.

This module provides a comprehensive structured logging system that includes
correlation ID tracking, metrics collection, and performance monitoring for
literature access operations.
"""

import uuid
import time
import threading
from typing import Any, Dict, Optional, Union, List
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict, Counter
from loguru import logger
import json


class CorrelationContext:
    """Thread-local storage for correlation IDs."""
    
    def __init__(self):
        self._local = threading.local()
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for current thread."""
        self._local.correlation_id = correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get correlation ID for current thread."""
        return getattr(self._local, 'correlation_id', None)
    
    def clear_correlation_id(self) -> None:
        """Clear correlation ID for current thread."""
        if hasattr(self._local, 'correlation_id'):
            delattr(self._local, 'correlation_id')


class MetricsCollector:
    """Collects and aggregates metrics from log entries."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._operations = defaultdict(lambda: {
            'count': 0,
            'success_count': 0,
            'error_count': 0,
            'total_duration_ms': 0,
            'avg_duration_ms': 0.0,
            'min_duration_ms': float('inf'),
            'max_duration_ms': 0,
            'status_counts': Counter(),
            'error_types': Counter()
        })
        self._request_counts = Counter()
        self._error_counts = Counter()
    
    def record_operation(self, 
                        operation: str, 
                        duration_ms: Optional[float] = None,
                        status: str = "unknown",
                        error_type: Optional[str] = None) -> None:
        """Record an operation with its metrics."""
        with self._lock:
            op_metrics = self._operations[operation]
            op_metrics['count'] += 1
            op_metrics['status_counts'][status] += 1
            
            if status == 'success':
                op_metrics['success_count'] += 1
            elif status == 'error':
                op_metrics['error_count'] += 1
                if error_type:
                    op_metrics['error_types'][error_type] += 1
            
            if duration_ms is not None:
                op_metrics['total_duration_ms'] += duration_ms
                op_metrics['avg_duration_ms'] = op_metrics['total_duration_ms'] / op_metrics['count']
                op_metrics['min_duration_ms'] = min(op_metrics['min_duration_ms'], duration_ms)
                op_metrics['max_duration_ms'] = max(op_metrics['max_duration_ms'], duration_ms)
    
    def record_request(self, service: str) -> None:
        """Record a request to a service."""
        with self._lock:
            self._request_counts[service] += 1
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        with self._lock:
            self._error_counts[error_type] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        with self._lock:
            # Clean up infinite values for JSON serialization
            operations = {}
            for op_name, op_data in self._operations.items():
                operations[op_name] = dict(op_data)
                if operations[op_name]['min_duration_ms'] == float('inf'):
                    operations[op_name]['min_duration_ms'] = 0
                # Convert Counter objects to regular dicts
                operations[op_name]['status_counts'] = dict(operations[op_name]['status_counts'])
                operations[op_name]['error_types'] = dict(operations[op_name]['error_types'])
            
            return {
                'operations': operations,
                'request_counts': dict(self._request_counts),
                'error_counts': dict(self._error_counts),
                'timestamp': datetime.now().isoformat()
            }
    
    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        with self._lock:
            self._operations.clear()
            self._request_counts.clear()
            self._error_counts.clear()


class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, logger_instance: 'StructuredLogger', operation: str):
        self.logger = logger_instance
        self.operation = operation
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        self.duration_ms = (end_time - self.start_time) * 1000

        status = "error" if exc_type else "success"
        error_type = exc_type.__name__ if exc_type else None

        # Record metrics directly without logging to avoid double counting
        self.logger.metrics_collector.record_operation(
            self.operation,
            self.duration_ms,
            status,
            error_type
        )


class StructuredLogger:
    """
    Structured logger with correlation IDs and metrics collection.
    
    Provides structured logging capabilities with automatic correlation ID
    tracking, metrics collection, and performance monitoring.
    """
    
    def __init__(self, logger_name: str = "literature_access"):
        """
        Initialize structured logger.
        
        Args:
            logger_name: Name for the logger instance
        """
        self.logger_name = logger_name
        self.correlation_context = CorrelationContext()
        self.metrics_collector = MetricsCollector()
        
        # Configure loguru with structured format
        self._configure_logger()
    
    def _configure_logger(self) -> None:
        """Configure loguru logger with structured format."""
        # Remove default handler and add structured handler
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=''),
            format="{message}",  # Use simple format since we handle formatting in _format_log_record
            level="DEBUG"
        )
    
    def _format_log_record(self, record) -> str:
        """Format log record with structured data."""
        # Extract structured data from record
        extra_data = record.get("extra", {})

        # Build structured log entry
        log_entry = {
            'timestamp': record['time'].isoformat(),
            'level': record['level'].name,
            'logger': self.logger_name,
            'message': record['message'],
            'correlation_id': self.correlation_context.get_correlation_id(),
            'thread_id': getattr(record.get('thread'), 'id', None),
            'process_id': getattr(record.get('process'), 'id', None),
            'module': record.get('name'),
            'function': record.get('function'),
            'line': record.get('line')
        }

        # Add any extra structured data
        if extra_data:
            log_entry.update(extra_data)

        # Remove None values for cleaner output
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        return json.dumps(log_entry, default=str) + '\n'
    
    def generate_correlation_id(self) -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())
    
    def set_correlation_id(self, correlation_id: Optional[str] = None) -> str:
        """
        Set correlation ID for current context.
        
        Args:
            correlation_id: Correlation ID to set, or None to generate new one
            
        Returns:
            The correlation ID that was set
        """
        if correlation_id is None:
            correlation_id = self.generate_correlation_id()
        
        self.correlation_context.set_correlation_id(correlation_id)
        return correlation_id
    
    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return self.correlation_context.get_correlation_id()
    
    def clear_correlation_id(self) -> None:
        """Clear current correlation ID."""
        self.correlation_context.clear_correlation_id()
    
    def _log_with_structure(self, level: str, message: str, **kwargs) -> None:
        """Log message with structured data."""
        # Record metrics if operation is specified
        if 'operation' in kwargs:
            operation = kwargs['operation']
            duration_ms = kwargs.get('duration_ms')
            status = kwargs.get('status', 'unknown')
            error_type = kwargs.get('exception_type')

            self.metrics_collector.record_operation(operation, duration_ms, status, error_type)

        # Record service requests
        if 'service' in kwargs:
            self.metrics_collector.record_request(kwargs['service'])

        # Record errors
        if level.upper() == 'ERROR' and 'exception_type' in kwargs:
            self.metrics_collector.record_error(kwargs['exception_type'])

        # Add correlation ID to the log data
        correlation_id = self.correlation_context.get_correlation_id()
        if correlation_id:
            kwargs['correlation_id'] = correlation_id

        # Log with structured data
        getattr(logger, level.lower())(message, **kwargs)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with structured data."""
        self._log_with_structure('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with structured data."""
        self._log_with_structure('INFO', message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with structured data."""
        self._log_with_structure('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with structured data."""
        self._log_with_structure('ERROR', message, **kwargs)
    
    @contextmanager
    def time_operation(self, operation: str):
        """
        Context manager for timing operations.
        
        Args:
            operation: Name of the operation being timed
            
        Yields:
            OperationTimer instance
        """
        timer = OperationTimer(self, operation)
        with timer:
            yield timer
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        return self.metrics_collector.get_metrics()
    
    def reset_metrics(self) -> None:
        """Reset collected metrics."""
        self.metrics_collector.reset_metrics()


# Global structured logger instance
structured_logger = StructuredLogger()
