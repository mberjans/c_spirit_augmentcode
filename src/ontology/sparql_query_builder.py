"""
SPARQL Query Builder for Plant Metabolite Knowledge Extraction.

This module provides functionality for building and executing SPARQL queries
against various ontology endpoints for term validation and information retrieval.
"""

import json
import time
import hashlib
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import re
from collections import defaultdict

try:
    from SPARQLWrapper import SPARQLWrapper, JSON
except ImportError:
    SPARQLWrapper = None
    JSON = None

from loguru import logger


class SPARQLQueryBuilder:
    """
    Builds and executes SPARQL queries for ontology term validation.
    
    This class provides methods to construct SPARQL queries for different types
    of ontology operations and execute them against various SPARQL endpoints.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the SPARQLQueryBuilder.
        
        Args:
            config: Optional configuration dictionary
            **kwargs: Additional configuration parameters
        """
        self.config = config or {}
        self.logger = logger
        
        # Default configuration
        self.default_config = {
            "timeout": 30,
            "max_retries": 3,
            "retry_delay": 1,
            "enable_cache": True,
            "cache_ttl": 3600,  # 1 hour
            "default_limit": 100,
            "user_agent": "PlantMetaboliteOntologyTrimmer/1.0"
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Override with any kwargs
        for key, value in kwargs.items():
            self.config[key] = value

        # Initialize cache (after processing all config)
        self.query_cache = {} if self.config["enable_cache"] else None
        
        # SPARQL endpoints for different ontologies
        self.ontology_endpoints = {
            "Plant Ontology": "http://sparql.plantontology.org/sparql",
            "Gene Ontology": "http://sparql.geneontology.org/sparql",
            "Chemical Ontology": "http://sparql.bioontology.org/sparql",
            "CHEBI": "https://www.ebi.ac.uk/rdf/services/chembl/sparql",
            "UniProt": "https://sparql.uniprot.org/sparql"
        }
        
        # Common prefixes for SPARQL queries
        self.common_prefixes = {
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "obo": "http://purl.obolibrary.org/obo/",
            "po": "http://purl.obolibrary.org/obo/PO_",
            "go": "http://purl.obolibrary.org/obo/GO_",
            "chebi": "http://purl.obolibrary.org/obo/CHEBI_"
        }
    
    def build_term_search_query(self, 
                               term: str, 
                               ontology: str, 
                               exact_match: bool = False,
                               case_sensitive: bool = False,
                               limit: int = None) -> str:
        """
        Build a SPARQL query to search for terms in an ontology.
        
        Args:
            term: Term to search for
            ontology: Target ontology name
            exact_match: Whether to perform exact matching
            case_sensitive: Whether search should be case sensitive
            limit: Maximum number of results
            
        Returns:
            SPARQL query string
        """
        prefixes = self._build_prefixes(ontology)
        limit_clause = f"LIMIT {limit or self.config['default_limit']}"
        
        if exact_match:
            if case_sensitive:
                filter_clause = f'FILTER(str(?label) = "{term}")'
            else:
                filter_clause = f'FILTER(LCASE(str(?label)) = LCASE("{term}"))'
        else:
            if case_sensitive:
                filter_clause = f'FILTER(CONTAINS(str(?label), "{term}"))'
            else:
                filter_clause = f'FILTER(CONTAINS(LCASE(str(?label)), LCASE("{term}")))'
        
        query = f"""
        {prefixes}
        
        SELECT DISTINCT ?term ?label ?definition WHERE {{
            ?term rdfs:label ?label .
            OPTIONAL {{ ?term rdfs:comment ?definition }}
            {filter_clause}
        }}
        ORDER BY ?label
        {limit_clause}
        """
        
        return query.strip()
    
    def build_hierarchy_query(self, 
                            term_uri: str, 
                            ontology: str,
                            direction: str = "both",
                            max_depth: int = None) -> str:
        """
        Build a SPARQL query to get term hierarchy information.
        
        Args:
            term_uri: URI of the term
            ontology: Target ontology name
            direction: "parents", "children", or "both"
            max_depth: Maximum depth to traverse
            
        Returns:
            SPARQL query string
        """
        prefixes = self._build_prefixes(ontology)
        
        if direction == "parents":
            pattern = f"<{term_uri}> rdfs:subClassOf+ ?parent ."
            select_vars = "?parent"
        elif direction == "children":
            pattern = f"?child rdfs:subClassOf+ <{term_uri}> ."
            select_vars = "?child"
        else:  # both
            pattern = f"""
            {{
                <{term_uri}> rdfs:subClassOf+ ?parent .
                BIND(?parent AS ?related)
                BIND("parent" AS ?relation)
            }} UNION {{
                ?child rdfs:subClassOf+ <{term_uri}> .
                BIND(?child AS ?related)
                BIND("child" AS ?relation)
            }}
            """
            select_vars = "?related ?relation"
        
        query = f"""
        {prefixes}
        
        SELECT DISTINCT {select_vars} ?label WHERE {{
            {pattern}
            ?related rdfs:label ?label .
        }}
        ORDER BY ?label
        """
        
        if max_depth:
            query += f"\nLIMIT {max_depth * 10}"  # Rough limit based on depth
        
        return query.strip()
    
    def build_property_query(self, 
                           term_uri: str, 
                           ontology: str,
                           property_type: str = None) -> str:
        """
        Build a SPARQL query to get term properties.
        
        Args:
            term_uri: URI of the term
            ontology: Target ontology name
            property_type: Specific property type to query
            
        Returns:
            SPARQL query string
        """
        prefixes = self._build_prefixes(ontology)
        
        if property_type:
            pattern = f"<{term_uri}> {property_type} ?value ."
            select_vars = "?value"
        else:
            pattern = f"<{term_uri}> ?property ?value ."
            select_vars = "?property ?value"
        
        query = f"""
        {prefixes}
        
        SELECT DISTINCT {select_vars} WHERE {{
            {pattern}
        }}
        ORDER BY ?property
        """
        
        return query.strip()
    
    def execute_query(self, query: str, endpoint_url: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query against an endpoint.
        
        Args:
            query: SPARQL query string
            endpoint_url: SPARQL endpoint URL
            
        Returns:
            Query results dictionary
        """
        if not SPARQLWrapper:
            self.logger.warning("SPARQLWrapper not available, returning empty results")
            return {"results": {"bindings": []}}
        
        retries = 0
        max_retries = self.config["max_retries"]
        
        while retries <= max_retries:
            try:
                sparql = SPARQLWrapper(endpoint_url)
                sparql.setTimeout(self.config["timeout"])
                sparql.setQuery(query)
                sparql.setReturnFormat(JSON)
                
                # Set user agent
                sparql.addCustomHttpHeader("User-Agent", self.config["user_agent"])
                
                results = sparql.query().convert()
                return results
                
            except TimeoutError:
                return {
                    "error": f"Query timeout after {self.config['timeout']} seconds",
                    "query": query,
                    "endpoint": endpoint_url
                }
            except Exception as e:
                retries += 1
                if retries > max_retries:
                    return {
                        "error": f"Query failed after {max_retries} retries: {str(e)}",
                        "query": query,
                        "endpoint": endpoint_url
                    }
                
                # Wait before retry
                time.sleep(self.config["retry_delay"] * retries)
        
        return {"results": {"bindings": []}}
    
    def search_terms_in_ontology(self, 
                                terms: List[str], 
                                ontology: str) -> Dict[str, Dict[str, Any]]:
        """
        Search for multiple terms in an ontology.
        
        Args:
            terms: List of terms to search for
            ontology: Target ontology name
            
        Returns:
            Dictionary with search results for each term
        """
        endpoint_url = self.get_ontology_endpoint(ontology)
        if not endpoint_url:
            return {term: {"found": False, "error": "Unknown ontology"} for term in terms}
        
        results = {}
        
        for term in terms:
            query = self.build_term_search_query(term, ontology)
            query_results = self.execute_query(query, endpoint_url)
            
            if "error" in query_results:
                results[term] = {
                    "found": False,
                    "error": query_results["error"]
                }
            else:
                bindings = query_results.get("results", {}).get("bindings", [])
                if bindings:
                    results[term] = {
                        "found": True,
                        "uri": bindings[0].get("term", {}).get("value"),
                        "label": bindings[0].get("label", {}).get("value"),
                        "definition": bindings[0].get("definition", {}).get("value"),
                        "matches": len(bindings)
                    }
                else:
                    results[term] = {"found": False}
        
        return results

    def get_term_hierarchy(self,
                          term_uri: str,
                          ontology: str) -> Dict[str, Any]:
        """
        Get hierarchy information for a term.

        Args:
            term_uri: URI of the term
            ontology: Target ontology name

        Returns:
            Hierarchy information dictionary
        """
        endpoint_url = self.get_ontology_endpoint(ontology)
        if not endpoint_url:
            return {"error": "Unknown ontology"}

        query = self.build_hierarchy_query(term_uri, ontology)
        results = self.execute_query(query, endpoint_url)

        if "error" in results:
            return results

        hierarchy = {"parents": [], "children": []}
        bindings = results.get("results", {}).get("bindings", [])

        for binding in bindings:
            relation = binding.get("relation", {}).get("value", "unknown")
            related_uri = binding.get("related", {}).get("value")
            label = binding.get("label", {}).get("value")

            if relation == "parent":
                hierarchy["parents"].append({"uri": related_uri, "label": label})
            elif relation == "child":
                hierarchy["children"].append({"uri": related_uri, "label": label})

        return hierarchy

    def get_term_properties(self,
                           term_uri: str,
                           ontology: str) -> Dict[str, Any]:
        """
        Get properties for a term.

        Args:
            term_uri: URI of the term
            ontology: Target ontology name

        Returns:
            Properties dictionary
        """
        endpoint_url = self.get_ontology_endpoint(ontology)
        if not endpoint_url:
            return {"error": "Unknown ontology"}

        query = self.build_property_query(term_uri, ontology)
        results = self.execute_query(query, endpoint_url)

        if "error" in results:
            return results

        properties = {}
        bindings = results.get("results", {}).get("bindings", [])

        for binding in bindings:
            prop = binding.get("property", {}).get("value")
            value = binding.get("value", {}).get("value")

            if prop and value:
                if prop not in properties:
                    properties[prop] = []
                properties[prop].append(value)

        return properties

    def validate_sparql_query(self, query: str) -> bool:
        """
        Validate SPARQL query syntax.

        Args:
            query: SPARQL query string

        Returns:
            True if query is valid, False otherwise
        """
        # Basic validation - check for required keywords
        query_upper = query.upper()

        # Must have SELECT or ASK or CONSTRUCT or DESCRIBE
        if not any(keyword in query_upper for keyword in ["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"]):
            return False

        # Must have WHERE clause for SELECT queries
        if "SELECT" in query_upper and "WHERE" not in query_upper:
            return False

        # Check for balanced braces
        open_braces = query.count("{")
        close_braces = query.count("}")
        if open_braces != close_braces:
            return False

        # Basic syntax check - no obvious syntax errors
        invalid_patterns = [
            r'\s+\.\s*\.',  # Double dots
            r'\{\s*\}',     # Empty braces
            r'[^a-zA-Z0-9_:]\s*\?[^a-zA-Z0-9_]',  # Invalid variable names
        ]

        for pattern in invalid_patterns:
            if re.search(pattern, query):
                return False

        return True

    def get_ontology_endpoint(self, ontology: str) -> Optional[str]:
        """
        Get SPARQL endpoint URL for an ontology.

        Args:
            ontology: Ontology name

        Returns:
            Endpoint URL or None if unknown
        """
        return self.ontology_endpoints.get(ontology)

    def format_query_results(self, raw_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format raw SPARQL query results into a more usable format.

        Args:
            raw_results: Raw results from SPARQL query

        Returns:
            Formatted results list
        """
        if "error" in raw_results:
            return []

        bindings = raw_results.get("results", {}).get("bindings", [])
        formatted_results = []

        for binding in bindings:
            result_item = {}
            for var, value_info in binding.items():
                result_item[var] = value_info.get("value")
            formatted_results.append(result_item)

        return formatted_results

    def build_federated_query(self, term: str, endpoints: List[str]) -> str:
        """
        Build a federated SPARQL query across multiple endpoints.

        Args:
            term: Term to search for
            endpoints: List of SPARQL endpoint URLs

        Returns:
            Federated SPARQL query string
        """
        prefixes = self._build_prefixes("Generic")

        service_clauses = []
        for endpoint in endpoints:
            service_clause = f"""
            SERVICE <{endpoint}> {{
                ?term rdfs:label ?label .
                FILTER(CONTAINS(LCASE(str(?label)), LCASE("{term}")))
            }}
            """
            service_clauses.append(service_clause)

        union_pattern = " UNION ".join([f"{{ {clause} }}" for clause in service_clauses])

        query = f"""
        {prefixes}

        SELECT DISTINCT ?term ?label WHERE {{
            {union_pattern}
        }}
        ORDER BY ?label
        LIMIT 100
        """

        return query.strip()

    def cached_execute_query(self, query: str, endpoint_url: str) -> Dict[str, Any]:
        """
        Execute query with caching support.

        Args:
            query: SPARQL query string
            endpoint_url: SPARQL endpoint URL

        Returns:
            Query results dictionary
        """
        if self.query_cache is None:
            return self.execute_query(query, endpoint_url)

        # Create cache key
        cache_key = hashlib.md5(f"{query}_{endpoint_url}".encode()).hexdigest()

        # Check cache
        if cache_key in self.query_cache:
            cache_entry = self.query_cache[cache_key]
            if time.time() - cache_entry["timestamp"] < self.config["cache_ttl"]:
                return cache_entry["results"]

        # Execute query and cache results
        results = self.execute_query(query, endpoint_url)
        self.query_cache[cache_key] = {
            "results": results,
            "timestamp": time.time()
        }

        return results

    def export_query_results(self, results: Dict[str, Any], output_path: str) -> None:
        """
        Export query results to a file.

        Args:
            results: Query results to export
            output_path: Path to output file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Exported query results to {output_path}")

    def _build_prefixes(self, ontology: str) -> str:
        """
        Build PREFIX declarations for SPARQL queries.

        Args:
            ontology: Target ontology name

        Returns:
            PREFIX declarations string
        """
        prefixes = []

        # Always include common prefixes
        for prefix, uri in self.common_prefixes.items():
            prefixes.append(f"PREFIX {prefix}: <{uri}>")

        return "\n".join(prefixes)
