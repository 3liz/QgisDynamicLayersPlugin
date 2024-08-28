__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path
from shutil import copyfile

from qgis.core import (
    Qgis,
    QgsFeatureRequest,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.tools import log, side_car_files, string_substitution, tr


class GenerateProjects:

    def __init__(
            self,
            project: QgsProject,
            coverage: QgsVectorLayer,
            field: str,
            expression_destination: str,
            destination: Path,
            copy_side_car_files: bool,
            feedback: QgsProcessingFeedback = None,
    ):
        """ Constructor. """
        self.project = project
        self.coverage = coverage
        self.field = field
        self.destination = destination
        self.expression_destination = expression_destination
        self.copy_side_car_files = copy_side_car_files
        self.feedback = feedback

    def process(self) -> bool:
        """ Generate all projects needed according to the coverage layer. """
        engine = DynamicLayersEngine(self.feedback)
        engine.discover_dynamic_layers_from_project(self.project)

        base_path = self.project.fileName()

        if not self.destination.exists():
            self.destination.mkdir()

        log(tr('Starting the loop over features'), Qgis.Info, self.feedback)

        request = QgsFeatureRequest()
        # noinspection PyUnresolvedReferences
        request.setFlags(QgsFeatureRequest.NoGeometry)
        for feature in self.coverage.getFeatures(request):
            engine.set_layer_and_feature(self.coverage, feature)

            if self.feedback:
                self.feedback.pushDebugInfo(tr('Feature : {}').format(feature.id()))

            engine.update_dynamic_layers_datasource()
            engine.update_dynamic_project_properties()

            # Output file name
            log(tr("Compute new value for output file name"), Qgis.Info, self.feedback)
            new_file = string_substitution(
                input_string=self.expression_destination,
                variables={},
                project=self.project,
                layer=self.coverage,
                feature=feature,
            )
            new_path = Path(f"{self.destination}/{new_file}")
            log(tr('Project written to new file name {}').format(new_path.name), Qgis.Info, self.feedback)
            self.project.setFileName(str(new_path))
            self.project.write()
            self.project.setFileName(base_path)

            if self.copy_side_car_files:
                files = side_car_files(Path(base_path))
                for a_file in files:
                    copyfile(a_file, str(new_path) + a_file.suffix)

        return True
