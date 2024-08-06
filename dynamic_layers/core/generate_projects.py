__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.core import (
    QgsProcessingFeatureSource,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.tools import tr


class GenerateProjects:

    def __init__(
            self,
            project: QgsProject,
            coverage: QgsVectorLayer | QgsProcessingFeatureSource,
            field: str,
            destination: Path,
            feedback: QgsProcessingFeedback = None,
    ):
        self.project = project
        self.coverage = coverage
        self.field = field
        self.destination = destination
        self.feedback = feedback

    def process(self) -> bool:
        engine = DynamicLayersEngine()
        engine.set_dynamic_layers_from_project(self.project)

        unique_values = self.coverage.uniqueValues(self.coverage.fields().indexFromName(self.field))

        base_path = self.project.fileName()
        base_name = self.project.baseName()

        for unique in unique_values:
            engine.search_and_replace_dictionary = {
                'folder': unique,
            }

            engine.set_dynamic_layers_datasource_from_dict()
            engine.set_dynamic_project_properties(self.project, "Test title", "Test abstract")

            new_path = "{}/{}_{}.qgs".format(self.project.homePath(), base_name, unique)
            if self.feedback:
                self.feedback.pushDebugInfo(tr('Project written to {}').format(new_path))
            self.project.setFileName(new_path)
            self.project.write()
            self.project.setFileName(base_path)

        return True
