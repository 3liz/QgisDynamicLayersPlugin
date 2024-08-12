__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import string

from pathlib import Path
from shutil import copyfile
from typing import List

from qgis.core import (
    QgsExpression,
    QgsProcessingFeatureSource,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.tools import side_car_files, tr


class GenerateProjects:

    def __init__(
            self,
            project: QgsProject,
            coverage: QgsVectorLayer | QgsProcessingFeatureSource,
            field: str,
            template_destination: string.Template,
            destination: Path,
            copy_side_car_files: bool,
            feedback: QgsProcessingFeedback = None,
    ):
        self.project = project
        self.coverage = coverage
        self.field = field
        self.destination = destination
        self.template_destination = template_destination
        self.copy_side_car_files = copy_side_car_files
        self.feedback = feedback

    def project_path_identifiers(self) -> List[str]:
        """List of identifiers in the string template. """
        # TODO In Python 3.11, use the new function get_identifiers
        return [
            s[1] or s[2] for s in string.Template.pattern.findall(self.template_destination.template) if s[1] or s[2]]

    def process(self) -> bool:
        engine = DynamicLayersEngine()
        engine.set_dynamic_layers_from_project(self.project)

        unique_values = self.coverage.uniqueValues(self.coverage.fields().indexFromName(self.field))

        base_path = self.project.fileName()

        if not self.destination.exists():
            self.destination.mkdir()

        token = self.project_path_identifiers()[0]

        for unique in unique_values:
            expression = QgsExpression.createFieldEqualityExpression(self.field, unique)
            if self.feedback:
                self.feedback.pushDebugInfo(tr('Expression generated {}').format(expression))

            engine.set_search_and_replace_dictionary_from_layer(self.coverage, expression)
            engine.set_dynamic_layers_datasource_from_dict()
            # TODO title and abstract
            engine.set_dynamic_project_properties(self.project)

            new_file = self.template_destination.substitute({token: unique})
            new_path = f"{self.destination}/{new_file}"
            if self.feedback:
                self.feedback.pushDebugInfo(tr('Project written to {}').format(new_path))
            self.project.setFileName(new_path)
            self.project.write()
            self.project.setFileName(base_path)

            if self.copy_side_car_files:
                files = side_car_files(Path(base_path))
                for a_file in files:
                    copyfile(a_file, new_path + a_file.suffix)

        return True
