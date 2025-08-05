"""
Base test class for literature access module tests.

This module provides common test utilities and fixtures for testing
literature access functionality.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any, Optional


class LiteratureTestBase:
    """Base class for literature access tests with common utilities."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_pmc_response(self):
        """Sample PMC API response for testing."""
        return {
            'status': 'success',
            'articles': [
                {
                    'pmcid': 'PMC123456',
                    'title': 'Plant Metabolite Analysis in Arabidopsis',
                    'authors': ['Smith, J.', 'Johnson, A.'],
                    'journal': 'Plant Biology Journal',
                    'year': 2023,
                    'doi': '10.1234/example.2023.001',
                    'abstract': 'This study analyzes plant metabolites in Arabidopsis leaves and stems.',
                    'full_text_url': 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/',
                    'pdf_url': 'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123456/pdf/'
                }
            ]
        }
    
    @pytest.fixture
    def sample_pubmed_response(self):
        """Sample PubMed API response for testing."""
        return {
            'esearchresult': {
                'count': '2',
                'retmax': '2',
                'idlist': ['12345678', '87654321']
            }
        }
    
    @pytest.fixture
    def sample_article_metadata(self):
        """Sample article metadata for testing."""
        return {
            'pmid': '12345678',
            'pmcid': 'PMC123456',
            'title': 'Plant Metabolite Analysis',
            'authors': ['Smith, J.', 'Johnson, A.'],
            'journal': 'Plant Biology Journal',
            'year': 2023,
            'volume': '45',
            'issue': '3',
            'pages': '123-135',
            'doi': '10.1234/example.2023.001',
            'abstract': 'This study analyzes plant metabolites.',
            'keywords': ['plant metabolites', 'arabidopsis', 'leaf', 'stem'],
            'mesh_terms': ['Plants', 'Metabolomics', 'Arabidopsis']
        }
    
    @pytest.fixture
    def mock_http_response(self):
        """Mock HTTP response for testing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'status': 'success'}
        mock_response.text = 'Sample response text'
        mock_response.content = b'Sample response content'
        mock_response.headers = {'Content-Type': 'application/json'}
        return mock_response
    
    @pytest.fixture
    def mock_rate_limiter(self):
        """Mock rate limiter for testing."""
        mock_limiter = Mock()
        mock_limiter.acquire = Mock()
        mock_limiter.release = Mock()
        mock_limiter.wait_time = 1.0
        return mock_limiter
    
    def create_mock_config(self, **overrides):
        """Create a mock configuration with optional overrides."""
        default_config = {
            'pmc_api_key': 'test_api_key',
            'pubmed_email': 'test@example.com',
            'rate_limit_delay': 1.0,
            'max_retries': 3,
            'timeout': 30,
            'download_directory': '/tmp/literature',
            'file_formats': ['xml', 'pdf'],
            'batch_size': 10
        }
        default_config.update(overrides)
        return default_config
    
    def create_sample_article_xml(self):
        """Create sample article XML content for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
        <article>
            <front>
                <article-meta>
                    <title-group>
                        <article-title>Plant Metabolite Analysis</article-title>
                    </title-group>
                    <contrib-group>
                        <contrib contrib-type="author">
                            <name>
                                <surname>Smith</surname>
                                <given-names>John</given-names>
                            </name>
                        </contrib>
                    </contrib-group>
                    <abstract>
                        <p>This study analyzes plant metabolites in Arabidopsis.</p>
                    </abstract>
                </article-meta>
            </front>
            <body>
                <sec>
                    <title>Introduction</title>
                    <p>Plant metabolites play crucial roles in plant biology.</p>
                </sec>
                <sec>
                    <title>Methods</title>
                    <p>We analyzed leaf and stem tissues from Arabidopsis plants.</p>
                </sec>
                <sec>
                    <title>Results</title>
                    <p>We identified several key metabolites in plant tissues.</p>
                </sec>
            </body>
        </article>"""
    
    def assert_valid_article_data(self, article_data: Dict[str, Any]):
        """Assert that article data contains required fields."""
        required_fields = ['title', 'authors', 'journal', 'year']
        for field in required_fields:
            assert field in article_data, f"Missing required field: {field}"
        
        # Validate data types
        assert isinstance(article_data['title'], str)
        assert isinstance(article_data['authors'], list)
        assert isinstance(article_data['year'], int)
    
    def assert_valid_download_result(self, result: Dict[str, Any]):
        """Assert that download result is valid."""
        assert 'success' in result
        assert 'downloaded_count' in result
        assert 'failed_count' in result
        assert 'errors' in result
        
        assert isinstance(result['success'], bool)
        assert isinstance(result['downloaded_count'], int)
        assert isinstance(result['failed_count'], int)
        assert isinstance(result['errors'], list)
