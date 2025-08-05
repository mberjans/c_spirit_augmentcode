"""
Tests for the CorpusAnalyzer class.

This module contains tests for corpus analysis functionality including
term frequency analysis and citation impact scoring.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from typing import Dict, List, Any

from tests.ontology.test_base import OntologyTestBase


class TestCorpusAnalyzer(OntologyTestBase):
    """Test cases for CorpusAnalyzer class."""
    
    def test_analyze_term_frequency_basic(self, mock_corpus_data):
        """Test basic term frequency analysis functionality."""
        # Import here to avoid circular imports during test discovery
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        # Test with mock corpus data
        result = analyzer.analyze_term_frequency(mock_corpus_data)
        
        # Assertions
        assert isinstance(result, dict)
        assert "leaf" in result
        assert "root" in result
        assert "stem" in result
        assert result["leaf"] >= 1  # Should appear at least once
        assert result["root"] >= 1
        assert result["stem"] >= 1
    
    def test_analyze_term_frequency_empty_corpus(self):
        """Test term frequency analysis with empty corpus."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        result = analyzer.analyze_term_frequency([])
        
        assert isinstance(result, dict)
        assert len(result) == 0
    
    def test_analyze_term_frequency_case_insensitive(self):
        """Test that term frequency analysis is case insensitive."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        # Create test data with mixed case
        test_data = [
            {
                "document_id": "test_001",
                "title": "Leaf Analysis",
                "abstract": "Study of LEAF structures and leaf development",
                "terms": ["Leaf", "LEAF", "leaf"],
                "citations": 10
            }
        ]
        
        result = analyzer.analyze_term_frequency(test_data)
        
        # All variations should be counted as the same term
        assert "leaf" in result
        assert result["leaf"] == 3  # Should count all three occurrences
    
    def test_analyze_term_frequency_with_filters(self):
        """Test term frequency analysis with filtering options."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        # Test with minimum frequency filter
        test_data = [
            {"document_id": "doc1", "terms": ["leaf", "leaf", "root"], "citations": 5},
            {"document_id": "doc2", "terms": ["leaf", "stem"], "citations": 3},
        ]
        
        result = analyzer.analyze_term_frequency(test_data, min_frequency=2)
        
        assert "leaf" in result  # Appears 3 times, above threshold
        assert "root" not in result  # Appears 1 time, below threshold
        assert "stem" not in result  # Appears 1 time, below threshold
    
    def test_calculate_citation_impact_basic(self, mock_corpus_data):
        """Test basic citation impact calculation."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        # Mock the scholarly API response
        with patch('src.ontology.corpus_analyzer.scholarly') as mock_scholarly:
            mock_scholarly.search_pubs_query.return_value = [
                Mock(citedby=15),
                Mock(citedby=22),
                Mock(citedby=18)
            ]
            
            result = analyzer.calculate_citation_impact(["leaf", "root", "stem"])
            
            assert isinstance(result, dict)
            assert "leaf" in result
            assert "root" in result
            assert "stem" in result
            assert all(isinstance(score, (int, float)) for score in result.values())
    
    def test_calculate_citation_impact_no_results(self):
        """Test citation impact calculation when no results found."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        with patch('src.ontology.corpus_analyzer.scholarly') as mock_scholarly:
            mock_scholarly.search_pubs_query.return_value = []
            
            result = analyzer.calculate_citation_impact(["nonexistent_term"])
            
            assert isinstance(result, dict)
            assert "nonexistent_term" in result
            assert result["nonexistent_term"] == 0
    
    def test_calculate_citation_impact_with_timeout(self):
        """Test citation impact calculation with API timeout handling."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        with patch('src.ontology.corpus_analyzer.scholarly') as mock_scholarly:
            mock_scholarly.search_pubs_query.side_effect = TimeoutError("API timeout")
            
            result = analyzer.calculate_citation_impact(["leaf"])
            
            # Should handle timeout gracefully
            assert isinstance(result, dict)
            assert "leaf" in result
            assert result["leaf"] == 0  # Default value on error
    
    def test_calculate_citation_impact_weighted_scoring(self):
        """Test citation impact calculation with weighted scoring."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        with patch('src.ontology.corpus_analyzer.scholarly') as mock_scholarly:
            # Mock different citation counts
            mock_scholarly.search_pubs_query.return_value = [
                Mock(citedby=100),  # High impact
                Mock(citedby=50),   # Medium impact
                Mock(citedby=10)    # Low impact
            ]
            
            result = analyzer.calculate_citation_impact(["high_impact_term"], 
                                                      weight_recent=True)
            
            assert isinstance(result, dict)
            assert "high_impact_term" in result
            assert result["high_impact_term"] > 0
    
    def test_get_term_statistics_comprehensive(self, mock_corpus_data):
        """Test comprehensive term statistics calculation."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        with patch.object(analyzer, 'calculate_citation_impact') as mock_citation:
            mock_citation.return_value = {"leaf": 45, "root": 38, "stem": 28}
            
            result = analyzer.get_term_statistics(mock_corpus_data)
            
            assert isinstance(result, dict)
            assert "leaf" in result
            
            # Check that result contains both frequency and citation data
            leaf_stats = result["leaf"]
            assert "frequency" in leaf_stats
            assert "citation_impact" in leaf_stats
            assert "combined_score" in leaf_stats
            assert isinstance(leaf_stats["frequency"], int)
            assert isinstance(leaf_stats["citation_impact"], (int, float))
            assert isinstance(leaf_stats["combined_score"], (int, float))
    
    def test_normalize_term_basic(self):
        """Test basic term normalization functionality."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        # Test various normalization scenarios
        assert analyzer.normalize_term("Leaf") == "leaf"
        assert analyzer.normalize_term("LEAF") == "leaf"
        assert analyzer.normalize_term("leaf") == "leaf"
        assert analyzer.normalize_term("  Leaf  ") == "leaf"
        assert analyzer.normalize_term("leaf-tissue") == "leaf-tissue"
    
    def test_filter_terms_by_relevance(self):
        """Test filtering terms by relevance score."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        term_stats = {
            "leaf": {"combined_score": 0.95},
            "root": {"combined_score": 0.85},
            "stem": {"combined_score": 0.75},
            "irrelevant": {"combined_score": 0.45}
        }
        
        result = analyzer.filter_terms_by_relevance(term_stats, threshold=0.8)
        
        assert "leaf" in result
        assert "root" in result
        assert "stem" not in result  # Below threshold
        assert "irrelevant" not in result  # Below threshold
    
    def test_export_analysis_results(self, tmp_path):
        """Test exporting analysis results to file."""
        from src.ontology.corpus_analyzer import CorpusAnalyzer
        
        analyzer = CorpusAnalyzer()
        
        test_results = {
            "leaf": {"frequency": 150, "citation_impact": 45, "combined_score": 0.95},
            "root": {"frequency": 120, "citation_impact": 38, "combined_score": 0.85}
        }
        
        output_file = tmp_path / "analysis_results.json"
        analyzer.export_analysis_results(test_results, str(output_file))
        
        assert output_file.exists()
        
        # Verify file contents
        import json
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        assert loaded_data == test_results
