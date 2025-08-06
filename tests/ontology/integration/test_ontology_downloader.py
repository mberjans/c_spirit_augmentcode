"""
Tests for Ontology Downloader Module.

This module tests the functionality of downloading and caching source ontologies
from various repositories with proper error handling and metadata management.
"""

import pytest
import json
import tempfile
import shutil
import requests
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from src.ontology.integration.ontology_downloader import OntologyDownloader, OntologySource


class TestOntologySource:
    """Test OntologySource configuration class."""
    
    def test_ontology_source_initialization(self):
        """Test OntologySource initialization with default values."""
        source = OntologySource(
            name="test_ontology",
            url="http://example.com/test.owl"
        )
        
        assert source.name == "test_ontology"
        assert source.url == "http://example.com/test.owl"
        assert source.format == "owl"
        assert source.description == ""
        assert source.update_frequency_days == 7
        assert source.priority == 1
        assert source.last_updated is None
        assert source.file_hash is None
        assert source.file_size is None
    
    def test_ontology_source_custom_values(self):
        """Test OntologySource initialization with custom values."""
        source = OntologySource(
            name="custom_ontology",
            url="http://example.com/custom.obo",
            format="obo",
            description="Custom test ontology",
            update_frequency_days=14,
            priority=5
        )
        
        assert source.name == "custom_ontology"
        assert source.url == "http://example.com/custom.obo"
        assert source.format == "obo"
        assert source.description == "Custom test ontology"
        assert source.update_frequency_days == 14
        assert source.priority == 5


