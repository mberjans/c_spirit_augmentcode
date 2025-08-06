"""
Multi-Ontology Integration System.

This module provides functionality for integrating terms from multiple source
ontologies into a unified system with conflict resolution and mapping capabilities.

The integration system handles:
- Downloading and processing 8 source ontologies
- Concept mapping and equivalence detection
- Conflict resolution with precedence rules
- Unified ontology generation
"""

from .ontology_downloader import OntologyDownloader

__all__ = [
    'OntologyDownloader'
]
