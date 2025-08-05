#!/usr/bin/env python3
"""Export ontology from Protégé format to various formats."""

import owlready2
from pathlib import Path

def export_ontology(input_file: str, output_format: str = "turtle"):
    """Export OWL ontology to specified format."""
    onto = owlready2.get_ontology(f"file://{input_file}").load()
    
    output_file = Path(input_file).with_suffix(f".{output_format}")
    onto.save(file=str(output_file), format=output_format)
    print(f"Exported to {output_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        export_ontology(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "turtle")
    else:
        print("Usage: python export_ontology.py <input_file> [format]")
