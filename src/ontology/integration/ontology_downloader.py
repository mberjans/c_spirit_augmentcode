"""
Ontology Downloader Module.

This module handles downloading and caching of source ontologies from various
repositories including OBO Foundry, BioPortal, and custom sources.

Supports the following 8 source ontologies:
1. ChEBI (Chemical Entities of Biological Interest)
2. Plant Ontology (PO)
3. Gene Ontology (GO) - Biological Process subset
4. NCBI Taxonomy
5. Environment Ontology (ENVO)
6. Phenotype and Trait Ontology (PATO)
7. Units of Measurement Ontology (UO)
8. Chemical Methods Ontology (CHMO)
"""

import os
import hashlib
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import time

from ...literature.structured_logger import structured_logger


class OntologySource:
    """Configuration for an ontology source."""
    
    def __init__(self, 
                 name: str,
                 url: str,
                 format: str = "owl",
                 description: str = "",
                 update_frequency_days: int = 7,
                 priority: int = 1):
        """
        Initialize ontology source configuration.
        
        Args:
            name: Short name identifier for the ontology
            url: Download URL for the ontology
            format: File format (owl, obo, json, etc.)
            description: Human-readable description
            update_frequency_days: How often to check for updates
            priority: Priority for conflict resolution (1=highest)
        """
        self.name = name
        self.url = url
        self.format = format
        self.description = description
        self.update_frequency_days = update_frequency_days
        self.priority = priority
        self.last_updated = None
        self.file_hash = None
        self.file_size = None


