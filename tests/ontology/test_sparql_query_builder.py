"""
Tests for the SPARQLQueryBuilder class.

This module contains tests for SPARQL query building and endpoint integration
functionality for ontology queries.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from tests.ontology.test_base import OntologyTestBase


class TestSPARQLQueryBuilder(OntologyTestBase):
    """Test cases for SPARQLQueryBuilder class."""
    
    def test_build_term_search_query_basic(self):
        """Test basic term search query building."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        query = builder.build_term_search_query("leaf", "Plant Ontology")
        
        assert isinstance(query, str)
        assert "leaf" in query.lower()
        assert "select" in query.lower()
        assert "where" in query.lower()
        assert "filter" in query.lower()
    
    def test_build_term_search_query_with_options(self):
        """Test term search query building with various options."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        # Test with exact match
        query = builder.build_term_search_query("leaf", "Plant Ontology", exact_match=True)
        assert "=" in query or "str(?label)" in query
        
        # Test with limit
        query = builder.build_term_search_query("leaf", "Plant Ontology", limit=5)
        assert "limit 5" in query.lower()
        
        # Test with case sensitivity
        query = builder.build_term_search_query("Leaf", "Plant Ontology", case_sensitive=True)
        assert "Leaf" in query
    
    def test_build_hierarchy_query_basic(self):
        """Test basic hierarchy query building."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        query = builder.build_hierarchy_query("http://example.org/leaf", "Plant Ontology")
        
        assert isinstance(query, str)
        assert "select" in query.lower()
        assert "subclassof" in query.lower() or "rdfs:subclassof" in query.lower()
        assert "http://example.org/leaf" in query
    
    def test_build_hierarchy_query_with_depth(self):
        """Test hierarchy query building with depth limit."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        query = builder.build_hierarchy_query(
            "http://example.org/leaf", 
            "Plant Ontology", 
            max_depth=3
        )
        
        assert isinstance(query, str)
        # Should contain some form of depth limiting
        assert "3" in query or "limit" in query.lower()
    
    def test_build_property_query_basic(self):
        """Test basic property query building."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        query = builder.build_property_query("http://example.org/leaf", "Plant Ontology")
        
        assert isinstance(query, str)
        assert "select" in query.lower()
        assert "http://example.org/leaf" in query
        assert "?property" in query or "?p" in query
    
    def test_build_property_query_specific_property(self):
        """Test property query building for specific property."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        query = builder.build_property_query(
            "http://example.org/leaf", 
            "Plant Ontology",
            property_type="rdfs:label"
        )
        
        assert isinstance(query, str)
        assert "rdfs:label" in query
    
    def test_execute_query_basic(self):
        """Test basic query execution."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        # Mock SPARQL endpoint
        with patch('src.ontology.sparql_query_builder.SPARQLWrapper') as mock_sparql:
            mock_endpoint = Mock()
            mock_sparql.return_value = mock_endpoint
            
            mock_endpoint.query.return_value.convert.return_value = {
                "results": {
                    "bindings": [
                        {"term": {"value": "http://example.org/leaf"}}
                    ]
                }
            }
            
            query = "SELECT ?term WHERE { ?term rdfs:label 'leaf' }"
            result = builder.execute_query(query, "http://example.org/sparql")
            
            assert isinstance(result, dict)
            assert "results" in result
            assert "bindings" in result["results"]
    
    def test_execute_query_with_timeout(self):
        """Test query execution with timeout handling."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder(timeout=10)
        
        with patch('src.ontology.sparql_query_builder.SPARQLWrapper') as mock_sparql:
            mock_endpoint = Mock()
            mock_sparql.return_value = mock_endpoint
            mock_endpoint.query.side_effect = TimeoutError("Query timeout")
            
            query = "SELECT ?term WHERE { ?term rdfs:label 'leaf' }"
            result = builder.execute_query(query, "http://example.org/sparql")
            
            # Should handle timeout gracefully
            assert isinstance(result, dict)
            assert "error" in result
            assert "timeout" in result["error"].lower()
    
    def test_execute_query_with_retries(self):
        """Test query execution with retry mechanism."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder(max_retries=3)
        
        with patch('src.ontology.sparql_query_builder.SPARQLWrapper') as mock_sparql:
            mock_endpoint = Mock()
            mock_sparql.return_value = mock_endpoint
            
            # First two calls fail, third succeeds
            mock_endpoint.query.side_effect = [
                Exception("Network error"),
                Exception("Network error"),
                Mock(convert=Mock(return_value={"results": {"bindings": []}}))
            ]
            
            query = "SELECT ?term WHERE { ?term rdfs:label 'leaf' }"
            result = builder.execute_query(query, "http://example.org/sparql")
            
            # Should succeed after retries
            assert isinstance(result, dict)
            assert "results" in result
    
    def test_search_terms_in_ontology_basic(self):
        """Test basic term search in ontology."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "results": {
                    "bindings": [
                        {
                            "term": {"value": "http://example.org/leaf"},
                            "label": {"value": "leaf"}
                        }
                    ]
                }
            }
            
            results = builder.search_terms_in_ontology(["leaf"], "Plant Ontology")
            
            assert isinstance(results, dict)
            assert "leaf" in results
            assert results["leaf"]["found"] is True
            assert "uri" in results["leaf"]
    
    def test_search_terms_in_ontology_not_found(self):
        """Test term search when terms are not found."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "results": {
                    "bindings": []
                }
            }
            
            results = builder.search_terms_in_ontology(["nonexistent"], "Plant Ontology")
            
            assert isinstance(results, dict)
            assert "nonexistent" in results
            assert results["nonexistent"]["found"] is False
    
    def test_get_term_hierarchy_basic(self):
        """Test getting term hierarchy."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "results": {
                    "bindings": [
                        {
                            "parent": {"value": "http://example.org/plant_part"},
                            "child": {"value": "http://example.org/leaf"}
                        }
                    ]
                }
            }
            
            hierarchy = builder.get_term_hierarchy("http://example.org/leaf", "Plant Ontology")
            
            assert isinstance(hierarchy, dict)
            assert "parents" in hierarchy or "children" in hierarchy
    
    def test_get_term_properties_basic(self):
        """Test getting term properties."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "results": {
                    "bindings": [
                        {
                            "property": {"value": "rdfs:label"},
                            "value": {"value": "leaf"}
                        },
                        {
                            "property": {"value": "rdfs:comment"},
                            "value": {"value": "A plant organ"}
                        }
                    ]
                }
            }
            
            properties = builder.get_term_properties("http://example.org/leaf", "Plant Ontology")
            
            assert isinstance(properties, dict)
            assert len(properties) > 0
    
    def test_validate_sparql_query_basic(self):
        """Test SPARQL query validation."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        # Valid query
        valid_query = "SELECT ?s WHERE { ?s rdfs:label ?label }"
        assert builder.validate_sparql_query(valid_query) is True
        
        # Invalid query
        invalid_query = "INVALID SPARQL SYNTAX"
        assert builder.validate_sparql_query(invalid_query) is False
    
    def test_get_ontology_endpoint_basic(self):
        """Test getting ontology endpoint URL."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        # Test known ontology
        endpoint = builder.get_ontology_endpoint("Plant Ontology")
        assert isinstance(endpoint, str)
        assert "http" in endpoint
        
        # Test unknown ontology
        endpoint = builder.get_ontology_endpoint("Unknown Ontology")
        assert endpoint is None
    
    def test_format_query_results_basic(self):
        """Test formatting query results."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        raw_results = {
            "results": {
                "bindings": [
                    {
                        "term": {"value": "http://example.org/leaf"},
                        "label": {"value": "leaf"}
                    }
                ]
            }
        }
        
        formatted = builder.format_query_results(raw_results)
        
        assert isinstance(formatted, list)
        assert len(formatted) > 0
        assert "term" in formatted[0]
        assert "label" in formatted[0]
    
    def test_build_federated_query_basic(self):
        """Test building federated queries across multiple endpoints."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        endpoints = ["http://sparql1.example.org", "http://sparql2.example.org"]
        query = builder.build_federated_query("leaf", endpoints)
        
        assert isinstance(query, str)
        assert "service" in query.lower() or "union" in query.lower()
    
    def test_cache_query_results_basic(self):
        """Test query result caching."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder(enable_cache=True)

        # Verify cache is enabled
        assert builder.query_cache is not None
        assert builder.config["enable_cache"] is True

        query = "SELECT ?s WHERE { ?s rdfs:label 'leaf' }"
        endpoint = "http://example.org/sparql"

        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {"results": {"bindings": []}}

            # First call should execute query
            result1 = builder.cached_execute_query(query, endpoint)

            # Verify cache has entry
            assert len(builder.query_cache) == 1

            # Second call should use cache
            result2 = builder.cached_execute_query(query, endpoint)

            assert result1 == result2
            assert mock_execute.call_count == 1  # Should only be called once
    
    def test_export_query_results_basic(self, tmp_path):
        """Test exporting query results."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder
        
        builder = SPARQLQueryBuilder()
        
        results = {
            "results": {
                "bindings": [
                    {"term": {"value": "http://example.org/leaf"}}
                ]
            }
        }
        
        output_file = tmp_path / "query_results.json"
        builder.export_query_results(results, str(output_file))
        
        assert output_file.exists()
        
        # Verify file contents
        import json
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        assert "results" in loaded_data

    def test_build_term_relationship_queries_basic(self):
        """Test basic term relationship query building."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"  # leaf
        queries = builder.build_term_relationship_queries(term_uri, "Plant Ontology")

        assert isinstance(queries, dict)
        assert len(queries) > 0

        # Should have forward and inverse queries for default relationship types
        expected_rel_types = ['is_a', 'part_of', 'has_part', 'regulates', 'located_in']
        for rel_type in expected_rel_types:
            assert f"{rel_type}_forward" in queries
            assert f"{rel_type}_inverse" in queries

        # Check query structure
        for query_name, query in queries.items():
            assert isinstance(query, str)
            assert "select" in query.lower()
            assert "where" in query.lower()
            assert term_uri in query

    def test_build_term_relationship_queries_specific_types(self):
        """Test relationship query building with specific relationship types."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        relationship_types = ['is_a', 'part_of']

        queries = builder.build_term_relationship_queries(
            term_uri, "Plant Ontology", relationship_types
        )

        assert isinstance(queries, dict)

        # Should only have queries for specified relationship types
        expected_queries = ['is_a_forward', 'is_a_inverse', 'part_of_forward', 'part_of_inverse']
        assert len(queries) == len(expected_queries)

        for expected_query in expected_queries:
            assert expected_query in queries

        # Should not have other relationship types
        assert 'has_part_forward' not in queries
        assert 'regulates_forward' not in queries

    def test_build_term_relationship_queries_no_inverse(self):
        """Test relationship query building without inverse relationships."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        relationship_types = ['is_a', 'part_of']

        queries = builder.build_term_relationship_queries(
            term_uri, "Plant Ontology", relationship_types, include_inverse=False
        )

        assert isinstance(queries, dict)

        # Should only have forward queries
        expected_queries = ['is_a_forward', 'part_of_forward']
        assert len(queries) == len(expected_queries)

        for expected_query in expected_queries:
            assert expected_query in queries

        # Should not have inverse queries
        assert 'is_a_inverse' not in queries
        assert 'part_of_inverse' not in queries

    def test_build_term_relationship_queries_predicate_mapping(self):
        """Test that relationship types are correctly mapped to predicates."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        relationship_types = ['is_a', 'part_of', 'has_part']

        queries = builder.build_term_relationship_queries(
            term_uri, "Plant Ontology", relationship_types, include_inverse=False
        )

        # Check that correct predicates are used
        assert 'rdfs:subClassOf' in queries['is_a_forward']
        assert 'obo:BFO_0000050' in queries['part_of_forward']  # part of
        assert 'obo:BFO_0000051' in queries['has_part_forward']  # has part

    def test_build_term_relationship_queries_query_structure(self):
        """Test the structure of generated relationship queries."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"
        relationship_types = ['is_a']

        queries = builder.build_term_relationship_queries(
            term_uri, "Plant Ontology", relationship_types
        )

        forward_query = queries['is_a_forward']
        inverse_query = queries['is_a_inverse']

        # Check forward query structure
        assert 'SELECT DISTINCT ?target ?targetLabel ?relation' in forward_query
        assert f'<{term_uri}> rdfs:subClassOf ?target' in forward_query
        assert '?target rdfs:label ?targetLabel' in forward_query
        assert 'BIND("is_a" AS ?relation)' in forward_query
        assert 'ORDER BY ?targetLabel' in forward_query

        # Check inverse query structure
        assert 'SELECT DISTINCT ?source ?sourceLabel ?relation' in inverse_query
        assert f'?source rdfs:subClassOf <{term_uri}>' in inverse_query
        assert '?source rdfs:label ?sourceLabel' in inverse_query
        assert 'BIND("is_a_inverse" AS ?relation)' in inverse_query
        assert 'ORDER BY ?sourceLabel' in inverse_query

    def test_execute_relationship_queries_basic(self):
        """Test executing relationship queries."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"

        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "results": {
                    "bindings": [
                        {
                            "target": {"value": "http://example.org/plant_part"},
                            "targetLabel": {"value": "plant part"},
                            "relation": {"value": "is_a"}
                        }
                    ]
                }
            }

            results = builder.execute_relationship_queries(
                term_uri, "Plant Ontology", ['is_a'], include_inverse=False
            )

            assert isinstance(results, dict)
            assert 'is_a_forward' in results
            assert isinstance(results['is_a_forward'], list)
            assert len(results['is_a_forward']) > 0

            # Check result structure
            result_item = results['is_a_forward'][0]
            assert 'target' in result_item
            assert 'targetLabel' in result_item
            assert 'relation' in result_item

    def test_execute_relationship_queries_unknown_ontology(self):
        """Test executing relationship queries with unknown ontology."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://example.org/term"

        results = builder.execute_relationship_queries(
            term_uri, "Unknown Ontology", ['is_a']
        )

        assert isinstance(results, dict)
        assert "error" in results
        assert "Unknown ontology" in results["error"]

    def test_execute_relationship_queries_with_errors(self):
        """Test executing relationship queries when SPARQL queries fail."""
        from src.ontology.sparql_query_builder import SPARQLQueryBuilder

        builder = SPARQLQueryBuilder()

        term_uri = "http://purl.obolibrary.org/obo/PO_0025034"

        with patch.object(builder, 'execute_query') as mock_execute:
            mock_execute.return_value = {
                "error": "SPARQL endpoint error"
            }

            results = builder.execute_relationship_queries(
                term_uri, "Plant Ontology", ['is_a'], include_inverse=False
            )

            assert isinstance(results, dict)
            assert 'is_a_forward' in results
            assert 'error' in results['is_a_forward']
            assert "SPARQL endpoint error" in results['is_a_forward']['error']
