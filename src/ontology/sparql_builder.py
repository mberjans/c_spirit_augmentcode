"""
SPARQL Builder for Ontology Trimming Operations.

This module provides specialized SPARQL query building functionality
specifically designed for ontology trimming and term validation operations.
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from loguru import logger


@dataclass
class TermValidationQuery:
    """Data class for term validation query results."""
    term: str
    query: str
    ontology: str
    query_type: str


class SPARQLBuilder:
    """
    Specialized SPARQL query builder for ontology trimming operations.
    
    This class focuses on building queries specifically needed for:
    - Term frequency analysis
    - Cross-reference validation
    - Hierarchical relationship discovery
    - Citation impact assessment
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the SPARQL builder.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # Default configuration
        self.default_config = {
            "default_limit": 1000,
            "include_deprecated": False,
            "include_obsolete": False,
            "min_confidence": 0.7
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
        
        # Common prefixes for ontology trimming queries
        self.prefixes = {
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "owl": "http://www.w3.org/2002/07/owl#",
            "obo": "http://purl.obolibrary.org/obo/",
            "po": "http://purl.obolibrary.org/obo/PO_",
            "go": "http://purl.obolibrary.org/obo/GO_",
            "chebi": "http://purl.obolibrary.org/obo/CHEBI_",
            "ncbitaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
            "peco": "http://purl.obolibrary.org/obo/PECO_"
        }
    
    def build_term_frequency_query(self,
                                 terms: List[str],
                                 ontology_prefix: str = "po") -> str:
        """
        Build a SPARQL query to analyze term frequency in ontology.

        Args:
            terms: List of terms to analyze
            ontology_prefix: Ontology prefix to use

        Returns:
            SPARQL query string for term frequency analysis
        """
        prefixes_str = self._build_prefixes()

        # Pre-compute lowercase terms for better performance
        lowercase_terms = [term.lower() for term in terms]

        # Create optimized FILTER clause using VALUES for better performance
        if len(terms) == 1:
            filter_clause = f'CONTAINS(LCASE(str(?label)), "{lowercase_terms[0]}")'
        else:
            values_clause = " ".join([f'"{term}"' for term in lowercase_terms])
            filter_clause = f"""
            VALUES ?search_term {{ {values_clause} }}
            FILTER(CONTAINS(LCASE(str(?label)), ?search_term))
            """

        # Get ontology prefix URI for filtering
        ontology_uri = self.prefixes.get(ontology_prefix, ontology_prefix)

        query = f"""
        {prefixes_str}

        SELECT ?term ?label ?definition (COALESCE(?usage_count, 0) AS ?final_usage_count) WHERE {{
            # Filter by ontology first for better performance
            ?term rdfs:label ?label .
            FILTER(STRSTARTS(str(?term), "{ontology_uri}"))

            # Apply term filter early
            {filter_clause}

            # Filter out deprecated terms early
            FILTER NOT EXISTS {{ ?term owl:deprecated "true"^^xsd:boolean }}

            # Get definition (prefer IAO definition over comment)
            OPTIONAL {{
                {{ ?term obo:IAO_0000115 ?definition }}
                UNION
                {{ ?term rdfs:comment ?definition . FILTER NOT EXISTS {{ ?term obo:IAO_0000115 ?def2 }} }}
            }}

            # Optimized usage count with separate optional block
            OPTIONAL {{
                SELECT ?term (COUNT(DISTINCT ?relation) AS ?usage_count) WHERE {{
                    {{ ?term ?relation ?object }} UNION {{ ?subject ?relation ?term }}
                    FILTER(?relation NOT IN (rdf:type, rdfs:label, rdfs:comment, obo:IAO_0000115))
                }}
                GROUP BY ?term
            }}
        }}
        ORDER BY DESC(?final_usage_count) ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()
    
    def build_cross_reference_query(self, 
                                  term_uri: str, 
                                  target_ontologies: List[str]) -> str:
        """
        Build a SPARQL query for cross-reference validation.
        
        Args:
            term_uri: URI of the term to validate
            target_ontologies: List of target ontology prefixes
            
        Returns:
            SPARQL query string for cross-reference validation
        """
        prefixes_str = self._build_prefixes()
        
        # Build UNION clauses for different ontologies
        union_clauses = []
        for ontology in target_ontologies:
            union_clause = f"""
            {{
                ?equivalent_term rdfs:label ?equiv_label .
                ?equivalent_term rdfs:comment ?equiv_definition .
                FILTER(STRSTARTS(str(?equivalent_term), "{self.prefixes.get(ontology, ontology)}"))
                FILTER(CONTAINS(LCASE(str(?equiv_label)), LCASE(str(?original_label))))
                BIND("{ontology}" AS ?source_ontology)
            }}
            """
            union_clauses.append(union_clause)
        
        union_pattern = " UNION ".join(union_clauses)
        
        query = f"""
        {prefixes_str}
        
        SELECT ?original_label ?equivalent_term ?equiv_label ?equiv_definition ?source_ontology WHERE {{
            <{term_uri}> rdfs:label ?original_label .
            
            {union_pattern}
        }}
        ORDER BY ?source_ontology ?equiv_label
        LIMIT {self.config['default_limit']}
        """
        
        return query.strip()
    
    def build_hierarchical_analysis_query(self,
                                        term_uri: str,
                                        max_depth: int = 3) -> str:
        """
        Build a SPARQL query for hierarchical relationship analysis.

        Args:
            term_uri: URI of the term to analyze
            max_depth: Maximum depth for hierarchy traversal

        Returns:
            SPARQL query string for hierarchical analysis
        """
        prefixes_str = self._build_prefixes()

        # Optimized query using property paths with depth limits
        query = f"""
        {prefixes_str}

        SELECT ?term ?label ?relation_type ?depth ?path WHERE {{
            {{
                # Optimized parents query with depth calculation
                <{term_uri}> rdfs:subClassOf{{1,{max_depth}}} ?term .
                ?term rdfs:label ?label .
                BIND("parent" AS ?relation_type)

                # More efficient depth calculation using property path
                {{
                    SELECT ?term (COUNT(?step) AS ?depth) WHERE {{
                        <{term_uri}> rdfs:subClassOf/rdfs:subClassOf* ?step .
                        ?step rdfs:subClassOf* ?term .
                        FILTER(?step != <{term_uri}>)
                    }}
                    GROUP BY ?term
                }}
            }} UNION {{
                # Optimized children query with depth calculation
                ?term rdfs:subClassOf{{1,{max_depth}}} <{term_uri}> .
                ?term rdfs:label ?label .
                BIND("child" AS ?relation_type)

                # More efficient depth calculation using property path
                {{
                    SELECT ?term (COUNT(?step) AS ?depth) WHERE {{
                        ?term rdfs:subClassOf/rdfs:subClassOf* ?step .
                        ?step rdfs:subClassOf* <{term_uri}> .
                        FILTER(?step != ?term)
                    }}
                    GROUP BY ?term
                }}
            }}

            # Optimized path string construction
            BIND(CONCAT(str(?depth), ":", ?relation_type) AS ?path)

            # Filter out the original term itself
            FILTER(?term != <{term_uri}>)
        }}
        ORDER BY ?relation_type ?depth ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()
    
    def build_citation_impact_query(self,
                                   terms: List[str],
                                   include_synonyms: bool = True) -> str:
        """
        Build a SPARQL query to assess citation impact of terms.

        Args:
            terms: List of terms to analyze
            include_synonyms: Whether to include synonym analysis

        Returns:
            SPARQL query string for citation impact analysis
        """
        prefixes_str = self._build_prefixes()

        # Pre-compute lowercase terms for better performance
        lowercase_terms = [term.lower() for term in terms]

        # Optimized term filtering using VALUES
        if len(terms) == 1:
            term_filter = f'CONTAINS(LCASE(str(?label)), "{lowercase_terms[0]}")'
            if include_synonyms:
                synonym_filter = f'CONTAINS(LCASE(str(?synonym)), "{lowercase_terms[0]}")'
        else:
            values_clause = " ".join([f'"{term}"' for term in lowercase_terms])
            term_filter = f"""
            VALUES ?search_term {{ {values_clause} }}
            FILTER(CONTAINS(LCASE(str(?label)), ?search_term))
            """
            if include_synonyms:
                synonym_filter = f"""
                VALUES ?search_term_syn {{ {values_clause} }}
                FILTER(CONTAINS(LCASE(str(?synonym)), ?search_term_syn))
                """

        # Build optimized SELECT and WHERE clauses
        if include_synonyms:
            select_clause = "SELECT ?term ?label ?synonym (COALESCE(?citation_count, 0) AS ?final_citation_count) (COALESCE(?impact_score, 0) AS ?final_impact_score)"
            synonym_clauses = f"""
            OPTIONAL {{
                {{ ?term obo:hasExactSynonym ?synonym }}
                UNION
                {{ ?term obo:hasRelatedSynonym ?synonym }}
                {synonym_filter if len(terms) > 1 else f'FILTER({synonym_filter})'}
            }}"""
        else:
            select_clause = "SELECT ?term ?label (COALESCE(?citation_count, 0) AS ?final_citation_count) (COALESCE(?impact_score, 0) AS ?final_impact_score)"
            synonym_clauses = ""

        query = f"""
        {prefixes_str}

        {select_clause} WHERE {{
            ?term rdfs:label ?label .

            # Apply term filter early for performance
            {term_filter if len(terms) > 1 else f'FILTER({term_filter})'}
            {synonym_clauses}

            # Optimized citation count with better filtering
            OPTIONAL {{
                SELECT ?term (COUNT(DISTINCT ?annotation) AS ?citation_count) WHERE {{
                    ?annotation ?property ?term .
                    VALUES ?property {{ obo:RO_0002612 obo:RO_0002614 }}  # evidence codes
                }}
                GROUP BY ?term
            }}

            # Optimized impact score calculation
            OPTIONAL {{
                SELECT ?term (COUNT(DISTINCT ?related) AS ?impact_score) WHERE {{
                    {{ ?term ?relation ?related }} UNION {{ ?related ?relation ?term }}
                    FILTER(?relation NOT IN (rdf:type, rdfs:label, rdfs:comment, obo:IAO_0000115))
                }}
                GROUP BY ?term
            }}
        }}
        ORDER BY DESC(?final_impact_score) DESC(?final_citation_count) ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()
    
    def build_term_validation_queries(self, 
                                    terms: List[str], 
                                    ontologies: List[str]) -> List[TermValidationQuery]:
        """
        Build comprehensive validation queries for a list of terms.
        
        Args:
            terms: List of terms to validate
            ontologies: List of ontology prefixes to check against
            
        Returns:
            List of TermValidationQuery objects
        """
        queries = []
        
        for term in terms:
            # Frequency analysis query
            freq_query = self.build_term_frequency_query([term])
            queries.append(TermValidationQuery(
                term=term,
                query=freq_query,
                ontology="combined",
                query_type="frequency_analysis"
            ))
            
            # Cross-reference validation for each ontology
            for ontology in ontologies:
                # Create a dummy URI for cross-reference (in real scenario, this would be actual term URI)
                term_uri = f"http://example.org/term/{term.replace(' ', '_')}"
                cross_ref_query = self.build_cross_reference_query(term_uri, [ontology])
                queries.append(TermValidationQuery(
                    term=term,
                    query=cross_ref_query,
                    ontology=ontology,
                    query_type="cross_reference"
                ))
        
        return queries
    
    def _build_prefixes(self) -> str:
        """
        Build PREFIX declarations for SPARQL queries.
        
        Returns:
            PREFIX declarations string
        """
        prefixes = []
        for prefix, uri in self.prefixes.items():
            prefixes.append(f"PREFIX {prefix}: <{uri}>")
        
        return "\n".join(prefixes)

    def build_term_similarity_query(self,
                                  source_term: str,
                                  target_ontology: str = "po",
                                  similarity_threshold: float = 0.8) -> str:
        """
        Build a SPARQL query to find similar terms in an ontology.

        Args:
            source_term: Term to find similarities for
            target_ontology: Target ontology prefix
            similarity_threshold: Minimum similarity threshold

        Returns:
            SPARQL query string for similarity analysis
        """
        prefixes_str = self._build_prefixes()

        query = f"""
        {prefixes_str}

        SELECT ?term ?label ?similarity_score ?match_type WHERE {{
            ?term rdfs:label ?label .

            # Exact match (highest score)
            {{
                FILTER(LCASE(str(?label)) = LCASE("{source_term}"))
                BIND(1.0 AS ?similarity_score)
                BIND("exact" AS ?match_type)
            }} UNION {{
                # Substring match
                FILTER(CONTAINS(LCASE(str(?label)), LCASE("{source_term}")))
                FILTER(LCASE(str(?label)) != LCASE("{source_term}"))
                BIND(0.9 AS ?similarity_score)
                BIND("substring" AS ?match_type)
            }} UNION {{
                # Word overlap match
                FILTER(REGEX(LCASE(str(?label)), "\\\\b" + LCASE("{source_term}") + "\\\\b"))
                FILTER(!CONTAINS(LCASE(str(?label)), LCASE("{source_term}")))
                BIND(0.8 AS ?similarity_score)
                BIND("word_overlap" AS ?match_type)
            }}

            FILTER(?similarity_score >= {similarity_threshold})
            FILTER(STRSTARTS(str(?term), "{self.prefixes.get(target_ontology, target_ontology)}"))
        }}
        ORDER BY DESC(?similarity_score) ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()

    def build_term_usage_statistics_query(self,
                                        ontology_prefix: str = "po") -> str:
        """
        Build a SPARQL query to get usage statistics for terms.

        Args:
            ontology_prefix: Ontology prefix to analyze

        Returns:
            SPARQL query string for usage statistics
        """
        prefixes_str = self._build_prefixes()

        query = f"""
        {prefixes_str}

        SELECT ?term ?label ?parent_count ?child_count ?total_relations ?usage_score WHERE {{
            ?term rdfs:label ?label .
            FILTER(STRSTARTS(str(?term), "{self.prefixes.get(ontology_prefix, ontology_prefix)}"))

            # Count parent relationships
            OPTIONAL {{
                SELECT ?term (COUNT(?parent) AS ?parent_count) WHERE {{
                    ?term rdfs:subClassOf ?parent .
                    FILTER(?parent != owl:Thing)
                }}
                GROUP BY ?term
            }}

            # Count child relationships
            OPTIONAL {{
                SELECT ?term (COUNT(?child) AS ?child_count) WHERE {{
                    ?child rdfs:subClassOf ?term .
                }}
                GROUP BY ?term
            }}

            # Count total relationships
            OPTIONAL {{
                SELECT ?term (COUNT(?relation) AS ?total_relations) WHERE {{
                    {{ ?term ?relation ?object }} UNION {{ ?subject ?relation ?term }}
                    FILTER(?relation != rdf:type)
                    FILTER(?relation != rdfs:label)
                }}
                GROUP BY ?term
            }}

            # Calculate usage score
            BIND(COALESCE(?parent_count, 0) + COALESCE(?child_count, 0) + COALESCE(?total_relations, 0) AS ?usage_score)
        }}
        ORDER BY DESC(?usage_score) ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()

    def build_deprecated_terms_query(self,
                                   ontology_prefix: str = "po") -> str:
        """
        Build a SPARQL query to identify deprecated or obsolete terms.

        Args:
            ontology_prefix: Ontology prefix to check

        Returns:
            SPARQL query string for deprecated terms
        """
        prefixes_str = self._build_prefixes()

        query = f"""
        {prefixes_str}

        SELECT ?term ?label ?deprecated ?obsolete ?replacement WHERE {{
            ?term rdfs:label ?label .
            FILTER(STRSTARTS(str(?term), "{self.prefixes.get(ontology_prefix, ontology_prefix)}"))

            # Check for deprecated status
            OPTIONAL {{ ?term owl:deprecated ?deprecated }}

            # Check for obsolete status
            OPTIONAL {{ ?term obo:IAO_0000231 ?obsolete_status }}
            BIND(BOUND(?obsolete_status) AS ?obsolete)

            # Look for replacement terms
            OPTIONAL {{ ?term obo:IAO_0100001 ?replacement }}

            FILTER(?deprecated = "true"^^xsd:boolean || ?obsolete = true)
        }}
        ORDER BY ?label
        LIMIT {self.config['default_limit']}
        """

        return query.strip()

    def validate_query_syntax(self, query: str) -> Dict[str, Any]:
        """
        Validate SPARQL query syntax and structure.

        Args:
            query: SPARQL query string to validate

        Returns:
            Validation result dictionary
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Basic syntax checks
        query_upper = query.upper()

        # Check for required keywords
        if not any(keyword in query_upper for keyword in ["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"]):
            validation_result["valid"] = False
            validation_result["errors"].append("Query must contain SELECT, ASK, CONSTRUCT, or DESCRIBE")

        # Check for WHERE clause in SELECT queries
        if "SELECT" in query_upper and "WHERE" not in query_upper:
            validation_result["valid"] = False
            validation_result["errors"].append("SELECT queries must contain WHERE clause")

        # Check for balanced braces
        open_braces = query.count("{")
        close_braces = query.count("}")
        if open_braces != close_braces:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Unbalanced braces: {open_braces} open, {close_braces} close")

        # Check for proper PREFIX declarations
        if "PREFIX" not in query and any(prefix in query for prefix in self.prefixes.keys()):
            validation_result["warnings"].append("Query uses prefixes but lacks PREFIX declarations")

        # Check for potential performance issues
        if "LIMIT" not in query_upper and "SELECT" in query_upper:
            validation_result["warnings"].append("Query lacks LIMIT clause, may return large result set")

        return validation_result

    def optimize_query_performance(self, query: str) -> str:
        """
        Apply performance optimizations to a SPARQL query.

        Args:
            query: Original SPARQL query string

        Returns:
            Optimized SPARQL query string
        """
        optimized_query = query

        # Add query hints for better performance
        if "SELECT" in query.upper() and "LIMIT" not in query.upper():
            optimized_query += f"\nLIMIT {self.config['default_limit']}"

        # Optimize FILTER placement - move early in query
        lines = optimized_query.split('\n')
        filter_lines = [line for line in lines if 'FILTER(' in line and 'OPTIONAL' not in line]
        non_filter_lines = [line for line in lines if line not in filter_lines]

        # Insert filters after WHERE clause for better performance
        optimized_lines = []
        where_found = False
        for line in non_filter_lines:
            optimized_lines.append(line)
            if 'WHERE {' in line and not where_found:
                where_found = True
                # Add filters right after WHERE clause
                for filter_line in filter_lines:
                    if filter_line.strip():
                        optimized_lines.append(filter_line)

        # Remove duplicate filter lines from original positions
        final_lines = []
        for line in optimized_lines:
            if line in filter_lines and any(f in final_lines for f in filter_lines):
                continue  # Skip duplicate filter
            final_lines.append(line)

        return '\n'.join(final_lines)

    def add_query_hints(self, query: str, hints: Dict[str, Any] = None) -> str:
        """
        Add performance hints to SPARQL queries.

        Args:
            query: Original query string
            hints: Dictionary of performance hints

        Returns:
            Query with performance hints added
        """
        if hints is None:
            hints = {
                'use_index': True,
                'parallel_execution': True,
                'result_caching': True
            }

        # Add query hints as comments for SPARQL engines that support them
        hint_comments = []

        if hints.get('use_index', False):
            hint_comments.append("# HINT: USE_INDEX")

        if hints.get('parallel_execution', False):
            hint_comments.append("# HINT: PARALLEL_EXECUTION")

        if hints.get('result_caching', False):
            hint_comments.append("# HINT: ENABLE_CACHING")

        if hint_comments:
            hints_str = '\n'.join(hint_comments)
            # Insert hints after PREFIX declarations
            lines = query.split('\n')
            prefix_end = 0
            for i, line in enumerate(lines):
                if not line.strip().startswith('PREFIX') and line.strip():
                    prefix_end = i
                    break

            lines.insert(prefix_end, hints_str)
            return '\n'.join(lines)

        return query