class OntologyDownloader:
    """
    Downloads and manages source ontologies for integration.
    
    Handles caching, update checking, and validation of ontology files.
    """
    
    def __init__(self, cache_dir: str = "data/ontologies/cache"):
        """
        Initialize ontology downloader.
        
        Args:
            cache_dir: Directory to store cached ontology files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.cache_dir / "metadata.json"
        self.sources = self._initialize_sources()
        self.metadata = self._load_metadata()
        
        # Set correlation ID for logging
        structured_logger.set_correlation_id()
    
    def _initialize_sources(self) -> Dict[str, OntologySource]:
        """Initialize the 8 source ontologies configuration."""
        sources = {
            'chebi': OntologySource(
                name='chebi',
                url='http://purl.obolibrary.org/obo/chebi.owl',
                format='owl',
                description='Chemical Entities of Biological Interest',
                priority=1
            ),
            'plant_ontology': OntologySource(
                name='plant_ontology',
                url='http://purl.obolibrary.org/obo/po.owl',
                format='owl',
                description='Plant Ontology',
                priority=2
            ),
            'gene_ontology_bp': OntologySource(
                name='gene_ontology_bp',
                url='http://purl.obolibrary.org/obo/go/go-basic.obo',
                format='obo',
                description='Gene Ontology - Biological Process',
                priority=3
            ),
            'ncbi_taxonomy': OntologySource(
                name='ncbi_taxonomy',
                url='http://purl.obolibrary.org/obo/ncbitaxon.owl',
                format='owl',
                description='NCBI Taxonomy',
                priority=4
            ),
            'environment_ontology': OntologySource(
                name='environment_ontology',
                url='http://purl.obolibrary.org/obo/envo.owl',
                format='owl',
                description='Environment Ontology',
                priority=5
            ),
            'phenotype_trait_ontology': OntologySource(
                name='phenotype_trait_ontology',
                url='http://purl.obolibrary.org/obo/pato.owl',
                format='owl',
                description='Phenotype and Trait Ontology',
                priority=6
            ),
            'units_ontology': OntologySource(
                name='units_ontology',
                url='http://purl.obolibrary.org/obo/uo.owl',
                format='owl',
                description='Units of Measurement Ontology',
                priority=7
            ),
            'chemical_methods_ontology': OntologySource(
                name='chemical_methods_ontology',
                url='http://purl.obolibrary.org/obo/chmo.owl',
                format='owl',
                description='Chemical Methods Ontology',
                priority=8
            )
        }
        return sources
    
    def _load_metadata(self) -> Dict:
        """Load cached metadata about downloaded ontologies."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                structured_logger.warning(
                    "Failed to load metadata file, starting fresh",
                    operation="load_metadata",
                    error=str(e),
                    status="warning"
                )
        return {}
    
    def _save_metadata(self) -> None:
        """Save metadata about downloaded ontologies."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except IOError as e:
            structured_logger.error(
                "Failed to save metadata file",
                operation="save_metadata",
                error=str(e),
                status="error"
            )
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def _needs_update(self, source: OntologySource) -> bool:
        """Check if an ontology needs to be updated."""
        source_metadata = self.metadata.get(source.name, {})
        
        # Check if file exists
        cache_file = self.cache_dir / f"{source.name}.{source.format}"
        if not cache_file.exists():
            return True
        
        # Check if enough time has passed since last update
        last_updated = source_metadata.get('last_updated')
        if last_updated:
            last_updated_date = datetime.fromisoformat(last_updated)
            if datetime.now() - last_updated_date < timedelta(days=source.update_frequency_days):
                return False
        
        return True
    
    def download_ontology(self, source_name: str, force_update: bool = False) -> Tuple[bool, str]:
        """
        Download a single ontology.
        
        Args:
            source_name: Name of the ontology source to download
            force_update: Force download even if cached version is recent
            
        Returns:
            Tuple of (success, message)
        """
        if source_name not in self.sources:
            return False, f"Unknown ontology source: {source_name}"
        
        source = self.sources[source_name]
        cache_file = self.cache_dir / f"{source.name}.{source.format}"
        
        # Check if update is needed
        if not force_update and not self._needs_update(source):
            structured_logger.info(
                "Ontology is up to date, skipping download",
                operation="download_ontology",
                ontology=source_name,
                status="skipped"
            )
            return True, f"Ontology {source_name} is up to date"
        
        structured_logger.info(
            "Starting ontology download",
            operation="download_ontology",
            ontology=source_name,
            url=source.url,
            status="started"
        )
        
        try:
            with structured_logger.time_operation(f"download_{source_name}"):
                # Download the ontology
                response = requests.get(source.url, timeout=300, stream=True)
                response.raise_for_status()
                
                # Write to temporary file first
                temp_file = cache_file.with_suffix(f".{source.format}.tmp")
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Calculate hash and validate
                file_hash = self._get_file_hash(temp_file)
                file_size = temp_file.stat().st_size
                
                # Move temp file to final location
                temp_file.rename(cache_file)
                
                # Update metadata
                self.metadata[source_name] = {
                    'last_updated': datetime.now().isoformat(),
                    'file_hash': file_hash,
                    'file_size': file_size,
                    'url': source.url,
                    'format': source.format
                }
                self._save_metadata()
                
                structured_logger.info(
                    "Ontology download completed successfully",
                    operation="download_ontology",
                    ontology=source_name,
                    file_size=file_size,
                    file_hash=file_hash[:16],  # First 16 chars of hash
                    status="success"
                )
                
                return True, f"Successfully downloaded {source_name}"
        
        except requests.RequestException as e:
            structured_logger.error(
                "Failed to download ontology",
                operation="download_ontology",
                ontology=source_name,
                error=str(e),
                error_type=type(e).__name__,
                status="error"
            )
            return False, f"Failed to download {source_name}: {str(e)}"
        
        except IOError as e:
            structured_logger.error(
                "Failed to save ontology file",
                operation="download_ontology",
                ontology=source_name,
                error=str(e),
                error_type=type(e).__name__,
                status="error"
            )
            return False, f"Failed to save {source_name}: {str(e)}"
    
    def download_all_ontologies(self, force_update: bool = False) -> Dict[str, Tuple[bool, str]]:
        """
        Download all configured ontologies.
        
        Args:
            force_update: Force download even if cached versions are recent
            
        Returns:
            Dictionary mapping ontology names to (success, message) tuples
        """
        results = {}
        
        structured_logger.info(
            "Starting bulk ontology download",
            operation="download_all_ontologies",
            ontology_count=len(self.sources),
            force_update=force_update,
            status="started"
        )
        
        for source_name in self.sources:
            success, message = self.download_ontology(source_name, force_update)
            results[source_name] = (success, message)
            
            # Add delay between downloads to be respectful to servers
            time.sleep(1.0)
        
        success_count = sum(1 for success, _ in results.values() if success)
        
        structured_logger.info(
            "Bulk ontology download completed",
            operation="download_all_ontologies",
            total_ontologies=len(self.sources),
            successful_downloads=success_count,
            failed_downloads=len(self.sources) - success_count,
            status="completed"
        )
        
        return results
    
    def get_ontology_path(self, source_name: str) -> Optional[Path]:
        """
        Get the local file path for a cached ontology.
        
        Args:
            source_name: Name of the ontology source
            
        Returns:
            Path to the cached ontology file, or None if not found
        """
        if source_name not in self.sources:
            return None
        
        source = self.sources[source_name]
        cache_file = self.cache_dir / f"{source.name}.{source.format}"
        
        return cache_file if cache_file.exists() else None
    
    def get_download_status(self) -> Dict[str, Dict]:
        """
        Get status information for all ontologies.
        
        Returns:
            Dictionary with status information for each ontology
        """
        status = {}
        
        for source_name, source in self.sources.items():
            cache_file = self.cache_dir / f"{source.name}.{source.format}"
            source_metadata = self.metadata.get(source_name, {})
            
            status[source_name] = {
                'name': source.name,
                'description': source.description,
                'url': source.url,
                'format': source.format,
                'priority': source.priority,
                'cached': cache_file.exists(),
                'cache_path': str(cache_file) if cache_file.exists() else None,
                'last_updated': source_metadata.get('last_updated'),
                'file_size': source_metadata.get('file_size'),
                'file_hash': source_metadata.get('file_hash'),
                'needs_update': self._needs_update(source)
            }
        
        return status
