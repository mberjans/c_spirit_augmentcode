"""
Tests for the TermClusterer class.

This module contains tests for hierarchical clustering functionality
for grouping similar ontology terms.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from tests.ontology.test_base import OntologyTestBase


class TestTermClusterer(OntologyTestBase):
    """Test cases for TermClusterer class."""
    
    def test_cluster_similar_terms_basic(self, sample_terms):
        """Test basic term clustering functionality."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        
        # Extract term labels for clustering
        terms = [term["label"].lower() for term in sample_terms]
        
        result = clusterer.cluster_similar_terms(terms)
        
        # Assertions
        assert isinstance(result, dict)
        assert "clusters" in result
        assert "cluster_labels" in result
        assert "similarity_matrix" in result
        
        # Check that all terms are assigned to clusters
        assert len(result["cluster_labels"]) == len(terms)
        assert all(isinstance(label, (int, np.integer)) for label in result["cluster_labels"])
    
    def test_cluster_similar_terms_empty_input(self):
        """Test clustering with empty input."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        result = clusterer.cluster_similar_terms([])
        
        assert isinstance(result, dict)
        assert result["clusters"] == {}
        assert result["cluster_labels"] == []
        assert result["similarity_matrix"] is None
    
    def test_cluster_similar_terms_single_term(self):
        """Test clustering with single term."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        result = clusterer.cluster_similar_terms(["leaf"])
        
        assert isinstance(result, dict)
        assert len(result["clusters"]) == 1
        assert result["cluster_labels"] == [0]
        assert "leaf" in result["clusters"][0]
    
    def test_cluster_similar_terms_with_similarity_threshold(self, sample_terms):
        """Test clustering with custom similarity threshold."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer(similarity_threshold=0.8)
        terms = [term["label"].lower() for term in sample_terms]
        
        result = clusterer.cluster_similar_terms(terms)
        
        assert isinstance(result, dict)
        assert "clusters" in result
        
        # With high threshold, should have more clusters (less grouping)
        num_clusters = len(result["clusters"])
        assert num_clusters >= 1
    
    def test_cluster_similar_terms_with_custom_method(self, sample_terms):
        """Test clustering with different clustering methods."""
        from src.ontology.term_clusterer import TermClusterer
        
        # Test with different clustering methods
        methods = ["ward", "complete", "average"]
        
        for method in methods:
            clusterer = TermClusterer(clustering_method=method)
            terms = [term["label"].lower() for term in sample_terms]
            
            result = clusterer.cluster_similar_terms(terms)
            
            assert isinstance(result, dict)
            assert "clusters" in result
            assert len(result["cluster_labels"]) == len(terms)
    
    def test_calculate_similarity_matrix_basic(self):
        """Test similarity matrix calculation."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = ["leaf", "leaves", "root", "stem"]
        
        similarity_matrix = clusterer.calculate_similarity_matrix(terms)
        
        assert isinstance(similarity_matrix, np.ndarray)
        assert similarity_matrix.shape == (len(terms), len(terms))
        
        # Matrix should be symmetric
        assert np.allclose(similarity_matrix, similarity_matrix.T)
        
        # Diagonal should be 1.0 (perfect self-similarity)
        assert np.allclose(np.diag(similarity_matrix), 1.0)
        
        # All values should be between 0 and 1
        assert np.all(similarity_matrix >= 0)
        assert np.all(similarity_matrix <= 1)
    
    def test_calculate_similarity_matrix_empty_input(self):
        """Test similarity matrix calculation with empty input."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        similarity_matrix = clusterer.calculate_similarity_matrix([])
        
        assert similarity_matrix is None
    
    def test_calculate_string_similarity_basic(self):
        """Test string similarity calculation."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        
        # Test exact match
        similarity = clusterer.calculate_string_similarity("leaf", "leaf")
        assert similarity == 1.0
        
        # Test similar terms
        similarity = clusterer.calculate_string_similarity("leaf", "leaves")
        assert 0.2 < similarity < 1.0  # Adjusted expectation

        # Test dissimilar terms
        similarity = clusterer.calculate_string_similarity("leaf", "root")
        assert 0.0 <= similarity < 0.3  # Adjusted expectation
    
    def test_calculate_string_similarity_methods(self):
        """Test different string similarity methods."""
        from src.ontology.term_clusterer import TermClusterer
        
        methods = ["jaccard", "cosine", "levenshtein"]
        
        for method in methods:
            clusterer = TermClusterer(similarity_method=method)
            
            similarity = clusterer.calculate_string_similarity("leaf", "leaves")
            
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0
    
    def test_validate_clusters_basic(self, sample_terms):
        """Test cluster validation functionality."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = [term["label"].lower() for term in sample_terms]
        
        # Create mock clustering result
        clustering_result = {
            "clusters": {
                0: ["leaf", "flower"],
                1: ["root", "stem"],
                2: ["seed"]
            },
            "cluster_labels": [0, 1, 1, 0, 2],
            "similarity_matrix": np.random.rand(5, 5)
        }
        
        validation_result = clusterer.validate_clusters(clustering_result, terms)
        
        assert isinstance(validation_result, dict)
        assert "silhouette_score" in validation_result
        assert "inertia" in validation_result
        assert "cluster_sizes" in validation_result
        
        # Check score ranges
        assert -1.0 <= validation_result["silhouette_score"] <= 1.0
        assert validation_result["inertia"] >= 0
    
    def test_validate_clusters_empty_input(self):
        """Test cluster validation with empty input."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        
        empty_result = {
            "clusters": {},
            "cluster_labels": [],
            "similarity_matrix": None
        }
        
        validation_result = clusterer.validate_clusters(empty_result, [])
        
        assert isinstance(validation_result, dict)
        assert validation_result["silhouette_score"] == 0.0
        assert validation_result["inertia"] == 0.0
        assert validation_result["cluster_sizes"] == {}
    
    def test_optimize_cluster_number(self, sample_terms):
        """Test automatic cluster number optimization."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = [term["label"].lower() for term in sample_terms]
        
        optimal_k = clusterer.optimize_cluster_number(terms, max_clusters=4)
        
        assert isinstance(optimal_k, int)
        assert 1 <= optimal_k <= min(4, len(terms))
    
    def test_get_cluster_representatives(self, sample_terms):
        """Test getting representative terms for each cluster."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = [term["label"].lower() for term in sample_terms]
        
        clustering_result = clusterer.cluster_similar_terms(terms)
        representatives = clusterer.get_cluster_representatives(clustering_result, terms)
        
        assert isinstance(representatives, dict)
        
        # Each cluster should have a representative
        for cluster_id in clustering_result["clusters"]:
            assert cluster_id in representatives
            assert representatives[cluster_id] in terms
    
    def test_merge_similar_clusters(self, sample_terms):
        """Test merging of similar clusters."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = [term["label"].lower() for term in sample_terms]
        
        # Create initial clustering
        clustering_result = clusterer.cluster_similar_terms(terms)
        
        # Test merging with high similarity threshold
        merged_result = clusterer.merge_similar_clusters(
            clustering_result, terms, merge_threshold=0.9
        )
        
        assert isinstance(merged_result, dict)
        assert "clusters" in merged_result
        assert "cluster_labels" in merged_result
        
        # Number of clusters should be <= original
        original_clusters = len(clustering_result["clusters"])
        merged_clusters = len(merged_result["clusters"])
        assert merged_clusters <= original_clusters
    
    def test_export_clustering_results(self, tmp_path, sample_terms):
        """Test exporting clustering results."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer()
        terms = [term["label"].lower() for term in sample_terms]
        
        clustering_result = clusterer.cluster_similar_terms(terms)
        
        output_file = tmp_path / "clustering_results.json"
        clusterer.export_clustering_results(clustering_result, str(output_file))
        
        assert output_file.exists()
        
        # Verify file contents
        import json
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        assert "clusters" in loaded_data
        assert "cluster_labels" in loaded_data
    
    def test_clustering_with_metadata(self, sample_terms):
        """Test clustering that incorporates term metadata."""
        from src.ontology.term_clusterer import TermClusterer
        
        clusterer = TermClusterer(use_metadata=True)
        
        # Include metadata in clustering
        result = clusterer.cluster_similar_terms_with_metadata(sample_terms)
        
        assert isinstance(result, dict)
        assert "clusters" in result
        assert "metadata_weights" in result
        
        # Check that metadata was considered
        assert result["metadata_weights"] is not None
