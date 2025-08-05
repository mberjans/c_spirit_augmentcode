# Ontology Trimming and Restructuring Documentation

## Overview

This document provides comprehensive documentation for the automated ontology trimming and restructuring system implemented as part of the Plant Metabolite Knowledge Extraction System. The system reduces anatomical terms from 2008 to approximately 293 manageable terms through systematic analysis and automated validation.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Methodology](#methodology)
3. [Implementation Components](#implementation-components)
4. [Usage Guide](#usage-guide)
5. [Validation and Quality Assurance](#validation-and-quality-assurance)
6. [Performance Optimization](#performance-optimization)
7. [Output and Reporting](#output-and-reporting)
8. [Troubleshooting](#troubleshooting)

## System Architecture

The ontology trimming system consists of several interconnected components:

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Corpus Analyzer  │    │   Term Clusterer    │    │ Automated Validator │
│                     │───▶│                     │───▶│                     │
│ - Frequency Analysis│    │ - Hierarchical      │    │ - Cross-reference   │
│ - Citation Impact   │    │   Clustering        │    │   Validation        │
│ - Usage Statistics  │    │ - Similarity        │    │ - Multi-metric      │
└─────────────────────┘    │   Grouping          │    │   Scoring           │
                           └─────────────────────┘    └─────────────────────┘
                                     │                           │
                                     ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  SPARQL Builder     │    │ SPARQL Query Builder│    │ Justification       │
│                     │◀───│                     │───▶│ Generator           │
│ - Query Optimization│    │ - Endpoint          │    │                     │
│ - Performance Hints │    │   Integration       │    │ - Report Generation │
│ - Validation        │    │ - Error Handling    │    │ - Documentation     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

## Methodology

### 1. Literature Corpus Analysis

The system analyzes term usage frequency in the target literature corpus using multiple metrics:

- **Term Frequency Analysis**: Counts occurrences of anatomical terms in scientific literature
- **Citation Impact Scoring**: Evaluates academic relevance based on citation patterns
- **Hierarchical Weighting**: Applies weights based on ontological hierarchy depth
- **Temporal Analysis**: Considers publication dates and recent usage trends

### 2. Hierarchical Clustering

Terms are grouped using advanced clustering algorithms:

- **Similarity Metrics**: String similarity, semantic similarity, and structural similarity
- **Clustering Algorithms**: Hierarchical clustering with configurable distance metrics
- **Validation**: Cluster quality assessment using silhouette analysis
- **Optimization**: Automated parameter tuning for optimal cluster formation

### 3. Automated Validation

Multi-stage validation process ensures quality:

- **Cross-reference Validation**: Verification against established ontologies (Plant Ontology, Gene Ontology, ChEBI)
- **Consistency Checking**: Logical consistency validation using reasoning engines
- **Completeness Assessment**: Coverage analysis for target domain
- **Quality Scoring**: Multi-metric scoring combining frequency, impact, and validation scores

## Implementation Components

### Core Classes

#### 1. CorpusAnalyzer (`src/ontology/corpus_analyzer.py`)

Analyzes term frequency and citation impact in literature corpus.

**Key Methods:**
- `analyze_term_frequency(terms, corpus_path)`: Analyzes frequency of terms in corpus
- `calculate_citation_impact(terms, citation_data)`: Calculates citation-based impact scores
- `generate_usage_statistics(terms)`: Generates comprehensive usage statistics

**Configuration Options:**
- `min_frequency_threshold`: Minimum frequency for term inclusion (default: 5)
- `citation_weight`: Weight for citation impact in scoring (default: 0.3)
- `temporal_decay`: Decay factor for older publications (default: 0.95)

#### 2. TermClusterer (`src/ontology/term_clusterer.py`)

Performs hierarchical clustering of similar terms.

**Key Methods:**
- `cluster_similar_terms(terms, similarity_threshold)`: Groups similar terms
- `calculate_similarity_matrix(terms)`: Computes pairwise similarity
- `validate_clusters(clusters)`: Assesses cluster quality

**Clustering Parameters:**
- `similarity_threshold`: Minimum similarity for clustering (default: 0.8)
- `max_cluster_size`: Maximum terms per cluster (default: 10)
- `linkage_method`: Clustering linkage method (default: 'ward')

#### 3. AutomatedValidator (`src/ontology/automated_validator.py`)

Validates term selection using multiple criteria.

**Key Methods:**
- `cross_reference_validation(terms, ontologies)`: Cross-validates against reference ontologies
- `calculate_validation_score(term, validation_results)`: Computes validation scores
- `generate_validation_report(results)`: Creates detailed validation reports

**Validation Criteria:**
- `cross_reference_weight`: Weight for cross-reference validation (default: 0.4)
- `consistency_weight`: Weight for logical consistency (default: 0.3)
- `completeness_weight`: Weight for domain completeness (default: 0.3)

### SPARQL Integration

#### 4. SPARQLBuilder (`src/ontology/sparql_builder.py`)

Builds optimized SPARQL queries for ontology operations.

**Key Features:**
- Performance-optimized query construction
- Support for multiple ontology endpoints
- Automated query validation and optimization
- Caching for improved performance

#### 5. SPARQLQueryBuilder (`src/ontology/sparql_query_builder.py`)

Executes SPARQL queries with robust error handling.

**Key Features:**
- Retry logic with exponential backoff
- Timeout handling and connection management
- Result caching and optimization
- Support for federated queries

### Documentation and Reporting

#### 6. JustificationGenerator (`src/ontology/justification_generator.py`)

Generates comprehensive justification documents.

**Key Features:**
- Automated report generation in multiple formats (JSON, Markdown)
- Statistical analysis and visualization data
- Methodology documentation
- Recommendations and quality metrics

## Usage Guide

### Basic Usage

```python
from src.ontology.corpus_analyzer import CorpusAnalyzer
from src.ontology.term_clusterer import TermClusterer
from src.ontology.automated_validator import AutomatedValidator
from src.ontology.justification_generator import JustificationGenerator

# Initialize components
analyzer = CorpusAnalyzer()
clusterer = TermClusterer()
validator = AutomatedValidator()
generator = JustificationGenerator()

# Analyze term frequency
terms = ['leaf', 'stem', 'root', 'flower']
frequency_results = analyzer.analyze_term_frequency(terms, 'path/to/corpus')

# Cluster similar terms
clusters = clusterer.cluster_similar_terms(terms, similarity_threshold=0.8)

# Validate term selection
validation_results = validator.cross_reference_validation(terms, ['po', 'go', 'chebi'])

# Generate justification report
selected_terms = [term for term in validation_results if term['final_score'] >= 0.7]
rejected_terms = [term for term in validation_results if term['final_score'] < 0.7]
report = generator.generate_selection_report(selected_terms, rejected_terms)

# Save report
generator.save_report_to_file(report, 'output/selection_report.json', format='json')
```

### Advanced Configuration

```python
# Custom configuration for corpus analysis
analyzer_config = {
    'min_frequency_threshold': 10,
    'citation_weight': 0.4,
    'temporal_decay': 0.9,
    'include_synonyms': True
}
analyzer = CorpusAnalyzer(analyzer_config)

# Custom clustering parameters
clusterer_config = {
    'similarity_threshold': 0.85,
    'max_cluster_size': 8,
    'linkage_method': 'complete',
    'distance_metric': 'cosine'
}
clusterer = TermClusterer(clusterer_config)

# Custom validation settings
validator_config = {
    'cross_reference_weight': 0.5,
    'consistency_weight': 0.3,
    'completeness_weight': 0.2,
    'min_validation_score': 0.8
}
validator = AutomatedValidator(validator_config)
```

## Validation and Quality Assurance

### Validation Metrics

The system uses multiple validation metrics to ensure quality:

1. **Cross-reference Validation Score**: Measures agreement with established ontologies
2. **Frequency-based Relevance**: Assesses term importance based on literature usage
3. **Citation Impact Score**: Evaluates academic significance
4. **Consistency Score**: Measures logical consistency within the ontology
5. **Completeness Score**: Assesses domain coverage

### Quality Thresholds

Default quality thresholds for term selection:

- **Minimum Final Score**: 0.7
- **Minimum Validation Score**: 0.8
- **Minimum Frequency Score**: 0.5
- **Minimum Citation Impact**: 0.6

### Automated Quality Checks

The system performs automated quality checks:

- **Duplicate Detection**: Identifies and removes duplicate terms
- **Consistency Validation**: Checks for logical inconsistencies
- **Completeness Assessment**: Ensures adequate domain coverage
- **Performance Monitoring**: Tracks system performance metrics

## Performance Optimization

### SPARQL Query Optimization

The system includes several performance optimizations:

1. **Query Caching**: Results are cached to avoid repeated queries
2. **Batch Processing**: Multiple terms processed in single queries
3. **Index Utilization**: Queries optimized for ontology indexes
4. **Connection Pooling**: Efficient connection management

### Memory and Processing Optimization

- **Streaming Processing**: Large datasets processed in chunks
- **Parallel Execution**: Multi-threaded processing where possible
- **Memory Management**: Efficient memory usage for large ontologies
- **Progress Monitoring**: Real-time progress tracking

## Output and Reporting

### Report Formats

The system generates reports in multiple formats:

1. **JSON**: Machine-readable structured data
2. **Markdown**: Human-readable documentation
3. **CSV**: Tabular data for analysis
4. **HTML**: Web-friendly reports with visualizations

### Report Contents

Generated reports include:

- **Executive Summary**: High-level statistics and outcomes
- **Methodology Documentation**: Detailed process description
- **Selected Terms**: List of selected terms with scores
- **Rejected Terms**: List of rejected terms with reasons
- **Statistical Analysis**: Comprehensive statistical metrics
- **Validation Details**: Cross-reference validation results
- **Recommendations**: Suggestions for improvement

## Troubleshooting

### Common Issues

1. **SPARQL Endpoint Timeouts**
   - Solution: Increase timeout values in configuration
   - Alternative: Use query optimization features

2. **Memory Issues with Large Ontologies**
   - Solution: Enable streaming processing
   - Alternative: Increase system memory allocation

3. **Low Validation Scores**
   - Solution: Review cross-reference sources
   - Alternative: Adjust validation thresholds

4. **Performance Issues**
   - Solution: Enable query caching
   - Alternative: Use parallel processing options

### Debugging

Enable detailed logging for debugging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Components will automatically use detailed logging
analyzer = CorpusAnalyzer({'debug_mode': True})
```

### Support and Maintenance

- **Log Files**: Check `logs/` directory for detailed execution logs
- **Test Suite**: Run `pytest tests/ontology/` for comprehensive testing
- **Performance Monitoring**: Use built-in performance metrics
- **Configuration Validation**: System validates configuration on startup

---

*This documentation is automatically maintained and updated with each system release.*