class TestOntologyDownloader:
    """Test OntologyDownloader functionality."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def downloader(self, temp_cache_dir):
        """Create OntologyDownloader instance for testing."""
        return OntologyDownloader(cache_dir=temp_cache_dir)
    
    def test_downloader_initialization(self, downloader, temp_cache_dir):
        """Test OntologyDownloader initialization."""
        assert downloader.cache_dir == Path(temp_cache_dir)
        assert downloader.cache_dir.exists()
        assert downloader.metadata_file == Path(temp_cache_dir) / "metadata.json"
        
        # Check that all 8 source ontologies are configured
        expected_sources = [
            'chebi', 'plant_ontology', 'gene_ontology_bp', 'ncbi_taxonomy',
            'environment_ontology', 'phenotype_trait_ontology', 'units_ontology',
            'chemical_methods_ontology'
        ]
        
        assert len(downloader.sources) == 8
        for source_name in expected_sources:
            assert source_name in downloader.sources
            source = downloader.sources[source_name]
            assert isinstance(source, OntologySource)
            assert source.name == source_name
            assert source.url.startswith('http')
            assert source.format in ['owl', 'obo']
    
    def test_source_priorities(self, downloader):
        """Test that source priorities are correctly assigned."""
        # ChEBI should have highest priority (1)
        assert downloader.sources['chebi'].priority == 1
        
        # Plant Ontology should have second priority (2)
        assert downloader.sources['plant_ontology'].priority == 2
        
        # All priorities should be unique and in range 1-8
        priorities = [source.priority for source in downloader.sources.values()]
        assert len(set(priorities)) == 8  # All unique
        assert min(priorities) == 1
        assert max(priorities) == 8
    
    def test_metadata_loading_empty(self, downloader):
        """Test metadata loading when no metadata file exists."""
        assert downloader.metadata == {}
    
    def test_metadata_loading_existing(self, temp_cache_dir):
        """Test metadata loading when metadata file exists."""
        metadata_file = Path(temp_cache_dir) / "metadata.json"
        test_metadata = {
            'chebi': {
                'last_updated': '2023-01-01T00:00:00',
                'file_hash': 'test_hash',
                'file_size': 1000
            }
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(test_metadata, f)
        
        downloader = OntologyDownloader(cache_dir=temp_cache_dir)
        assert downloader.metadata == test_metadata
    
    def test_metadata_loading_corrupted(self, temp_cache_dir):
        """Test metadata loading when metadata file is corrupted."""
        metadata_file = Path(temp_cache_dir) / "metadata.json"
        
        # Write invalid JSON
        with open(metadata_file, 'w') as f:
            f.write("invalid json content")
        
        downloader = OntologyDownloader(cache_dir=temp_cache_dir)
        assert downloader.metadata == {}  # Should fall back to empty dict
    
    def test_needs_update_no_cache(self, downloader):
        """Test needs_update when no cached file exists."""
        source = downloader.sources['chebi']
        assert downloader._needs_update(source) is True
    
    def test_needs_update_recent_cache(self, downloader, temp_cache_dir):
        """Test needs_update when cached file is recent."""
        # Create a cached file
        cache_file = Path(temp_cache_dir) / "chebi.owl"
        cache_file.write_text("test content")
        
        # Set recent metadata
        downloader.metadata['chebi'] = {
            'last_updated': datetime.now().isoformat()
        }
        
        source = downloader.sources['chebi']
        assert downloader._needs_update(source) is False
    
    def test_needs_update_old_cache(self, downloader, temp_cache_dir):
        """Test needs_update when cached file is old."""
        # Create a cached file
        cache_file = Path(temp_cache_dir) / "chebi.owl"
        cache_file.write_text("test content")
        
        # Set old metadata
        old_date = datetime.now() - timedelta(days=10)
        downloader.metadata['chebi'] = {
            'last_updated': old_date.isoformat()
        }
        
        source = downloader.sources['chebi']
        assert downloader._needs_update(source) is True
    
    def test_download_ontology_success(self, downloader):
        """Test successful ontology download."""
        mock_content = b"<?xml version='1.0'?><owl:Ontology>test content</owl:Ontology>"
        
        with patch('requests.get') as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [mock_content]
            mock_get.return_value = mock_response
            
            success, message = downloader.download_ontology('chebi', force_update=True)
            
            assert success is True
            assert "Successfully downloaded chebi" in message
            
            # Verify file was created
            cache_file = downloader.cache_dir / "chebi.owl"
            assert cache_file.exists()
            assert cache_file.read_bytes() == mock_content
            
            # Verify metadata was updated
            assert 'chebi' in downloader.metadata
            metadata = downloader.metadata['chebi']
            assert 'last_updated' in metadata
            assert 'file_hash' in metadata
            assert 'file_size' in metadata
            assert metadata['file_size'] == len(mock_content)
    
    def test_download_ontology_network_error(self, downloader):
        """Test ontology download with network error."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            
            success, message = downloader.download_ontology('chebi', force_update=True)
            
            assert success is False
            assert "Failed to download chebi" in message
            assert "Network error" in message
    
    def test_download_ontology_unknown_source(self, downloader):
        """Test download with unknown ontology source."""
        success, message = downloader.download_ontology('unknown_ontology')
        
        assert success is False
        assert "Unknown ontology source" in message
    
    def test_download_ontology_skip_recent(self, downloader, temp_cache_dir):
        """Test skipping download when cached version is recent."""
        # Create cached file and recent metadata
        cache_file = Path(temp_cache_dir) / "chebi.owl"
        cache_file.write_text("existing content")
        
        downloader.metadata['chebi'] = {
            'last_updated': datetime.now().isoformat()
        }
        
        success, message = downloader.download_ontology('chebi', force_update=False)
        
        assert success is True
        assert "is up to date" in message
    
    def test_download_all_ontologies(self, downloader):
        """Test downloading all ontologies."""
        mock_content = b"test ontology content"
        
        with patch('requests.get') as mock_get, \
             patch('time.sleep') as mock_sleep:  # Speed up test
            
            # Mock successful responses for all ontologies
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [mock_content]
            mock_get.return_value = mock_response
            
            results = downloader.download_all_ontologies(force_update=True)
            
            # Verify all 8 ontologies were processed
            assert len(results) == 8
            
            # Verify all downloads were successful
            for source_name, (success, message) in results.items():
                assert success is True
                assert f"Successfully downloaded {source_name}" in message
            
            # Verify delay was added between downloads
            assert mock_sleep.call_count == 8
    
    def test_get_ontology_path_existing(self, downloader, temp_cache_dir):
        """Test getting path for existing ontology."""
        # Create cached file
        cache_file = Path(temp_cache_dir) / "chebi.owl"
        cache_file.write_text("test content")
        
        path = downloader.get_ontology_path('chebi')
        assert path == cache_file
        assert path.exists()
    
    def test_get_ontology_path_missing(self, downloader):
        """Test getting path for missing ontology."""
        path = downloader.get_ontology_path('chebi')
        assert path is None
    
    def test_get_ontology_path_unknown_source(self, downloader):
        """Test getting path for unknown source."""
        path = downloader.get_ontology_path('unknown_source')
        assert path is None
    
    def test_get_download_status(self, downloader, temp_cache_dir):
        """Test getting download status for all ontologies."""
        # Create one cached file
        cache_file = Path(temp_cache_dir) / "chebi.owl"
        cache_file.write_text("test content")
        
        # Add metadata for cached file
        downloader.metadata['chebi'] = {
            'last_updated': datetime.now().isoformat(),
            'file_hash': 'test_hash',
            'file_size': 12
        }
        
        status = downloader.get_download_status()
        
        # Verify status for all 8 ontologies
        assert len(status) == 8
        
        # Check cached ontology status
        chebi_status = status['chebi']
        assert chebi_status['name'] == 'chebi'
        assert chebi_status['cached'] is True
        assert chebi_status['cache_path'] is not None
        assert chebi_status['last_updated'] is not None
        assert chebi_status['file_size'] == 12
        assert chebi_status['file_hash'] == 'test_hash'
        
        # Check non-cached ontology status
        po_status = status['plant_ontology']
        assert po_status['name'] == 'plant_ontology'
        assert po_status['cached'] is False
        assert po_status['cache_path'] is None
        assert po_status['last_updated'] is None
        assert po_status['needs_update'] is True
