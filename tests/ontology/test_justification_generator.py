"""
Tests for the JustificationGenerator class.

This module contains tests for automated justification document generation
functionality for ontology term selection.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any
from pathlib import Path
import json

from tests.ontology.test_base import OntologyTestBase


class TestJustificationGenerator(OntologyTestBase):
    """Test cases for JustificationGenerator class."""
    
    def test_justification_generator_initialization(self):
        """Test JustificationGenerator initialization."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        assert generator.config is not None
        assert hasattr(generator, 'logger')
        
        # Test with custom config
        custom_config = {'output_format': 'markdown', 'include_metrics': True}
        generator_custom = JustificationGenerator(custom_config)
        
        assert generator_custom.config['output_format'] == 'markdown'
        assert generator_custom.config['include_metrics'] is True
    
    def test_generate_selection_report_basic(self):
        """Test basic selection report generation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        # Mock term selection data
        selected_terms = [
            {
                'term': 'leaf',
                'uri': 'http://purl.obolibrary.org/obo/PO_0025034',
                'frequency_score': 0.85,
                'citation_impact': 0.92,
                'validation_score': 0.88,
                'final_score': 0.88
            },
            {
                'term': 'stem',
                'uri': 'http://purl.obolibrary.org/obo/PO_0025047',
                'frequency_score': 0.78,
                'citation_impact': 0.84,
                'validation_score': 0.81,
                'final_score': 0.81
            }
        ]
        
        rejected_terms = [
            {
                'term': 'obsolete_term',
                'uri': 'http://purl.obolibrary.org/obo/PO_0000001',
                'frequency_score': 0.12,
                'citation_impact': 0.05,
                'validation_score': 0.08,
                'final_score': 0.08,
                'rejection_reason': 'Low validation score'
            }
        ]
        
        report = generator.generate_selection_report(selected_terms, rejected_terms)
        
        assert isinstance(report, dict)
        assert 'summary' in report
        assert 'selected_terms' in report
        assert 'rejected_terms' in report
        assert 'methodology' in report
        assert 'statistics' in report
        
        # Check summary statistics
        assert report['summary']['total_selected'] == 2
        assert report['summary']['total_rejected'] == 1
        assert report['summary']['selection_rate'] == 2/3
    
    def test_generate_selection_report_with_metrics(self):
        """Test selection report generation with detailed metrics."""
        from src.ontology.justification_generator import JustificationGenerator
        
        config = {'include_detailed_metrics': True, 'include_visualizations': True}
        generator = JustificationGenerator(config)
        
        selected_terms = [
            {
                'term': 'leaf',
                'uri': 'http://purl.obolibrary.org/obo/PO_0025034',
                'frequency_score': 0.85,
                'citation_impact': 0.92,
                'validation_score': 0.88,
                'final_score': 0.88,
                'hierarchical_depth': 3,
                'relationship_count': 15
            }
        ]
        
        report = generator.generate_selection_report(selected_terms, [])
        
        assert 'detailed_metrics' in report
        assert 'score_distribution' in report
        assert 'validation_details' in report
    
    def test_generate_methodology_section(self):
        """Test methodology section generation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        methodology = generator.generate_methodology_section()
        
        assert isinstance(methodology, dict)
        assert 'overview' in methodology
        assert 'scoring_criteria' in methodology
        assert 'validation_process' in methodology
        assert 'selection_thresholds' in methodology
        
        # Check that scoring criteria are documented
        scoring_criteria = methodology['scoring_criteria']
        assert 'frequency_analysis' in scoring_criteria
        assert 'citation_impact' in scoring_criteria
        assert 'cross_reference_validation' in scoring_criteria
    
    def test_generate_statistics_summary(self):
        """Test statistics summary generation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        terms_data = [
            {'final_score': 0.95, 'frequency_score': 0.90, 'citation_impact': 0.88},
            {'final_score': 0.82, 'frequency_score': 0.85, 'citation_impact': 0.79},
            {'final_score': 0.76, 'frequency_score': 0.72, 'citation_impact': 0.80},
        ]
        
        stats = generator.generate_statistics_summary(terms_data)
        
        assert isinstance(stats, dict)
        assert 'score_statistics' in stats
        assert 'distribution_analysis' in stats
        
        # Check score statistics
        score_stats = stats['score_statistics']
        assert 'mean_score' in score_stats
        assert 'median_score' in score_stats
        assert 'std_deviation' in score_stats
        assert 'min_score' in score_stats
        assert 'max_score' in score_stats
        
        # Verify calculations
        assert score_stats['mean_score'] == pytest.approx(0.843, rel=1e-2)
        assert score_stats['min_score'] == 0.76
        assert score_stats['max_score'] == 0.95
    
    def test_export_report_to_markdown(self):
        """Test exporting report to markdown format."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator({'output_format': 'markdown'})
        
        report_data = {
            'summary': {'total_selected': 10, 'total_rejected': 5},
            'methodology': {'overview': 'Test methodology'},
            'selected_terms': [{'term': 'leaf', 'final_score': 0.88}]
        }
        
        markdown_content = generator.export_report_to_markdown(report_data)
        
        assert isinstance(markdown_content, str)
        assert '# Ontology Term Selection Report' in markdown_content
        assert '## Summary' in markdown_content
        assert '## Methodology' in markdown_content
        assert '## Selected Terms' in markdown_content
        assert 'Total Selected: 10' in markdown_content
        assert 'Total Rejected: 5' in markdown_content
    
    def test_export_report_to_json(self):
        """Test exporting report to JSON format."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        report_data = {
            'summary': {'total_selected': 10, 'total_rejected': 5},
            'selected_terms': [{'term': 'leaf', 'final_score': 0.88}]
        }
        
        json_content = generator.export_report_to_json(report_data)
        
        assert isinstance(json_content, str)
        
        # Verify it's valid JSON
        parsed_data = json.loads(json_content)
        assert parsed_data['summary']['total_selected'] == 10
        assert parsed_data['selected_terms'][0]['term'] == 'leaf'
    
    def test_save_report_to_file(self, tmp_path):
        """Test saving report to file."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        report_data = {
            'summary': {'total_selected': 5},
            'selected_terms': [{'term': 'leaf'}]
        }
        
        output_file = tmp_path / "selection_report.json"
        generator.save_report_to_file(report_data, str(output_file), format='json')
        
        assert output_file.exists()
        
        # Verify file contents
        with open(output_file) as f:
            loaded_data = json.load(f)
        
        assert loaded_data['summary']['total_selected'] == 5
        assert loaded_data['selected_terms'][0]['term'] == 'leaf'
    
    def test_generate_validation_details(self):
        """Test validation details generation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        validation_results = [
            {
                'term': 'leaf',
                'cross_references': ['GO:0048046', 'CHEBI:33256'],
                'validation_sources': ['Plant Ontology', 'Gene Ontology', 'ChEBI'],
                'confidence_score': 0.92
            }
        ]
        
        details = generator.generate_validation_details(validation_results)
        
        assert isinstance(details, dict)
        assert 'validation_summary' in details
        assert 'cross_reference_analysis' in details
        assert 'confidence_distribution' in details
        
        # Check validation summary
        summary = details['validation_summary']
        assert 'total_terms_validated' in summary
        assert 'average_confidence' in summary
        assert 'validation_sources_used' in summary
    
    def test_create_score_visualization_data(self):
        """Test score visualization data creation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator({'include_visualizations': True})
        
        terms_data = [
            {'term': 'leaf', 'final_score': 0.95, 'frequency_score': 0.90},
            {'term': 'stem', 'final_score': 0.82, 'frequency_score': 0.85},
            {'term': 'root', 'final_score': 0.76, 'frequency_score': 0.72}
        ]
        
        viz_data = generator.create_score_visualization_data(terms_data)
        
        assert isinstance(viz_data, dict)
        assert 'score_distribution' in viz_data
        assert 'score_correlation' in viz_data
        assert 'top_terms' in viz_data
        
        # Check score distribution data
        distribution = viz_data['score_distribution']
        assert 'bins' in distribution
        assert 'counts' in distribution
        assert len(distribution['bins']) > 0
        assert len(distribution['counts']) > 0
    
    def test_generate_recommendations(self):
        """Test recommendations generation."""
        from src.ontology.justification_generator import JustificationGenerator
        
        generator = JustificationGenerator()
        
        analysis_results = {
            'low_scoring_terms': ['term1', 'term2'],
            'high_confidence_terms': ['leaf', 'stem'],
            'validation_gaps': ['missing_cross_refs'],
            'methodology_improvements': ['increase_sample_size']
        }
        
        recommendations = generator.generate_recommendations(analysis_results)
        
        assert isinstance(recommendations, dict)
        assert 'term_selection' in recommendations
        assert 'methodology' in recommendations
        assert 'validation' in recommendations
        assert 'future_work' in recommendations
        
        # Check that recommendations are actionable
        term_recs = recommendations['term_selection']
        assert len(term_recs) > 0
        assert all(isinstance(rec, str) for rec in term_recs)
