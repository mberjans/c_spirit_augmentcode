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
        
        # Create FILTER clause for terms
        term_filters = []
        for term in terms:
            term_filters.append(f'CONTAINS(LCASE(str(?label)), LCASE("{term}"))')
        
        filter_clause = " || ".join(term_filters)
        
        query = f"""
        {prefixes_str}
        
        SELECT ?term ?label ?definition ?usage_count WHERE {{
            ?term rdfs:label ?label .
            OPTIONAL {{ ?term rdfs:comment ?definition }}
            OPTIONAL {{ ?term obo:IAO_0000115 ?definition }}
            
            # Count usage in relationships
            {{
                SELECT ?term (COUNT(?relation) AS ?usage_count) WHERE {{
                    {{ ?term ?relation ?object }} UNION {{ ?subject ?relation ?term }}
                    FILTER(?relation != rdf:type)
                }}
                GROUP BY ?term
            }}
            
            FILTER({filter_clause})
            FILTER(!BOUND(?deprecated) || ?deprecated != "true"^^xsd:boolean)
        }}
        ORDER BY DESC(?usage_count) ?label
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
        
        query = f"""
        {prefixes_str}
        
        SELECT ?term ?label ?relation_type ?depth ?path WHERE {{
            {{
                # Parents (ancestors)
                <{term_uri}> rdfs:subClassOf+ ?term .
                ?term rdfs:label ?label .
                BIND("parent" AS ?relation_type)
                
                # Calculate depth
                {{
                    SELECT ?term (COUNT(?intermediate) AS ?depth) WHERE {{
                        <{term_uri}> rdfs:subClassOf+ ?intermediate .
                        ?intermediate rdfs:subClassOf* ?term .
                    }}
                    GROUP BY ?term
                }}
                
                FILTER(?depth <= {max_depth})
            }} UNION {{
                # Children (descendants)
                ?term rdfs:subClassOf+ <{term_uri}> .
                ?term rdfs:label ?label .
                BIND("child" AS ?relation_type)
                
                # Calculate depth
                {{
                    SELECT ?term (COUNT(?intermediate) AS ?depth) WHERE {{
                        ?term rdfs:subClassOf+ ?intermediate .
                        ?intermediate rdfs:subClassOf* <{term_uri}> .
                    }}
                    GROUP BY ?term
                }}
                
                FILTER(?depth <= {max_depth})
            }}
            
            # Build path string for visualization
            BIND(CONCAT(str(?depth), ":", str(?relation_type)) AS ?path)
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
        
        # Create term filter
        term_filters = []
        for term in terms:
            term_filters.append(f'CONTAINS(LCASE(str(?label)), LCASE("{term}"))')
            if include_synonyms:
                term_filters.append(f'CONTAINS(LCASE(str(?synonym)), LCASE("{term}"))')

        filter_clause = " || ".join(term_filters)

        # Build SELECT clause and OPTIONAL clauses based on include_synonyms
        if include_synonyms:
            select_clause = "SELECT ?term ?label ?synonym ?citation_count ?impact_score"
            synonym_clauses = """
            OPTIONAL { ?term obo:hasExactSynonym ?synonym }
            OPTIONAL { ?term obo:hasRelatedSynonym ?synonym }"""
        else:
            select_clause = "SELECT ?term ?label ?citation_count ?impact_score"
            synonym_clauses = ""

        query = f"""
        {prefixes_str}

        {select_clause} WHERE {{
            ?term rdfs:label ?label .{synonym_clauses}
            
            # Citation count (approximated by usage in annotations)
            OPTIONAL {{
                SELECT ?term (COUNT(?annotation) AS ?citation_count) WHERE {{
                    ?annotation ?property ?term .
                    FILTER(?property IN (obo:RO_0002612, obo:RO_0002614))  # evidence codes
                }}
                GROUP BY ?term
            }}
            
            # Impact score based on relationships and usage
            OPTIONAL {{
                SELECT ?term (COUNT(DISTINCT ?related) AS ?impact_score) WHERE {{
                    {{ ?term ?relation ?related }} UNION {{ ?related ?relation ?term }}
                    FILTER(?relation != rdf:type)
                    FILTER(?relation != rdfs:label)
                }}
                GROUP BY ?term
            }}
            
            FILTER({filter_clause})
        }}
        ORDER BY DESC(?impact_score) DESC(?citation_count) ?label
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
