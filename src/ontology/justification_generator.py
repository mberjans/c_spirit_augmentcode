"""
Justification Generator for Ontology Term Selection.

This module provides functionality for generating automated justification
documents for ontology term selection decisions, including detailed
methodology, statistics, and validation reports.
"""

import json
import statistics
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
import numpy as np
from loguru import logger


class JustificationGenerator:
    """
    Generates automated justification documents for ontology term selection.
    
    This class creates comprehensive reports documenting the methodology,
    criteria, and results of automated ontology term selection processes.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the JustificationGenerator.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # Default configuration
        self.default_config = {
            "output_format": "json",
            "include_detailed_metrics": False,
            "include_visualizations": False,
            "selection_threshold": 0.7,
            "confidence_threshold": 0.8,
            "max_terms_display": 100
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def generate_selection_report(self, 
                                selected_terms: List[Dict[str, Any]], 
                                rejected_terms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a comprehensive selection report.
        
        Args:
            selected_terms: List of selected terms with scores
            rejected_terms: List of rejected terms with reasons
            
        Returns:
            Complete selection report dictionary
        """
        report = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "generator_version": "1.0.0",
                "selection_threshold": self.config["selection_threshold"]
            },
            "summary": self._generate_summary(selected_terms, rejected_terms),
            "methodology": self.generate_methodology_section(),
            "selected_terms": selected_terms[:self.config["max_terms_display"]],
            "rejected_terms": rejected_terms[:self.config["max_terms_display"]],
            "statistics": self.generate_statistics_summary(selected_terms + rejected_terms)
        }
        
        # Add optional sections based on configuration
        if self.config.get("include_detailed_metrics", False):
            report["detailed_metrics"] = self._generate_detailed_metrics(selected_terms)
            report["score_distribution"] = self._analyze_score_distribution(selected_terms)
            report["validation_details"] = self._generate_validation_summary(selected_terms)
        
        if self.config.get("include_visualizations", False):
            report["visualization_data"] = self.create_score_visualization_data(selected_terms)
        
        return report
    
    def generate_methodology_section(self) -> Dict[str, Any]:
        """
        Generate the methodology section of the report.
        
        Returns:
            Methodology documentation dictionary
        """
        return {
            "overview": "Automated ontology term selection using multi-criteria scoring approach",
            "scoring_criteria": {
                "frequency_analysis": {
                    "description": "Term usage frequency in target literature corpus",
                    "weight": 0.3,
                    "calculation": "Normalized frequency count with hierarchical weighting"
                },
                "citation_impact": {
                    "description": "Citation impact and academic relevance scoring",
                    "weight": 0.3,
                    "calculation": "Citation count normalized by publication year and field"
                },
                "cross_reference_validation": {
                    "description": "Cross-reference validation against established ontologies",
                    "weight": 0.4,
                    "calculation": "Weighted average of cross-reference matches and confidence scores"
                }
            },
            "validation_process": {
                "cross_reference_sources": ["Plant Ontology", "Gene Ontology", "ChEBI", "NCBI Taxonomy"],
                "validation_threshold": self.config["confidence_threshold"],
                "automated_checks": ["consistency", "completeness", "redundancy"]
            },
            "selection_thresholds": {
                "minimum_score": self.config["selection_threshold"],
                "confidence_threshold": self.config["confidence_threshold"],
                "quality_filters": ["deprecated_terms", "obsolete_terms", "low_usage"]
            }
        }
    
    def generate_statistics_summary(self, terms_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistical summary of term scores.
        
        Args:
            terms_data: List of terms with scoring data
            
        Returns:
            Statistical summary dictionary
        """
        if not terms_data:
            return {"error": "No terms data provided"}
        
        # Extract scores
        final_scores = [term.get('final_score', 0) for term in terms_data if 'final_score' in term]
        frequency_scores = [term.get('frequency_score', 0) for term in terms_data if 'frequency_score' in term]
        citation_scores = [term.get('citation_impact', 0) for term in terms_data if 'citation_impact' in term]
        
        stats = {
            "score_statistics": {
                "mean_score": statistics.mean(final_scores) if final_scores else 0,
                "median_score": statistics.median(final_scores) if final_scores else 0,
                "std_deviation": statistics.stdev(final_scores) if len(final_scores) > 1 else 0,
                "min_score": min(final_scores) if final_scores else 0,
                "max_score": max(final_scores) if final_scores else 0
            },
            "distribution_analysis": {
                "high_scoring_terms": len([s for s in final_scores if s >= 0.8]),
                "medium_scoring_terms": len([s for s in final_scores if 0.5 <= s < 0.8]),
                "low_scoring_terms": len([s for s in final_scores if s < 0.5])
            }
        }
        
        if frequency_scores:
            stats["frequency_statistics"] = {
                "mean": statistics.mean(frequency_scores),
                "median": statistics.median(frequency_scores)
            }
        
        if citation_scores:
            stats["citation_statistics"] = {
                "mean": statistics.mean(citation_scores),
                "median": statistics.median(citation_scores)
            }
        
        return stats
    
    def export_report_to_markdown(self, report_data: Dict[str, Any]) -> str:
        """
        Export report to markdown format.
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            Markdown formatted report string
        """
        markdown_lines = [
            "# Ontology Term Selection Report",
            "",
            f"Generated: {report_data.get('metadata', {}).get('generated_at', 'Unknown')}",
            "",
            "## Summary",
            "",
            f"Total Selected: {report_data.get('summary', {}).get('total_selected', 0)}",
            f"Total Rejected: {report_data.get('summary', {}).get('total_rejected', 0)}",
            f"Selection Rate: {report_data.get('summary', {}).get('selection_rate', 0):.2%}",
            "",
            "## Methodology",
            "",
            report_data.get('methodology', {}).get('overview', 'No methodology provided'),
            "",
            "## Selected Terms",
            ""
        ]
        
        # Add selected terms
        selected_terms = report_data.get('selected_terms', [])
        for term in selected_terms[:10]:  # Limit to first 10 for readability
            term_name = term.get('term', 'Unknown')
            final_score = term.get('final_score', 0)
            markdown_lines.append(f"- **{term_name}**: {final_score:.3f}")
        
        if len(selected_terms) > 10:
            markdown_lines.append(f"- ... and {len(selected_terms) - 10} more terms")
        
        return "\n".join(markdown_lines)
    
    def export_report_to_json(self, report_data: Dict[str, Any]) -> str:
        """
        Export report to JSON format.
        
        Args:
            report_data: Report data dictionary
            
        Returns:
            JSON formatted report string
        """
        return json.dumps(report_data, indent=2, ensure_ascii=False)
    
    def save_report_to_file(self, 
                           report_data: Dict[str, Any], 
                           output_path: str, 
                           format: str = 'json') -> None:
        """
        Save report to file.
        
        Args:
            report_data: Report data to save
            output_path: Path to output file
            format: Output format ('json' or 'markdown')
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == 'json':
            content = self.export_report_to_json(report_data)
        elif format.lower() == 'markdown':
            content = self.export_report_to_markdown(report_data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"Report saved to {output_path}")
    
    def _generate_summary(self, selected_terms: List[Dict], rejected_terms: List[Dict]) -> Dict[str, Any]:
        """Generate summary statistics."""
        total_selected = len(selected_terms)
        total_rejected = len(rejected_terms)
        total_terms = total_selected + total_rejected

        return {
            "total_selected": total_selected,
            "total_rejected": total_rejected,
            "total_evaluated": total_terms,
            "selection_rate": total_selected / total_terms if total_terms > 0 else 0
        }

    def generate_validation_details(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate validation details section.

        Args:
            validation_results: List of validation results for terms

        Returns:
            Validation details dictionary
        """
        if not validation_results:
            return {"error": "No validation results provided"}

        # Extract validation data
        confidence_scores = [result.get('confidence_score', 0) for result in validation_results]
        all_sources = set()
        total_cross_refs = 0

        for result in validation_results:
            sources = result.get('validation_sources', [])
            all_sources.update(sources)
            cross_refs = result.get('cross_references', [])
            total_cross_refs += len(cross_refs)

        return {
            "validation_summary": {
                "total_terms_validated": len(validation_results),
                "average_confidence": statistics.mean(confidence_scores) if confidence_scores else 0,
                "validation_sources_used": list(all_sources),
                "total_cross_references": total_cross_refs
            },
            "cross_reference_analysis": {
                "average_cross_refs_per_term": total_cross_refs / len(validation_results) if validation_results else 0,
                "sources_coverage": len(all_sources)
            },
            "confidence_distribution": {
                "high_confidence": len([s for s in confidence_scores if s >= 0.8]),
                "medium_confidence": len([s for s in confidence_scores if 0.5 <= s < 0.8]),
                "low_confidence": len([s for s in confidence_scores if s < 0.5])
            }
        }

    def create_score_visualization_data(self, terms_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create data for score visualizations.

        Args:
            terms_data: List of terms with scoring data

        Returns:
            Visualization data dictionary
        """
        if not terms_data:
            return {"error": "No terms data provided"}

        # Extract scores
        final_scores = [term.get('final_score', 0) for term in terms_data if 'final_score' in term]
        frequency_scores = [term.get('frequency_score', 0) for term in terms_data if 'frequency_score' in term]

        # Create score distribution bins
        if final_scores:
            bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            counts = [0] * (len(bins) - 1)

            for score in final_scores:
                for i in range(len(bins) - 1):
                    if bins[i] <= score < bins[i + 1]:
                        counts[i] += 1
                        break
                else:
                    if score >= bins[-1]:
                        counts[-1] += 1
        else:
            bins = []
            counts = []

        # Top terms for display
        sorted_terms = sorted(terms_data, key=lambda x: x.get('final_score', 0), reverse=True)
        top_terms = [
            {
                'term': term.get('term', 'Unknown'),
                'score': term.get('final_score', 0)
            }
            for term in sorted_terms[:10]
        ]

        return {
            "score_distribution": {
                "bins": bins,
                "counts": counts
            },
            "score_correlation": {
                "final_vs_frequency": self._calculate_correlation(final_scores, frequency_scores)
            },
            "top_terms": top_terms
        }

    def generate_recommendations(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate recommendations based on analysis results.

        Args:
            analysis_results: Results from term selection analysis

        Returns:
            Recommendations dictionary
        """
        recommendations = {
            "term_selection": [],
            "methodology": [],
            "validation": [],
            "future_work": []
        }

        # Term selection recommendations
        if analysis_results.get('low_scoring_terms'):
            recommendations["term_selection"].append(
                "Consider reviewing low-scoring terms for potential inclusion with manual validation"
            )

        if analysis_results.get('high_confidence_terms'):
            recommendations["term_selection"].append(
                "High-confidence terms show strong validation and should be prioritized"
            )

        # Methodology recommendations
        if analysis_results.get('methodology_improvements'):
            for improvement in analysis_results['methodology_improvements']:
                if improvement == 'increase_sample_size':
                    recommendations["methodology"].append(
                        "Consider increasing literature corpus sample size for better frequency analysis"
                    )

        # Validation recommendations
        if analysis_results.get('validation_gaps'):
            recommendations["validation"].append(
                "Address validation gaps by expanding cross-reference sources"
            )

        # Future work recommendations
        recommendations["future_work"].extend([
            "Implement machine learning approaches for automated term scoring",
            "Develop domain-specific validation criteria",
            "Create interactive visualization tools for term selection review"
        ])

        return recommendations

    def _generate_detailed_metrics(self, terms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate detailed metrics for selected terms."""
        if not terms:
            return {}

        metrics = {}

        # Score component analysis
        for component in ['frequency_score', 'citation_impact', 'validation_score']:
            scores = [term.get(component, 0) for term in terms if component in term]
            if scores:
                metrics[f"{component}_analysis"] = {
                    "mean": statistics.mean(scores),
                    "median": statistics.median(scores),
                    "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0
                }

        return metrics

    def _analyze_score_distribution(self, terms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze score distribution patterns."""
        final_scores = [term.get('final_score', 0) for term in terms if 'final_score' in term]

        if not final_scores:
            return {}

        return {
            "quartiles": {
                "q1": np.percentile(final_scores, 25) if final_scores else 0,
                "q2": np.percentile(final_scores, 50) if final_scores else 0,
                "q3": np.percentile(final_scores, 75) if final_scores else 0
            },
            "outliers": {
                "count": len([s for s in final_scores if s > np.percentile(final_scores, 95)]) if final_scores else 0
            }
        }

    def _generate_validation_summary(self, terms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate validation summary for detailed metrics."""
        validation_scores = [term.get('validation_score', 0) for term in terms if 'validation_score' in term]

        return {
            "validation_coverage": len(validation_scores) / len(terms) if terms else 0,
            "average_validation_score": statistics.mean(validation_scores) if validation_scores else 0
        }

    def _calculate_correlation(self, scores1: List[float], scores2: List[float]) -> float:
        """Calculate correlation between two score lists."""
        if len(scores1) != len(scores2) or len(scores1) < 2:
            return 0.0

        try:
            return np.corrcoef(scores1, scores2)[0, 1]
        except:
            return 0.0
