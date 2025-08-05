"""
Shared test fixtures for the plant metabolite knowledge extraction system.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock

from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS, OWL


@pytest.fixture
def sample_terms():
    """Fixture providing sample anatomical terms."""
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


@pytest.fixture
def mock_corpus_data():
    """Fixture providing mock corpus data."""
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


@pytest.fixture
def mock_sparql_endpoint():
    """Fixture providing mock SPARQL endpoint."""
    mock_endpoint = Mock()
    mock_endpoint.query.return_value = Mock()
    mock_endpoint.query.return_value.bindings = [
        {"term": "http://example.org/plant-metabolite-ontology#Leaf"},
        {"term": "http://example.org/plant-metabolite-ontology#Root"},
    ]
    return mock_endpoint


@pytest.fixture
def temp_ontology_file():
    """Fixture providing a temporary ontology file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.owl', delete=False) as f:
        f.write("""<?xml version="1.0"?>
<rdf:RDF xmlns="http://example.org/plant-metabolite-ontology#"
         xml:base="http://example.org/plant-metabolite-ontology"
         xmlns:owl="http://www.w3.org/2002/07/owl#"
         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
    <owl:Ontology rdf:about="http://example.org/plant-metabolite-ontology"/>
    
    <owl:Class rdf:about="http://example.org/plant-metabolite-ontology#PlantPart">
        <rdfs:label>Plant Part</rdfs:label>
    </owl:Class>
    
    <owl:Class rdf:about="http://example.org/plant-metabolite-ontology#Leaf">
        <rdfs:subClassOf rdf:resource="http://example.org/plant-metabolite-ontology#PlantPart"/>
        <rdfs:label>Leaf</rdfs:label>
    </owl:Class>
</rdf:RDF>""")
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    os.unlink(temp_file)


@pytest.fixture
def test_graph():
    """Fixture providing a test RDF graph."""
    PMO = Namespace("http://example.org/plant-metabolite-ontology#")
    graph = Graph()
    graph.bind("pmo", PMO)
    graph.bind("owl", OWL)
    graph.bind("rdfs", RDFS)
    
    # Load sample ontology data
    sample_ontology_path = Path(__file__).parent / "fixtures" / "ontology_samples.owl"
    if sample_ontology_path.exists():
        graph.parse(str(sample_ontology_path), format="xml")
    
    return graph
