"""
Term Clusterer for Plant Metabolite Knowledge Extraction.

This module provides functionality for hierarchical clustering of ontology terms
to group similar terms together for ontology trimming and organization.
"""

import json
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import re
from collections import defaultdict

from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import pdist, squareform
from scipy.cluster.hierarchy import dendrogram, linkage
import Levenshtein

from loguru import logger


class TermClusterer:
    """
    Clusters similar ontology terms using hierarchical clustering.
    
    This class provides methods to cluster similar terms based on string similarity,
    semantic similarity, and optional metadata to help with ontology organization
    and term reduction.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the TermClusterer.

        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.config = config or {}
        self.logger = logger

        # Default configuration
        self.default_config = {
            "similarity_threshold": 0.7,
            "clustering_method": "complete",  # Changed from ward to complete
            "similarity_method": "cosine",
            "min_cluster_size": 1,
            "max_clusters": None,
            "use_metadata": False,
            "metadata_weight": 0.3
        }

        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value

        # Override with any kwargs
        for key, value in kwargs.items():
            self.config[key] = value
    
    def cluster_similar_terms(self, terms: List[str]) -> Dict[str, Any]:
        """
        Cluster similar terms using hierarchical clustering.
        
        Args:
            terms: List of terms to cluster
            
        Returns:
            Dictionary containing clustering results
        """
        if not terms:
            return {
                "clusters": {},
                "cluster_labels": [],
                "similarity_matrix": None
            }
        
        if len(terms) == 1:
            return {
                "clusters": {0: [terms[0]]},
                "cluster_labels": [0],
                "similarity_matrix": np.array([[1.0]])
            }
        
        # Calculate similarity matrix
        similarity_matrix = self.calculate_similarity_matrix(terms)
        
        # Convert similarity to distance
        distance_matrix = 1 - similarity_matrix
        
        # Perform hierarchical clustering
        n_clusters = self._determine_optimal_clusters(distance_matrix, terms)

        # Ensure diagonal is zero for precomputed distances
        np.fill_diagonal(distance_matrix, 0)

        # Use appropriate linkage method for precomputed distances
        linkage_method = self.config["clustering_method"]
        if linkage_method == "ward":
            # Ward doesn't work with precomputed, use complete instead
            linkage_method = "complete"

        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric='precomputed',
            linkage=linkage_method
        )

        cluster_labels = clustering.fit_predict(distance_matrix)
        
        # Organize results
        clusters = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            clusters[label].append(terms[i])
        
        result = {
            "clusters": dict(clusters),
            "cluster_labels": cluster_labels.tolist(),
            "similarity_matrix": similarity_matrix
        }
        
        self.logger.info(f"Clustered {len(terms)} terms into {len(clusters)} clusters")
        
        return result
    
    def calculate_similarity_matrix(self, terms: List[str]) -> Optional[np.ndarray]:
        """
        Calculate similarity matrix for terms.
        
        Args:
            terms: List of terms
            
        Returns:
            Similarity matrix as numpy array
        """
        if not terms:
            return None
        
        n_terms = len(terms)
        similarity_matrix = np.zeros((n_terms, n_terms))
        
        for i in range(n_terms):
            for j in range(n_terms):
                if i == j:
                    similarity_matrix[i, j] = 1.0
                else:
                    similarity = self.calculate_string_similarity(terms[i], terms[j])
                    similarity_matrix[i, j] = similarity
        
        return similarity_matrix
    
    def calculate_string_similarity(self, term1: str, term2: str) -> float:
        """
        Calculate similarity between two terms.
        
        Args:
            term1: First term
            term2: Second term
            
        Returns:
            Similarity score between 0 and 1
        """
        if not term1 or not term2:
            return 0.0
        
        method = self.config["similarity_method"]
        
        if method == "jaccard":
            return self._jaccard_similarity(term1, term2)
        elif method == "cosine":
            return self._cosine_similarity(term1, term2)
        elif method == "levenshtein":
            return self._levenshtein_similarity(term1, term2)
        else:
            # Default to cosine similarity
            return self._cosine_similarity(term1, term2)
    
    def validate_clusters(self, clustering_result: Dict[str, Any], terms: List[str]) -> Dict[str, float]:
        """
        Validate clustering quality using various metrics.
        
        Args:
            clustering_result: Result from clustering
            terms: Original terms list
            
        Returns:
            Dictionary with validation metrics
        """
        if not terms or not clustering_result["cluster_labels"]:
            return {
                "silhouette_score": 0.0,
                "inertia": 0.0,
                "cluster_sizes": {}
            }
        
        cluster_labels = clustering_result["cluster_labels"]
        similarity_matrix = clustering_result["similarity_matrix"]
        
        # Calculate silhouette score
        if len(set(cluster_labels)) > 1 and similarity_matrix is not None:
            distance_matrix = 1 - similarity_matrix
            # Ensure diagonal is zero for precomputed distances
            np.fill_diagonal(distance_matrix, 0)
            sil_score = silhouette_score(distance_matrix, cluster_labels, metric='precomputed')
        else:
            sil_score = 0.0
        
        # Calculate inertia (within-cluster sum of squares)
        inertia = self._calculate_inertia(clustering_result, similarity_matrix)
        
        # Calculate cluster sizes
        cluster_sizes = {}
        for cluster_id, cluster_terms in clustering_result["clusters"].items():
            cluster_sizes[cluster_id] = len(cluster_terms)
        
        return {
            "silhouette_score": sil_score,
            "inertia": inertia,
            "cluster_sizes": cluster_sizes
        }
    
    def optimize_cluster_number(self, terms: List[str], max_clusters: int = 10) -> int:
        """
        Find optimal number of clusters using elbow method.
        
        Args:
            terms: List of terms to cluster
            max_clusters: Maximum number of clusters to try
            
        Returns:
            Optimal number of clusters
        """
        if len(terms) <= 1:
            return 1
        
        max_clusters = min(max_clusters, len(terms))
        
        similarity_matrix = self.calculate_similarity_matrix(terms)
        distance_matrix = 1 - similarity_matrix
        # Ensure diagonal is zero for precomputed distances
        np.fill_diagonal(distance_matrix, 0)

        inertias = []
        silhouette_scores = []

        # Use appropriate linkage method for precomputed distances
        linkage_method = self.config["clustering_method"]
        if linkage_method == "ward":
            linkage_method = "complete"

        for k in range(2, max_clusters + 1):
            clustering = AgglomerativeClustering(
                n_clusters=k,
                metric='precomputed',
                linkage=linkage_method
            )

            labels = clustering.fit_predict(distance_matrix)
            
            # Calculate metrics
            sil_score = silhouette_score(distance_matrix, labels, metric='precomputed')
            silhouette_scores.append(sil_score)
            
            # Simple inertia calculation
            inertia = self._calculate_inertia_for_labels(labels, distance_matrix)
            inertias.append(inertia)
        
        # Find optimal k using silhouette score
        if silhouette_scores:
            optimal_k = int(np.argmax(silhouette_scores) + 2)  # +2 because we start from k=2
        else:
            optimal_k = 2

        return optimal_k
    
    def get_cluster_representatives(self, clustering_result: Dict[str, Any], terms: List[str]) -> Dict[int, str]:
        """
        Get representative term for each cluster.
        
        Args:
            clustering_result: Result from clustering
            terms: Original terms list
            
        Returns:
            Dictionary mapping cluster ID to representative term
        """
        representatives = {}
        similarity_matrix = clustering_result["similarity_matrix"]
        
        for cluster_id, cluster_terms in clustering_result["clusters"].items():
            if len(cluster_terms) == 1:
                representatives[cluster_id] = cluster_terms[0]
            else:
                # Find term with highest average similarity to others in cluster
                cluster_indices = [terms.index(term) for term in cluster_terms]
                
                best_score = -1
                best_term = cluster_terms[0]
                
                for term in cluster_terms:
                    term_idx = terms.index(term)
                    avg_similarity = np.mean([
                        similarity_matrix[term_idx, other_idx] 
                        for other_idx in cluster_indices if other_idx != term_idx
                    ])
                    
                    if avg_similarity > best_score:
                        best_score = avg_similarity
                        best_term = term
                
                representatives[cluster_id] = best_term
        
        return representatives
    
    def merge_similar_clusters(self, clustering_result: Dict[str, Any], terms: List[str], merge_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Merge clusters that are very similar to each other.
        
        Args:
            clustering_result: Initial clustering result
            terms: Original terms list
            merge_threshold: Threshold for merging clusters
            
        Returns:
            Updated clustering result with merged clusters
        """
        clusters = clustering_result["clusters"].copy()
        representatives = self.get_cluster_representatives(clustering_result, terms)
        
        # Calculate inter-cluster similarities
        cluster_ids = list(clusters.keys())
        merged = set()
        
        for i, cluster_id1 in enumerate(cluster_ids):
            if cluster_id1 in merged:
                continue
                
            for cluster_id2 in cluster_ids[i+1:]:
                if cluster_id2 in merged:
                    continue
                
                # Calculate similarity between cluster representatives
                rep1 = representatives[cluster_id1]
                rep2 = representatives[cluster_id2]
                similarity = self.calculate_string_similarity(rep1, rep2)
                
                if similarity >= merge_threshold:
                    # Merge cluster_id2 into cluster_id1
                    clusters[cluster_id1].extend(clusters[cluster_id2])
                    del clusters[cluster_id2]
                    merged.add(cluster_id2)
        
        # Rebuild cluster labels
        new_cluster_labels = [-1] * len(terms)
        for new_id, (cluster_id, cluster_terms) in enumerate(clusters.items()):
            for term in cluster_terms:
                term_idx = terms.index(term)
                new_cluster_labels[term_idx] = new_id
        
        # Renumber clusters to be consecutive
        renumbered_clusters = {}
        for new_id, (old_id, cluster_terms) in enumerate(clusters.items()):
            renumbered_clusters[new_id] = cluster_terms
        
        return {
            "clusters": renumbered_clusters,
            "cluster_labels": new_cluster_labels,
            "similarity_matrix": clustering_result["similarity_matrix"]
        }
    
    def cluster_similar_terms_with_metadata(self, terms_with_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Cluster terms incorporating metadata information.
        
        Args:
            terms_with_metadata: List of term dictionaries with metadata
            
        Returns:
            Clustering result with metadata weights
        """
        if not terms_with_metadata:
            return {
                "clusters": {},
                "cluster_labels": [],
                "similarity_matrix": None,
                "metadata_weights": None
            }
        
        terms = [term_data["label"].lower() for term_data in terms_with_metadata]
        
        # Calculate string similarity matrix
        string_similarity = self.calculate_similarity_matrix(terms)
        
        # Calculate metadata similarity if available
        metadata_similarity = self._calculate_metadata_similarity(terms_with_metadata)
        
        # Combine similarities
        if metadata_similarity is not None:
            metadata_weight = self.config["metadata_weight"]
            combined_similarity = (
                (1 - metadata_weight) * string_similarity + 
                metadata_weight * metadata_similarity
            )
        else:
            combined_similarity = string_similarity
        
        # Perform clustering with combined similarity
        distance_matrix = 1 - combined_similarity
        n_clusters = self._determine_optimal_clusters(distance_matrix, terms)
        
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric='precomputed',
            linkage=self.config["clustering_method"]
        )
        
        cluster_labels = clustering.fit_predict(distance_matrix)
        
        # Organize results
        clusters = defaultdict(list)
        for i, label in enumerate(cluster_labels):
            clusters[label].append(terms[i])
        
        return {
            "clusters": dict(clusters),
            "cluster_labels": cluster_labels.tolist(),
            "similarity_matrix": combined_similarity,
            "metadata_weights": metadata_similarity
        }
    
    def export_clustering_results(self, clustering_result: Dict[str, Any], output_path: str) -> None:
        """
        Export clustering results to a JSON file.
        
        Args:
            clustering_result: Clustering results to export
            output_path: Path to output file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy arrays and types to JSON-serializable formats
        exportable_result = clustering_result.copy()

        # Convert similarity matrix
        if "similarity_matrix" in exportable_result and exportable_result["similarity_matrix"] is not None:
            exportable_result["similarity_matrix"] = exportable_result["similarity_matrix"].tolist()

        # Convert cluster keys from numpy int64 to regular int
        if "clusters" in exportable_result:
            clusters_dict = {}
            for key, value in exportable_result["clusters"].items():
                clusters_dict[int(key)] = value
            exportable_result["clusters"] = clusters_dict

        # Convert cluster labels from numpy types to regular int
        if "cluster_labels" in exportable_result:
            exportable_result["cluster_labels"] = [int(label) for label in exportable_result["cluster_labels"]]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(exportable_result, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported clustering results to {output_path}")
    
    def _jaccard_similarity(self, term1: str, term2: str) -> float:
        """Calculate Jaccard similarity between two terms."""
        set1 = set(term1.lower().split())
        set2 = set(term2.lower().split())
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _cosine_similarity(self, term1: str, term2: str) -> float:
        """Calculate cosine similarity between two terms."""
        vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(2, 3))
        try:
            tfidf_matrix = vectorizer.fit_transform([term1.lower(), term2.lower()])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Round to avoid floating point precision issues
            return round(float(similarity), 10)
        except:
            return 0.0
    
    def _levenshtein_similarity(self, term1: str, term2: str) -> float:
        """Calculate normalized Levenshtein similarity."""
        distance = Levenshtein.distance(term1.lower(), term2.lower())
        max_len = max(len(term1), len(term2))
        return 1 - (distance / max_len) if max_len > 0 else 1.0
    
    def _determine_optimal_clusters(self, distance_matrix: np.ndarray, terms: List[str]) -> int:
        """Determine optimal number of clusters."""
        max_clusters = self.config.get("max_clusters")
        if max_clusters is None:
            max_clusters = min(10, len(terms))
        
        if len(terms) <= 2:
            return len(terms)
        
        # Use threshold-based clustering if specified
        threshold = self.config["similarity_threshold"]
        if threshold:
            # Simple threshold-based approach
            linkage_matrix = linkage(squareform(distance_matrix), method=self.config["clustering_method"])
            # Find number of clusters at threshold
            from scipy.cluster.hierarchy import fcluster
            cluster_labels = fcluster(linkage_matrix, 1 - threshold, criterion='distance')
            return len(np.unique(cluster_labels))
        
        return min(max_clusters, len(terms))
    
    def _calculate_inertia(self, clustering_result: Dict[str, Any], similarity_matrix: np.ndarray) -> float:
        """Calculate clustering inertia."""
        if similarity_matrix is None:
            return 0.0
        
        inertia = 0.0
        clusters = clustering_result["clusters"]
        
        for cluster_terms in clusters.values():
            if len(cluster_terms) > 1:
                # Calculate within-cluster distances
                cluster_distances = []
                for i, term1 in enumerate(cluster_terms):
                    for term2 in cluster_terms[i+1:]:
                        # This is a simplified calculation
                        cluster_distances.append(1.0)  # Placeholder
                
                inertia += sum(cluster_distances)
        
        return inertia
    
    def _calculate_inertia_for_labels(self, labels: np.ndarray, distance_matrix: np.ndarray) -> float:
        """Calculate inertia for given cluster labels."""
        inertia = 0.0
        unique_labels = np.unique(labels)
        
        for label in unique_labels:
            cluster_indices = np.where(labels == label)[0]
            if len(cluster_indices) > 1:
                cluster_distances = distance_matrix[np.ix_(cluster_indices, cluster_indices)]
                inertia += np.sum(cluster_distances)
        
        return inertia
    
    def _calculate_metadata_similarity(self, terms_with_metadata: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """Calculate similarity matrix based on metadata."""
        if not terms_with_metadata or "frequency" not in terms_with_metadata[0]:
            return None
        
        n_terms = len(terms_with_metadata)
        metadata_similarity = np.zeros((n_terms, n_terms))
        
        # Extract frequency and citation data
        frequencies = [term.get("frequency", 0) for term in terms_with_metadata]
        citations = [term.get("citation_count", 0) for term in terms_with_metadata]
        
        # Normalize
        max_freq = max(frequencies) if frequencies else 1
        max_cite = max(citations) if citations else 1
        
        for i in range(n_terms):
            for j in range(n_terms):
                if i == j:
                    metadata_similarity[i, j] = 1.0
                else:
                    # Simple metadata similarity based on frequency and citation similarity
                    freq_sim = 1 - abs(frequencies[i] - frequencies[j]) / max_freq
                    cite_sim = 1 - abs(citations[i] - citations[j]) / max_cite
                    metadata_similarity[i, j] = (freq_sim + cite_sim) / 2
        
        return metadata_similarity
