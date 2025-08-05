"""
Base test class for ontology operations.

This module provides common functionality and fixtures for ontology-related tests.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch

import owlready2
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL


class OntologyTestBase:
    """Base class for ontology-related tests."""
    
    @pytest.fixture(autouse=True)
    def setup_ontology_test(self):
        """Set up common test fixtures for ontology tests."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_ontology_path = Path(self.temp_dir) / "test_ontology.owl"
        
        # Define common namespaces
        self.PMO = Namespace("http://example.org/plant-metabolite-ontology#")
        self.test_graph = Graph()
        self.test_graph.bind("pmo", self.PMO)
        self.test_graph.bind("owl", OWL)
        self.test_graph.bind("rdfs", RDFS)
        
        # Load sample ontology data
        self.sample_ontology_path = Path(__file__).parent.parent / "fixtures" / "ontology_samples.owl"
        if self.sample_ontology_path.exists():
            self.test_graph.parse(str(self.sample_ontology_path), format="xml")
        
        yield
        
        # Cleanup
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_sample_terms(self) -> List[Dict[str, Any]]:
        """Create sample anatomical terms for testing."""
        return [
            {
                "uri": "http://example.org/plant-metabolite-ontology#Leaf",
                "label": "Leaf",
                "definition": "A flattened structure of a higher plant, typically green and blade-like",
                "parent": "http://example.org/plant-metabolite-ontology#PlantPart",
                "frequency": 150,
                "citation_count": 45
            },
            {
                "uri": "http://example.org/plant-metabolite-ontology#Root",
                "label": "Root",
                "definition": "The part of a plant which typically lies below the surface of the soil",
                "parent": "http://example.org/plant-metabolite-ontology#PlantPart",
                "frequency": 120,
                "citation_count": 38
            },
            {
                "uri": "http://example.org/plant-metabolite-ontology#Stem",
                "label": "Stem",
                "definition": "The main trunk of a plant",
                "parent": "http://example.org/plant-metabolite-ontology#PlantPart",
                "frequency": 95,
                "citation_count": 28
            },
            {
                "uri": "http://example.org/plant-metabolite-ontology#Flower",
                "label": "Flower",
                "definition": "The reproductive structure found in flowering plants",
                "parent": "http://example.org/plant-metabolite-ontology#PlantPart",
                "frequency": 85,
                "citation_count": 32
            },
            {
                "uri": "http://example.org/plant-metabolite-ontology#Seed",
                "label": "Seed",
                "definition": "A plant embryo and food reserve enclosed in a protective outer covering",
                "parent": "http://example.org/plant-metabolite-ontology#PlantPart",
                "frequency": 75,
                "citation_count": 25
            }
        ]
    
    def create_mock_corpus_data(self) -> List[Dict[str, Any]]:
        """Create mock corpus data for testing."""
        return [
            {
                "document_id": "doc_001",
                "title": "Metabolite accumulation in plant leaves",
                "abstract": "This study examines the accumulation of secondary metabolites in leaf tissues...",
                "terms": ["leaf", "metabolite", "accumulation", "secondary metabolite"],
                "citations": 15
            },
            {
                "document_id": "doc_002", 
                "title": "Root metabolite profiles in stress conditions",
                "abstract": "Analysis of root metabolite profiles under various stress conditions...",
                "terms": ["root", "metabolite", "stress", "profile"],
                "citations": 22
            },
            {
                "document_id": "doc_003",
                "title": "Stem anatomy and metabolite transport",
                "abstract": "Investigation of stem anatomical features and their role in metabolite transport...",
                "terms": ["stem", "anatomy", "metabolite", "transport"],
                "citations": 18
            }
        ]
    
    def assert_ontology_consistency(self, ontology_path: str):
        """Assert that an ontology is consistent."""
        try:
            world = owlready2.World()
            onto = world.get_ontology(f"file://{ontology_path}").load()
            
            # Run consistency check
            with onto:
                owlready2.sync_reasoner_pellet(world, infer_property_values=True)
            
            # If we get here without exception, ontology is consistent
            assert True
        except Exception as e:
            pytest.fail(f"Ontology consistency check failed: {e}")
    
    def count_ontology_classes(self, ontology_path: str) -> int:
        """Count the number of classes in an ontology."""
        graph = Graph()
        graph.parse(ontology_path, format="xml")
        
        # Count OWL classes
        class_count = len(list(graph.subjects(RDF.type, OWL.Class)))
        return class_count
    
    def get_ontology_properties(self, ontology_path: str) -> List[str]:
        """Get list of properties in an ontology."""
        graph = Graph()
        graph.parse(ontology_path, format="xml")
        
        # Get object properties
        properties = []
        for prop in graph.subjects(RDF.type, OWL.ObjectProperty):
            properties.append(str(prop))
        
        return properties
    
    def mock_sparql_endpoint(self) -> Mock:
        """Create a mock SPARQL endpoint for testing."""
        mock_endpoint = Mock()
        mock_endpoint.query.return_value = Mock()
        mock_endpoint.query.return_value.bindings = [
            {"term": URIRef("http://example.org/plant-metabolite-ontology#Leaf")},
            {"term": URIRef("http://example.org/plant-metabolite-ontology#Root")},
        ]
        return mock_endpoint
    
    def create_test_validation_data(self) -> Dict[str, Any]:
        """Create test data for validation scenarios."""
        return {
            "valid_terms": [
                {"uri": "http://example.org/plant-metabolite-ontology#Leaf", "score": 0.95},
                {"uri": "http://example.org/plant-metabolite-ontology#Root", "score": 0.88},
            ],
            "invalid_terms": [
                {"uri": "http://example.org/plant-metabolite-ontology#InvalidTerm", "score": 0.45},
            ],
            "threshold": 0.8
        }


@pytest.fixture
def ontology_test_base():
    """Fixture to provide OntologyTestBase instance."""
    return OntologyTestBase()


@pytest.fixture
def sample_terms():
    """Fixture providing sample anatomical terms."""
    base = OntologyTestBase()
    return base.create_sample_terms()


@pytest.fixture
def mock_corpus_data():
    """Fixture providing mock corpus data."""
    base = OntologyTestBase()
    return base.create_mock_corpus_data()


@pytest.fixture
def mock_sparql_endpoint():
    """Fixture providing mock SPARQL endpoint."""
    base = OntologyTestBase()
    return base.mock_sparql_endpoint()
