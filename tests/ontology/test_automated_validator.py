"""
Tests for the AutomatedValidator class.

This module contains tests for automated validation functionality including
cross-reference validation and multi-metric scoring.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from tests.ontology.test_base import OntologyTestBase


class TestAutomatedValidator(OntologyTestBase):
    """Test cases for AutomatedValidator class."""
    
    def test_cross_reference_validation_basic(self, sample_terms):
        """Test basic cross-reference validation functionality."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        # Mock external ontology data
        with patch.object(validator, '_query_external_ontology') as mock_query:
            mock_query.return_value = {
                "leaf": {"found": True, "confidence": 0.95, "source": "Plant Ontology"},
                "root": {"found": True, "confidence": 0.88, "source": "Plant Ontology"},
                "stem": {"found": True, "confidence": 0.92, "source": "Plant Ontology"}
            }
            
            terms = [term["label"].lower() for term in sample_terms[:3]]
            result = validator.cross_reference_validation(terms)
            
            assert isinstance(result, dict)
            assert "leaf" in result
            assert "root" in result
            assert "stem" in result
            
            # Check validation structure
            for term, validation in result.items():
                assert "found" in validation
                assert "confidence" in validation
                assert "source" in validation
                assert isinstance(validation["found"], bool)
                assert isinstance(validation["confidence"], (int, float))
    
    def test_cross_reference_validation_empty_input(self):
        """Test cross-reference validation with empty input."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        result = validator.cross_reference_validation([])
        
        assert isinstance(result, dict)
        assert len(result) == 0
    
    def test_cross_reference_validation_not_found(self):
        """Test cross-reference validation when terms are not found."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        with patch.object(validator, '_query_external_ontology') as mock_query:
            mock_query.return_value = {
                "nonexistent_term": {"found": False, "confidence": 0.0, "source": "Plant Ontology"}
            }
            
            result = validator.cross_reference_validation(["nonexistent_term"])
            
            assert "nonexistent_term" in result
            assert result["nonexistent_term"]["found"] is False
            assert result["nonexistent_term"]["confidence"] == 0.0
    
    def test_cross_reference_validation_multiple_sources(self):
        """Test cross-reference validation against multiple ontology sources."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator(ontology_sources=["Plant Ontology", "Gene Ontology"])
        
        with patch.object(validator, '_query_external_ontology') as mock_query:
            mock_query.side_effect = [
                {"leaf": {"found": True, "confidence": 0.95, "source": "Plant Ontology"}},
                {"leaf": {"found": True, "confidence": 0.88, "source": "Gene Ontology"}}
            ]
            
            result = validator.cross_reference_validation(["leaf"])
            
            assert "leaf" in result
            # Should aggregate results from multiple sources
            assert result["leaf"]["found"] is True
            assert result["leaf"]["confidence"] > 0.8
    
    def test_calculate_multi_metric_score_basic(self, sample_terms):
        """Test basic multi-metric scoring functionality."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        # Create mock data for scoring
        term_data = {
            "leaf": {
                "frequency": 150,
                "citation_impact": 45,
                "validation_confidence": 0.95,
                "cluster_coherence": 0.85
            },
            "root": {
                "frequency": 120,
                "citation_impact": 38,
                "validation_confidence": 0.88,
                "cluster_coherence": 0.78
            }
        }
        
        result = validator.calculate_multi_metric_score(term_data)
        
        assert isinstance(result, dict)
        assert "leaf" in result
        assert "root" in result
        
        # Check score structure
        for term, score_data in result.items():
            assert "combined_score" in score_data
            assert "component_scores" in score_data
            assert isinstance(score_data["combined_score"], (int, float))
            assert 0.0 <= score_data["combined_score"] <= 1.0
    
    def test_calculate_multi_metric_score_empty_input(self):
        """Test multi-metric scoring with empty input."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        result = validator.calculate_multi_metric_score({})
        
        assert isinstance(result, dict)
        assert len(result) == 0
    
    def test_calculate_multi_metric_score_custom_weights(self):
        """Test multi-metric scoring with custom weights."""
        from src.ontology.automated_validator import AutomatedValidator
        
        custom_weights = {
            "frequency": 0.4,
            "citation_impact": 0.3,
            "validation_confidence": 0.2,
            "cluster_coherence": 0.1
        }
        
        validator = AutomatedValidator(scoring_weights=custom_weights)
        
        term_data = {
            "leaf": {
                "frequency": 150,
                "citation_impact": 45,
                "validation_confidence": 0.95,
                "cluster_coherence": 0.85
            }
        }
        
        result = validator.calculate_multi_metric_score(term_data)
        
        assert "leaf" in result
        assert "combined_score" in result["leaf"]
        assert isinstance(result["leaf"]["combined_score"], (int, float))
    
    def test_validate_term_selection_basic(self, sample_terms):
        """Test basic term selection validation."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        # Mock the validation and scoring methods
        with patch.object(validator, 'cross_reference_validation') as mock_validation, \
             patch.object(validator, 'calculate_multi_metric_score') as mock_scoring:
            
            mock_validation.return_value = {
                "leaf": {"found": True, "confidence": 0.95, "source": "Plant Ontology"},
                "root": {"found": True, "confidence": 0.88, "source": "Plant Ontology"}
            }
            
            mock_scoring.return_value = {
                "leaf": {"combined_score": 0.92, "component_scores": {}},
                "root": {"combined_score": 0.85, "component_scores": {}}
            }
            
            terms = [term["label"].lower() for term in sample_terms[:2]]
            result = validator.validate_term_selection(terms)
            
            assert isinstance(result, dict)
            assert "validation_results" in result
            assert "scoring_results" in result
            assert "recommended_terms" in result
            assert "rejected_terms" in result
    
    def test_validate_term_selection_with_threshold(self):
        """Test term selection validation with custom threshold."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator(selection_threshold=0.9)
        
        with patch.object(validator, 'cross_reference_validation') as mock_validation, \
             patch.object(validator, 'calculate_multi_metric_score') as mock_scoring:
            
            mock_validation.return_value = {
                "high_score": {"found": True, "confidence": 0.95, "source": "Plant Ontology"},
                "low_score": {"found": True, "confidence": 0.75, "source": "Plant Ontology"}
            }
            
            mock_scoring.return_value = {
                "high_score": {"combined_score": 0.95, "component_scores": {}},
                "low_score": {"combined_score": 0.75, "component_scores": {}}
            }
            
            result = validator.validate_term_selection(["high_score", "low_score"])
            
            # Only high_score should be recommended with threshold 0.9
            assert "high_score" in result["recommended_terms"]
            assert "low_score" in result["rejected_terms"]
    
    def test_generate_validation_report(self, tmp_path):
        """Test validation report generation."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        # Mock validation results
        validation_results = {
            "validation_results": {
                "leaf": {"found": True, "confidence": 0.95, "source": "Plant Ontology"}
            },
            "scoring_results": {
                "leaf": {"combined_score": 0.92, "component_scores": {}}
            },
            "recommended_terms": ["leaf"],
            "rejected_terms": []
        }
        
        output_file = tmp_path / "validation_report.json"
        validator.generate_validation_report(validation_results, str(output_file))
        
        assert output_file.exists()
        
        # Verify file contents
        import json
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        assert "validation_results" in loaded_data
        assert "scoring_results" in loaded_data
        assert "recommended_terms" in loaded_data
    
    def test_query_external_ontology_plant_ontology(self):
        """Test querying Plant Ontology."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        # Mock SPARQL query
        with patch('src.ontology.automated_validator.SPARQLWrapper') as mock_sparql:
            mock_endpoint = Mock()
            mock_sparql.return_value = mock_endpoint
            
            mock_endpoint.query.return_value.convert.return_value = {
                "results": {
                    "bindings": [
                        {"term": {"value": "http://purl.obolibrary.org/obo/PO_0025034"}}
                    ]
                }
            }
            
            result = validator._query_external_ontology("leaf", "Plant Ontology")
            
            assert isinstance(result, dict)
            assert "leaf" in result
            assert result["leaf"]["found"] is True
    
    def test_query_external_ontology_timeout_handling(self):
        """Test handling of timeout errors in external ontology queries."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        with patch('src.ontology.automated_validator.SPARQLWrapper') as mock_sparql:
            mock_endpoint = Mock()
            mock_sparql.return_value = mock_endpoint
            mock_endpoint.query.side_effect = TimeoutError("Query timeout")
            
            result = validator._query_external_ontology("leaf", "Plant Ontology")
            
            # Should handle timeout gracefully
            assert isinstance(result, dict)
            assert "leaf" in result
            assert result["leaf"]["found"] is False
            assert result["leaf"]["confidence"] == 0.0
    
    def test_normalize_scores_basic(self):
        """Test score normalization functionality."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        raw_scores = {
            "frequency": [100, 200, 150],
            "citation_impact": [10, 30, 20],
            "validation_confidence": [0.8, 0.9, 0.85]
        }
        
        normalized = validator._normalize_scores(raw_scores)
        
        assert isinstance(normalized, dict)
        for metric, scores in normalized.items():
            assert all(0.0 <= score <= 1.0 for score in scores)
    
    def test_aggregate_validation_results(self):
        """Test aggregation of validation results from multiple sources."""
        from src.ontology.automated_validator import AutomatedValidator
        
        validator = AutomatedValidator()
        
        results_list = [
            {"found": True, "confidence": 0.95, "source": "Plant Ontology"},
            {"found": True, "confidence": 0.88, "source": "Gene Ontology"},
            {"found": False, "confidence": 0.0, "source": "Chemical Ontology"}
        ]

        aggregated = validator._aggregate_validation_results(results_list)

        assert aggregated["found"] is True  # Should be True if found in any source
        assert 0.5 < aggregated["confidence"] < 1.0  # Should be weighted average
