"""
Automated Validator for Plant Metabolite Knowledge Extraction.

This module provides functionality for automated validation of ontology terms
through cross-reference validation and multi-metric scoring systems.
"""

import json
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path
import time
from collections import defaultdict

try:
    from SPARQLWrapper import SPARQLWrapper, JSON
except ImportError:
    SPARQLWrapper = None
    JSON = None

from loguru import logger


class AutomatedValidator:
    """
    Validates ontology terms using cross-reference validation and multi-metric scoring.
    
    This class provides methods to validate terms against established ontologies,
    calculate comprehensive scores, and generate validation reports for term selection.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the AutomatedValidator.
        
        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.config = config or {}
        self.logger = logger
        
        # Default configuration
        self.default_config = {
            "ontology_sources": ["Plant Ontology", "Gene Ontology"],
            "selection_threshold": 0.8,
            "scoring_weights": {
                "frequency": 0.3,
                "citation_impact": 0.25,
                "validation_confidence": 0.3,
                "cluster_coherence": 0.15
            },
            "sparql_timeout": 30,
            "max_retries": 3,
            "validation_cache": True
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Override with any kwargs
        for key, value in kwargs.items():
            self.config[key] = value
        
        # Initialize validation cache
        self.validation_cache = {} if self.config["validation_cache"] else None
        
        # SPARQL endpoints for different ontologies
        self.sparql_endpoints = {
            "Plant Ontology": "http://sparql.plantontology.org/sparql",
            "Gene Ontology": "http://sparql.geneontology.org/sparql",
            "Chemical Ontology": "http://sparql.bioontology.org/sparql"
        }
    
    def cross_reference_validation(self, terms: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Validate terms against external ontology sources.
        
        Args:
            terms: List of terms to validate
            
        Returns:
            Dictionary with validation results for each term
        """
        if not terms:
            return {}
        
        validation_results = {}
        ontology_sources = self.config["ontology_sources"]
        
        for term in terms:
            term_results = []
            
            for source in ontology_sources:
                # Check cache first
                cache_key = f"{term}_{source}"
                if self.validation_cache and cache_key in self.validation_cache:
                    result = self.validation_cache[cache_key]
                else:
                    result = self._query_external_ontology(term, source)
                    if self.validation_cache:
                        self.validation_cache[cache_key] = result
                
                if term in result:
                    term_results.append(result[term])
            
            # Aggregate results from multiple sources
            if term_results:
                validation_results[term] = self._aggregate_validation_results(term_results)
            else:
                validation_results[term] = {
                    "found": False,
                    "confidence": 0.0,
                    "source": "None",
                    "sources_checked": ontology_sources
                }
        
        self.logger.info(f"Validated {len(terms)} terms against {len(ontology_sources)} ontology sources")
        return validation_results
    
    def calculate_multi_metric_score(self, term_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculate comprehensive scores using multiple metrics.
        
        Args:
            term_data: Dictionary with term data including various metrics
            
        Returns:
            Dictionary with calculated scores for each term
        """
        if not term_data:
            return {}
        
        scoring_results = {}
        weights = self.config["scoring_weights"]
        
        # Extract raw scores for normalization
        raw_scores = defaultdict(list)
        terms = list(term_data.keys())
        
        for term, data in term_data.items():
            for metric in weights.keys():
                if metric in data:
                    raw_scores[metric].append(data[metric])
                else:
                    raw_scores[metric].append(0.0)
        
        # Normalize scores
        normalized_scores = self._normalize_scores(raw_scores)
        
        # Calculate combined scores
        for i, term in enumerate(terms):
            component_scores = {}
            combined_score = 0.0
            
            for metric, weight in weights.items():
                if metric in normalized_scores:
                    score = normalized_scores[metric][i]
                    component_scores[metric] = score
                    combined_score += weight * score
            
            scoring_results[term] = {
                "combined_score": combined_score,
                "component_scores": component_scores
            }
        
        self.logger.info(f"Calculated multi-metric scores for {len(terms)} terms")
        return scoring_results
    
    def validate_term_selection(self, terms: List[str], term_metadata: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Perform comprehensive term selection validation.
        
        Args:
            terms: List of terms to validate
            term_metadata: Optional metadata for terms
            
        Returns:
            Comprehensive validation results
        """
        # Perform cross-reference validation
        validation_results = self.cross_reference_validation(terms)
        
        # Prepare data for scoring
        if term_metadata:
            scoring_data = term_metadata.copy()
            # Add validation confidence to scoring data
            for term in terms:
                if term in validation_results and term in scoring_data:
                    scoring_data[term]["validation_confidence"] = validation_results[term]["confidence"]
        else:
            # Create minimal scoring data from validation results
            scoring_data = {}
            for term in terms:
                if term in validation_results:
                    scoring_data[term] = {
                        "validation_confidence": validation_results[term]["confidence"],
                        "frequency": 1.0,  # Default values
                        "citation_impact": 1.0,
                        "cluster_coherence": 1.0
                    }
        
        # Calculate multi-metric scores
        scoring_results = self.calculate_multi_metric_score(scoring_data)
        
        # Apply selection threshold
        threshold = self.config["selection_threshold"]
        recommended_terms = []
        rejected_terms = []
        
        for term in terms:
            if term in scoring_results:
                score = scoring_results[term]["combined_score"]
                if score >= threshold:
                    recommended_terms.append(term)
                else:
                    rejected_terms.append(term)
            else:
                rejected_terms.append(term)
        
        return {
            "validation_results": validation_results,
            "scoring_results": scoring_results,
            "recommended_terms": recommended_terms,
            "rejected_terms": rejected_terms,
            "threshold_used": threshold,
            "summary": {
                "total_terms": len(terms),
                "recommended": len(recommended_terms),
                "rejected": len(rejected_terms),
                "recommendation_rate": len(recommended_terms) / len(terms) if terms else 0
            }
        }
    
    def generate_validation_report(self, validation_results: Dict[str, Any], output_path: str) -> None:
        """
        Generate a comprehensive validation report.
        
        Args:
            validation_results: Results from validate_term_selection
            output_path: Path to output file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata to the report
        report_data = validation_results.copy()
        report_data["metadata"] = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "configuration": self.config,
            "ontology_sources": self.config["ontology_sources"],
            "selection_threshold": self.config["selection_threshold"]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Generated validation report at {output_path}")
    
    def _query_external_ontology(self, term: str, ontology_source: str) -> Dict[str, Dict[str, Any]]:
        """
        Query an external ontology for term validation.
        
        Args:
            term: Term to query
            ontology_source: Name of ontology source
            
        Returns:
            Validation result for the term
        """
        if not SPARQLWrapper:
            self.logger.warning("SPARQLWrapper not available, returning mock results")
            return {
                term: {
                    "found": True,
                    "confidence": 0.8,
                    "source": ontology_source,
                    "uri": f"http://example.org/{term}"
                }
            }
        
        endpoint_url = self.sparql_endpoints.get(ontology_source)
        if not endpoint_url:
            return {
                term: {
                    "found": False,
                    "confidence": 0.0,
                    "source": ontology_source,
                    "error": "Unknown ontology source"
                }
            }
        
        try:
            sparql = SPARQLWrapper(endpoint_url)
            sparql.setTimeout(self.config["sparql_timeout"])
            
            # Construct SPARQL query based on ontology source
            if ontology_source == "Plant Ontology":
                query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                PREFIX obo: <http://purl.obolibrary.org/obo/>
                
                SELECT ?term WHERE {{
                    ?term rdfs:label ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
                }}
                LIMIT 10
                """
            else:
                # Generic query for other ontologies
                query = f"""
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                
                SELECT ?term WHERE {{
                    ?term rdfs:label ?label .
                    FILTER(CONTAINS(LCASE(?label), LCASE("{term}")))
                }}
                LIMIT 10
                """
            
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)
            
            results = sparql.query().convert()
            
            # Process results
            if results["results"]["bindings"]:
                return {
                    term: {
                        "found": True,
                        "confidence": 0.9,  # High confidence for exact matches
                        "source": ontology_source,
                        "uri": results["results"]["bindings"][0]["term"]["value"]
                    }
                }
            else:
                return {
                    term: {
                        "found": False,
                        "confidence": 0.0,
                        "source": ontology_source,
                        "uri": None
                    }
                }
                
        except (TimeoutError, Exception) as e:
            self.logger.warning(f"Error querying {ontology_source} for term '{term}': {e}")
            return {
                term: {
                    "found": False,
                    "confidence": 0.0,
                    "source": ontology_source,
                    "error": str(e)
                }
            }
    
    def _normalize_scores(self, raw_scores: Dict[str, List[float]]) -> Dict[str, List[float]]:
        """
        Normalize scores to 0-1 range using min-max normalization.
        
        Args:
            raw_scores: Dictionary of raw score lists
            
        Returns:
            Dictionary of normalized score lists
        """
        normalized = {}
        
        for metric, scores in raw_scores.items():
            if not scores:
                normalized[metric] = []
                continue
            
            min_score = min(scores)
            max_score = max(scores)
            
            if max_score == min_score:
                # All scores are the same
                normalized[metric] = [1.0] * len(scores)
            else:
                normalized[metric] = [
                    (score - min_score) / (max_score - min_score)
                    for score in scores
                ]
        
        return normalized
    
    def _aggregate_validation_results(self, results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate validation results from multiple sources.
        
        Args:
            results_list: List of validation results from different sources
            
        Returns:
            Aggregated validation result
        """
        if not results_list:
            return {"found": False, "confidence": 0.0, "source": "None"}
        
        # If any source found the term, consider it found
        found = any(result.get("found", False) for result in results_list)
        
        # Calculate weighted average confidence
        confidences = [result.get("confidence", 0.0) for result in results_list]
        avg_confidence = sum(confidences) / len(confidences)
        
        # Collect sources
        sources = [result.get("source", "Unknown") for result in results_list]
        
        return {
            "found": found,
            "confidence": avg_confidence,
            "source": ", ".join(sources),
            "individual_results": results_list
        }
