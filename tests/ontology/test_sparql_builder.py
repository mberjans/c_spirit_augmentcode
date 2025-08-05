"""
Tests for the SPARQLBuilder class.

This module contains tests for specialized SPARQL query building
functionality for ontology trimming operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from tests.ontology.test_base import OntologyTestBase


class TestSPARQLBuilder(OntologyTestBase):
    """Test cases for SPARQLBuilder class."""
    
    def test_sparql_builder_initialization(self):
        """Test SPARQLBuilder initialization."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        assert builder.config is not None
        assert builder.config['default_limit'] == 1000
        assert builder.config['include_deprecated'] is False
        assert builder.config['include_obsolete'] is False
        assert builder.config['min_confidence'] == 0.7
        
        # Test with custom config
        custom_config = {'default_limit': 500, 'min_confidence': 0.8}
        builder_custom = SPARQLBuilder(custom_config)
        
        assert builder_custom.config['default_limit'] == 500
        assert builder_custom.config['min_confidence'] == 0.8
        assert builder_custom.config['include_deprecated'] is False  # default preserved
    
    def test_build_term_frequency_query_basic(self):
        """Test basic term frequency query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        terms = ['leaf', 'stem']
        query = builder.build_term_frequency_query(terms)
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert 'WHERE' in query
        assert 'leaf' in query
        assert 'stem' in query
        assert 'usage_count' in query
        assert 'ORDER BY DESC(?usage_count)' in query
        assert 'LIMIT 1000' in query
    
    def test_build_term_frequency_query_with_prefix(self):
        """Test term frequency query with specific ontology prefix."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        terms = ['metabolite']
        query = builder.build_term_frequency_query(terms, ontology_prefix='chebi')
        
        assert isinstance(query, str)
        assert 'metabolite' in query
        assert 'PREFIX chebi:' in query
    
    def test_build_cross_reference_query_basic(self):
        """Test basic cross-reference validation query."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        target_ontologies = ['go', 'chebi']
        
        query = builder.build_cross_reference_query(term_uri, target_ontologies)
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert term_uri in query
        assert 'equivalent_term' in query
        assert 'source_ontology' in query
        assert 'UNION' in query
    
    def test_build_hierarchical_analysis_query_basic(self):
        """Test hierarchical analysis query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        query = builder.build_hierarchical_analysis_query(term_uri, max_depth=2)
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert term_uri in query
        assert 'rdfs:subClassOf+' in query
        assert 'relation_type' in query
        assert 'depth' in query
        assert 'parent' in query
        assert 'child' in query
        assert 'FILTER(?depth <= 2)' in query
    
    def test_build_citation_impact_query_basic(self):
        """Test citation impact query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        terms = ['leaf', 'photosynthesis']
        query = builder.build_citation_impact_query(terms)
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert 'citation_count' in query
        assert 'impact_score' in query
        assert 'leaf' in query
        assert 'photosynthesis' in query
        assert 'ORDER BY DESC(?impact_score)' in query
    
    def test_build_citation_impact_query_no_synonyms(self):
        """Test citation impact query without synonyms."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        terms = ['leaf']
        query = builder.build_citation_impact_query(terms, include_synonyms=False)
        
        assert isinstance(query, str)
        assert 'leaf' in query
        # Should not include synonym-related patterns when include_synonyms=False
        synonym_count = query.count('synonym')
        assert synonym_count == 0  # No synonym references when include_synonyms=False
        assert '?synonym' not in query  # Synonym variable should not be in SELECT
    
    def test_build_term_validation_queries_basic(self):
        """Test building comprehensive validation queries."""
        from src.ontology.sparql_builder import SPARQLBuilder, TermValidationQuery
        
        builder = SPARQLBuilder()
        
        terms = ['leaf', 'stem']
        ontologies = ['po', 'go']
        
        queries = builder.build_term_validation_queries(terms, ontologies)
        
        assert isinstance(queries, list)
        assert len(queries) > 0
        
        # Should have frequency analysis + cross-reference queries
        expected_count = len(terms) * (1 + len(ontologies))  # 1 freq + N cross-ref per term
        assert len(queries) == expected_count
        
        # Check query types
        query_types = [q.query_type for q in queries]
        assert 'frequency_analysis' in query_types
        assert 'cross_reference' in query_types
        
        # Check that all queries are TermValidationQuery objects
        for query in queries:
            assert isinstance(query, TermValidationQuery)
            assert hasattr(query, 'term')
            assert hasattr(query, 'query')
            assert hasattr(query, 'ontology')
            assert hasattr(query, 'query_type')
    
    def test_build_term_similarity_query_basic(self):
        """Test term similarity query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        source_term = 'leaf'
        query = builder.build_term_similarity_query(source_term)
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert 'similarity_score' in query
        assert 'match_type' in query
        assert source_term in query
        assert 'exact' in query
        assert 'substring' in query
        assert 'word_overlap' in query
    
    def test_build_term_similarity_query_with_threshold(self):
        """Test term similarity query with custom threshold."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        source_term = 'leaf'
        threshold = 0.9
        query = builder.build_term_similarity_query(source_term, similarity_threshold=threshold)
        
        assert isinstance(query, str)
        assert f'FILTER(?similarity_score >= {threshold})' in query
    
    def test_build_usage_statistics_query_basic(self):
        """Test usage statistics query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        query = builder.build_term_usage_statistics_query()
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert 'parent_count' in query
        assert 'child_count' in query
        assert 'total_relations' in query
        assert 'usage_score' in query
        assert 'ORDER BY DESC(?usage_score)' in query
    
    def test_build_deprecated_terms_query_basic(self):
        """Test deprecated terms query building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        query = builder.build_deprecated_terms_query()
        
        assert isinstance(query, str)
        assert 'SELECT' in query
        assert 'deprecated' in query
        assert 'obsolete' in query
        assert 'replacement' in query
        assert 'owl:deprecated' in query
        assert 'obo:IAO_0000231' in query
    
    def test_validate_query_syntax_valid_query(self):
        """Test query syntax validation with valid query."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        valid_query = """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        SELECT ?s ?label WHERE {
            ?s rdfs:label ?label .
        }
        LIMIT 100
        """
        
        result = builder.validate_query_syntax(valid_query)
        
        assert isinstance(result, dict)
        assert result['valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_query_syntax_invalid_query(self):
        """Test query syntax validation with invalid query."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        # Missing WHERE clause
        invalid_query = "SELECT ?s ?label"
        
        result = builder.validate_query_syntax(invalid_query)
        
        assert isinstance(result, dict)
        assert result['valid'] is False
        assert len(result['errors']) > 0
        assert any('WHERE' in error for error in result['errors'])
    
    def test_validate_query_syntax_unbalanced_braces(self):
        """Test query syntax validation with unbalanced braces."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        # Unbalanced braces
        invalid_query = "SELECT ?s WHERE { ?s rdfs:label ?label ."
        
        result = builder.validate_query_syntax(invalid_query)
        
        assert isinstance(result, dict)
        assert result['valid'] is False
        assert any('braces' in error.lower() for error in result['errors'])
    
    def test_validate_query_syntax_warnings(self):
        """Test query syntax validation warnings."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        # Query without LIMIT
        query_no_limit = "SELECT ?s WHERE { ?s rdfs:label ?label }"
        
        result = builder.validate_query_syntax(query_no_limit)
        
        assert isinstance(result, dict)
        assert result['valid'] is True
        assert len(result['warnings']) > 0
        assert any('LIMIT' in warning for warning in result['warnings'])
    
    def test_prefixes_building(self):
        """Test PREFIX declarations building."""
        from src.ontology.sparql_builder import SPARQLBuilder
        
        builder = SPARQLBuilder()
        
        prefixes = builder._build_prefixes()
        
        assert isinstance(prefixes, str)
        assert 'PREFIX rdfs:' in prefixes
        assert 'PREFIX rdf:' in prefixes
        assert 'PREFIX owl:' in prefixes
        assert 'PREFIX obo:' in prefixes
        assert 'PREFIX po:' in prefixes
        assert 'PREFIX go:' in prefixes
        assert 'PREFIX chebi:' in prefixes
