# Protégé Integration Setup

## Installation

1. **Java Requirements**
   - Install Java 11 or higher
   - Verify installation: `java -version`

2. **Protégé Installation**
   - Download Protégé 5.6.4 from:
     https://protege.stanford.edu/products.php#desktop-protege
   - Install following platform-specific instructions

3. **Project Setup**
   - Run: `python scripts/setup_protege.py`
   - Open Protégé and load project file: `data/ontologies/plant_metabolite_project.pprj`

## Configuration

The Protégé integration is configured via `config/protege_config.yaml`:

- **Reasoners**: Pellet, FaCT++, ELK
- **Required Plugins**: OWL Viz, OntoGraf, SPARQL Query, Ontology Debugger
- **Export Formats**: OWL/XML, RDF/XML, Turtle, N-Triples, JSON-LD

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
