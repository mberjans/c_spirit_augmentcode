"""
Literature Access Module for C-Spirit Plant Metabolite Knowledge Extraction System.

This module provides functionality for accessing and downloading scientific literature
from various sources including PubMed Central (PMC), PubMed, and other academic databases.

Key Components:
- PMCClient: PubMed Central API client for article download
- PubMedClient: PubMed API client for metadata and search
- LiteratureProcessor: Text processing and extraction utilities
- DownloadManager: Coordinated download workflows with rate limiting

Usage:
    from src.literature import PMCClient, PubMedClient
    
    # Initialize clients
    pmc_client = PMCClient()
    pubmed_client = PubMedClient()
    
    # Download articles
    articles = pmc_client.download_articles(['PMC123456', 'PMC789012'])
"""

__version__ = "1.0.0"
__author__ = "C-Spirit Development Team"

# Import main classes when available
try:
    from .pmc_client import PMCClient
    from .pubmed_client import PubMedClient
    from .literature_processor import LiteratureProcessor
    from .download_manager import DownloadManager
    
    __all__ = [
        'PMCClient',
        'PubMedClient', 
        'LiteratureProcessor',
        'DownloadManager'
    ]
except ImportError:
    # Classes not yet implemented
    __all__ = []
