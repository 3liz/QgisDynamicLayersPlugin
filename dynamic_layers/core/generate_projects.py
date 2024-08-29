__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import json

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
from dynamic_layers.definitions import PLUGIN_SCOPE, PluginProjectProperty
from dynamic_layers.tools import (
    log_message,
    side_car_files,
    string_substitution,
    tr,
)


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
        self.feedback.setProgress(0)
        engine = DynamicLayersEngine(self.feedback)
        engine.discover_dynamic_layers_from_project(self.project)

        base_path = self.project.fileName()

        if not self.destination.exists():
            self.destination.mkdir()

        log_message(tr('Starting the loop over features'), Qgis.Info, self.feedback)

        total = 100.0 / self.coverage.featureCount() if self.coverage.featureCount() else 0

        request = QgsFeatureRequest()
        # noinspection PyUnresolvedReferences
        request.setFlags(QgsFeatureRequest.NoGeometry)
        for i, feature in enumerate(self.coverage.getFeatures(request)):
            if self.feedback:
                if self.feedback.isCanceled():
                    break
                self.feedback.pushDebugInfo(tr('Feature : {}').format(feature.id()))

            engine.set_layer_and_feature(self.coverage, feature)
            engine.update_dynamic_layers_datasource()
            if self.feedback:
                if self.feedback.isCanceled():
                    break

            for layer in self.project.mapLayers().values():
                # Force refresh layer extents
                if hasattr(layer, 'updateExtents'):
                    layer.updateExtents(True)
            if self.feedback:
                if self.feedback.isCanceled():
                    break

            engine.update_dynamic_project_properties()
            if self.feedback:
                if self.feedback.isCanceled():
                    break

            engine.force_refresh_all_layer_extents()

            # Set new extent
            extent = engine.update_project_extent()

            # Output file name
            log_message(tr("Compute new value for output file name"), Qgis.Info, self.feedback)
            new_file = string_substitution(
                input_string=self.expression_destination,
                variables={},
                project=self.project,
                layer=self.coverage,
                feature=feature,
            )
            new_path = Path(f"{self.destination}/{new_file}")
            log_message(tr('Project written to new file name {}').format(new_path.name), Qgis.Info, self.feedback)
            self.project.setFileName(str(new_path))
            self.project.write()
            self.project.setFileName(base_path)

            if self.copy_side_car_files:
                files = side_car_files(Path(base_path))
                for a_file in files:
                    destination = str(new_path) + a_file.suffix
                    copyfile(a_file, destination)

                    if a_file.suffix.lower() == '.cfg' and extent:
                        # Specific for Lizmap file
                        try:
                            with open(destination, 'r') as f:
                                content = json.load(f)
                            # print(f"File opened {destination}")
                            content['options']['bbox'] = extent
                            content['options']['initialExtent'] = [float(f) for f in extent]
                            with open(destination, 'w') as f:
                                json.dump(content, f, sort_keys=True, indent=4)
                                f.write("\n")
                            log_message(
                                tr('updating Lizmap configuration file about the extent'),
                                Qgis.Info,
                                self.feedback,
                            )
                        except Exception as e:
                            log_message(
                                tr('Error with the Lizmap configuration file : {}').format(e),
                                Qgis.Critical,
                                self.feedback,
                            )

            if self.feedback:
                self.feedback.setProgress(int(i * total))

        return True
