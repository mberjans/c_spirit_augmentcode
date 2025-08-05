#!/usr/bin/env python3
"""
Protégé Integration Setup Script
Configures the development environment for Protégé integration with the plant metabolite project.
"""

import os
import sys
import yaml
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional

class ProtegeSetup:
    """Handles Protégé installation and configuration setup."""
    
    def __init__(self, config_path: str = "config/protege_config.yaml"):
        """Initialize with configuration file."""
        self.config_path = Path(config_path)
        self.project_root = Path(__file__).parent.parent
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load Protégé configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Configuration file not found: {self.config_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error parsing configuration file: {e}")
            sys.exit(1)
    
    def check_java_installation(self) -> bool:
        """Check if Java is installed and meets version requirements."""
        try:
            result = subprocess.run(['java', '-version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Parse Java version from output
                version_line = result.stderr.split('\n')[0]
                print(f"Java found: {version_line}")
                return True
            else:
                print("Java not found. Please install Java 11 or higher.")
                return False
        except FileNotFoundError:
            print("Java not found. Please install Java 11 or higher.")
            return False
    
    def create_directory_structure(self) -> None:
        """Create necessary directories for ontology management."""
        base_dir = self.project_root / self.config['protege']['project']['base_directory']
        
        directories = [
            base_dir,
            base_dir / "source_ontologies",
            base_dir / "integrated",
            base_dir / "backups",
            base_dir / "exports",
            self.project_root / "scripts" / "protege_scripts"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {directory}")
    
    def create_protege_project_file(self) -> None:
        """Create a Protégé project file (.pprj) for the main ontology."""
        project_config = self.config['protege']['project']
        base_dir = self.project_root / project_config['base_directory']
        
        # Create main ontology file if it doesn't exist
        main_ontology_path = base_dir / project_config['main_ontology']
        if not main_ontology_path.exists():
            self._create_base_ontology(main_ontology_path)
        
        # Create Protégé project file
        project_file_content = self._generate_project_file_content()
        project_file_path = base_dir / "plant_metabolite_project.pprj"
        
        with open(project_file_path, 'w') as f:
            f.write(project_file_content)
        
        print(f"Created Protégé project file: {project_file_path}")
    
    def _create_base_ontology(self, ontology_path: Path) -> None:
        """Create a base OWL ontology file."""
        base_ontology_content = '''<?xml version="1.0"?>
<rdf:RDF xmlns="http://example.org/plant-metabolites#"
     xml:base="http://example.org/plant-metabolites"
     xmlns:owl="http://www.w3.org/2002/07/owl#"
     xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
     xmlns:xml="http://www.w3.org/XML/1998/namespace"
     xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
    <owl:Ontology rdf:about="http://example.org/plant-metabolites">
        <rdfs:label>Plant Metabolite Knowledge Extraction Ontology</rdfs:label>
        <rdfs:comment>Integrated ontology for plant metabolite knowledge extraction system</rdfs:comment>
        <owl:versionInfo>1.0.0</owl:versionInfo>
    </owl:Ontology>
</rdf:RDF>'''
        
        with open(ontology_path, 'w') as f:
            f.write(base_ontology_content)
        
        print(f"Created base ontology: {ontology_path}")
    
    def _generate_project_file_content(self) -> str:
        """Generate Protégé project file content."""
        project_config = self.config['protege']['project']
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<project>
    <name>Plant Metabolite Knowledge Extraction</name>
    <description>Ontology project for plant metabolite knowledge extraction system</description>
    <ontology_uri>http://example.org/plant-metabolites</ontology_uri>
    <main_file>{project_config['main_ontology']}</main_file>
    <reasoner>{self.config['protege']['reasoners']['default']}</reasoner>
    <plugins>
        {self._format_plugins()}
    </plugins>
</project>'''
    
    def _format_plugins(self) -> str:
        """Format plugin list for project file."""
        plugins = self.config['protege']['plugins']['required']
        plugin_xml = ""
        for plugin in plugins:
            plugin_xml += f"        <plugin>{plugin}</plugin>\n"
        return plugin_xml.strip()
    
    def create_integration_scripts(self) -> None:
        """Create scripts for integrating Protégé with Python tools."""
        scripts_dir = self.project_root / "scripts" / "protege_scripts"
        
        # Create OWL export script
        export_script = '''#!/usr/bin/env python3
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
'''
        
        with open(scripts_dir / "export_ontology.py", 'w') as f:
            f.write(export_script)
        
        print(f"Created integration scripts in: {scripts_dir}")
    
    def generate_setup_documentation(self) -> None:
        """Generate documentation for Protégé setup and usage."""
        docs_content = f"""# Protégé Integration Setup

## Installation

1. **Java Requirements**
   - Install Java 11 or higher
   - Verify installation: `java -version`

2. **Protégé Installation**
   - Download Protégé {self.config['protege']['installation']['version']} from:
     {self.config['protege']['installation']['download_url']}
   - Install following platform-specific instructions

3. **Project Setup**
   - Run: `python scripts/setup_protege.py`
   - Open Protégé and load project file: `data/ontologies/plant_metabolite_project.pprj`

## Configuration

The Protégé integration is configured via `config/protege_config.yaml`:

- **Reasoners**: {', '.join(self.config['protege']['reasoners']['alternatives'])}
- **Required Plugins**: {', '.join(self.config['protege']['plugins']['required'])}
- **Export Formats**: {', '.join(self.config['protege']['formats']['export'])}

## Usage

1. **Opening the Project**
   ```bash
   # Start Protégé and open the project file
   protege data/ontologies/plant_metabolite_project.pprj
   ```

2. **Exporting Ontologies**
   ```bash
   # Export to different formats
   python scripts/protege_scripts/export_ontology.py data/ontologies/plant_metabolite_ontology.owl turtle
   ```

3. **Integration with Python**
   ```python
   import owlready2
   onto = owlready2.get_ontology("file://data/ontologies/plant_metabolite_ontology.owl").load()
   ```

## Troubleshooting

- **Memory Issues**: Increase Java heap size: `-Xmx4G`
- **Plugin Issues**: Check plugin compatibility with Protégé version
- **Reasoning Timeout**: Adjust timeout in configuration file
"""
        
        docs_path = self.project_root / "docs" / "protege_setup.md"
        with open(docs_path, 'w') as f:
            f.write(docs_content)
        
        print(f"Created setup documentation: {docs_path}")
    
    def run_setup(self) -> None:
        """Run the complete Protégé setup process."""
        print("Setting up Protégé integration...")
        
        # Check prerequisites
        if not self.check_java_installation():
            print("Please install Java before continuing.")
            return
        
        # Create directory structure
        self.create_directory_structure()
        
        # Create project files
        self.create_protege_project_file()
        
        # Create integration scripts
        self.create_integration_scripts()
        
        # Generate documentation
        self.generate_setup_documentation()
        
        print("\nProtégé integration setup complete!")
        print("Next steps:")
        print("1. Download and install Protégé from the URL in the documentation")
        print("2. Open the project file: data/ontologies/plant_metabolite_project.pprj")
        print("3. Install required plugins as listed in the configuration")

def main():
    """Main entry point."""
    setup = ProtegeSetup()
    setup.run_setup()

if __name__ == "__main__":
    main()
