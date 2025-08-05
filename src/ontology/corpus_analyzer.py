"""
Corpus Analyzer for Plant Metabolite Knowledge Extraction.

This module provides functionality for analyzing literature corpus to extract
term frequency information and calculate citation impact scores for ontology terms.
"""

import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import re

try:
    import scholarly
except ImportError:
    scholarly = None

from loguru import logger


class CorpusAnalyzer:
    """
    Analyzes literature corpus for term frequency and citation impact.
    
    This class provides methods to analyze a corpus of scientific literature
    to extract term frequencies, calculate citation impact scores, and generate
    comprehensive statistics for ontology term selection.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CorpusAnalyzer.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # Default configuration
        self.default_config = {
            "min_term_length": 2,
            "max_term_length": 50,
            "case_sensitive": False,
            "include_stopwords": False,
            "citation_weight": 0.3,
            "frequency_weight": 0.7
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def analyze_term_frequency(self, 
                             corpus_data: List[Dict[str, Any]], 
                             min_frequency: int = 1) -> Dict[str, int]:
        """
        Analyze term frequency in the corpus.
        
        Args:
            corpus_data: List of documents with terms and metadata
            min_frequency: Minimum frequency threshold for inclusion
            
        Returns:
            Dictionary mapping terms to their frequencies
        """
        if not corpus_data:
            return {}
        
        term_counter = Counter()
        
        for document in corpus_data:
            terms = document.get("terms", [])
            
            for term in terms:
                normalized_term = self.normalize_term(term)
                if self._is_valid_term(normalized_term):
                    term_counter[normalized_term] += 1
        
        # Filter by minimum frequency
        filtered_terms = {
            term: count for term, count in term_counter.items()
            if count >= min_frequency
        }
        
        self.logger.info(f"Analyzed {len(corpus_data)} documents, "
                        f"found {len(filtered_terms)} terms above threshold")
        
        return filtered_terms
    
    def calculate_citation_impact(self, 
                                terms: List[str], 
                                weight_recent: bool = False) -> Dict[str, float]:
        """
        Calculate citation impact scores for terms.
        
        Args:
            terms: List of terms to analyze
            weight_recent: Whether to weight recent citations more heavily
            
        Returns:
            Dictionary mapping terms to citation impact scores
        """
        if not scholarly:
            self.logger.warning("Scholarly library not available, returning zero scores")
            return {term: 0.0 for term in terms}
        
        citation_scores = {}
        
        for term in terms:
            try:
                # Search for publications related to the term
                search_query = f'"{term}" plant metabolite'
                publications = list(scholarly.search_pubs_query(search_query))
                
                if not publications:
                    citation_scores[term] = 0.0
                    continue
                
                # Calculate citation impact
                total_citations = sum(
                    getattr(pub, 'citedby', 0) for pub in publications[:10]  # Limit to top 10
                )
                
                # Normalize by number of publications
                avg_citations = total_citations / min(len(publications), 10)
                
                # Apply weighting if requested
                if weight_recent:
                    # Simple recency weighting (would need publication dates in real implementation)
                    avg_citations *= 1.2
                
                citation_scores[term] = avg_citations
                
            except (TimeoutError, Exception) as e:
                self.logger.warning(f"Error calculating citation impact for '{term}': {e}")
                citation_scores[term] = 0.0
        
        self.logger.info(f"Calculated citation impact for {len(terms)} terms")
        return citation_scores
    
    def get_term_statistics(self, corpus_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """
        Get comprehensive statistics for terms in the corpus.
        
        Args:
            corpus_data: List of documents with terms and metadata
            
        Returns:
            Dictionary with comprehensive term statistics
        """
        # Get frequency data
        frequency_data = self.analyze_term_frequency(corpus_data)
        
        # Get citation impact data
        terms = list(frequency_data.keys())
        citation_data = self.calculate_citation_impact(terms)
        
        # Combine statistics
        term_stats = {}
        
        for term in terms:
            frequency = frequency_data.get(term, 0)
            citation_impact = citation_data.get(term, 0.0)
            
            # Calculate combined score
            freq_weight = self.config["frequency_weight"]
            cite_weight = self.config["citation_weight"]
            
            # Normalize frequency (simple min-max normalization)
            max_freq = max(frequency_data.values()) if frequency_data else 1
            normalized_freq = frequency / max_freq
            
            # Normalize citation impact
            max_citations = max(citation_data.values()) if citation_data else 1
            normalized_citations = citation_impact / max_citations if max_citations > 0 else 0
            
            combined_score = (freq_weight * normalized_freq + 
                            cite_weight * normalized_citations)
            
            term_stats[term] = {
                "frequency": frequency,
                "citation_impact": citation_impact,
                "combined_score": combined_score
            }
        
        return term_stats
    
    def normalize_term(self, term: str) -> str:
        """
        Normalize a term for consistent processing.
        
        Args:
            term: Raw term string
            
        Returns:
            Normalized term string
        """
        if not term:
            return ""
        
        # Strip whitespace
        normalized = term.strip()
        
        # Convert to lowercase if not case sensitive
        if not self.config["case_sensitive"]:
            normalized = normalized.lower()
        
        return normalized
    
    def filter_terms_by_relevance(self, 
                                term_stats: Dict[str, Dict[str, float]], 
                                threshold: float = 0.8) -> Dict[str, Dict[str, float]]:
        """
        Filter terms by relevance score threshold.
        
        Args:
            term_stats: Dictionary of term statistics
            threshold: Minimum combined score threshold
            
        Returns:
            Filtered dictionary of term statistics
        """
        filtered_stats = {
            term: stats for term, stats in term_stats.items()
            if stats.get("combined_score", 0) >= threshold
        }
        
        self.logger.info(f"Filtered {len(term_stats)} terms to {len(filtered_stats)} "
                        f"above threshold {threshold}")
        
        return filtered_stats
    
    def export_analysis_results(self, 
                               results: Dict[str, Any], 
                               output_path: str) -> None:
        """
        Export analysis results to a JSON file.
        
        Args:
            results: Analysis results to export
            output_path: Path to output file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported analysis results to {output_path}")
    
    def _is_valid_term(self, term: str) -> bool:
        """
        Check if a term is valid for analysis.
        
        Args:
            term: Term to validate
            
        Returns:
            True if term is valid, False otherwise
        """
        if not term:
            return False
        
        # Check length constraints
        if len(term) < self.config["min_term_length"]:
            return False
        
        if len(term) > self.config["max_term_length"]:
            return False
        
        # Check for basic validity (contains letters)
        if not re.search(r'[a-zA-Z]', term):
            return False
        
        return True
