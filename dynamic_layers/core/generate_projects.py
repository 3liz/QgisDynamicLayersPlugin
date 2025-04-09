__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import json

from pathlib import Path
from shutil import copyfile, copytree

from qgis.core import (
    Qgis,
    QgsFeatureRequest,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QApplication

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
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
            limit: int = None,
    ):
        """ Constructor. """
        self.project = project
        self.coverage = coverage
        self.field = field
        self.destination = destination
        self.expression_destination = expression_destination
        self.copy_side_car_files = copy_side_car_files
        self.feedback = feedback
        self.limit = limit

    def process(self) -> bool:
        """ Generate all projects needed according to the coverage layer. """
        if self.feedback:
            self.feedback.setProgress(0)
        engine = DynamicLayersEngine(self.feedback)
        engine.discover_dynamic_layers_from_project(self.project)

        base_path = self.project.fileName()

        if not self.destination.exists():
            self.destination.mkdir()

        log_message(tr('Copying side-car files : {}').format(self.copy_side_car_files), Qgis.MessageLevel.Info, self.feedback)

        log_message(tr('Starting the loop over features'), Qgis.MessageLevel.Info, self.feedback)

        total = 100.0 / self.coverage.featureCount() if self.coverage.featureCount() else 0

        request = QgsFeatureRequest()
        # noinspection PyUnresolvedReferences
        request.setFlags(QgsFeatureRequest.NoGeometry)
        if self.limit and self.limit >= 0:
            # For debug only
            request.setLimit(self.limit)
            if total >= self.limit:
                total = self.limit

        for i, feature in enumerate(self.coverage.getFeatures(request)):
            if self.feedback:
                if self.feedback.isCanceled():
                    break
                self.feedback.pushDebugInfo(tr(
                    'Feature ID : {} → "{}" = \'{}\'').format(feature.id(), self.field, feature[self.field]))

            if hasattr(self.feedback, 'widget'):
                # It's the own Feedback object
                QApplication.processEvents()

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
            log_message(tr("Compute new value for output file name"), Qgis.MessageLevel.Info, self.feedback)
            new_file = string_substitution(
                input_string=self.expression_destination,
                variables={},
                project=self.project,
                layer=self.coverage,
                feature=feature,
            )
            new_path = Path(f"{self.destination}/{new_file}")
            new_file_name = new_path.stem

            # The new path can contain new folder, specific to the evaluated expression
            if not new_path.parent.exists():
                new_path.parent.mkdir()

            # First copy side-car files, to avoid Lizmap to have question about a new project without CFG file
            cfg_file = None
            if self.copy_side_car_files:
                base_path_obj = Path(base_path)
                files = side_car_files(base_path_obj)
                log_message(
                    tr('List of side-car files 1/2 : {}').format(str([str(f) for f in files])),
                    Qgis.MessageLevel.Info,
                    self.feedback,
                )
                for a_file in files:
                    destination = str(new_path) + a_file.suffix
                    copyfile(a_file, destination)
                    if a_file.suffix.lower() == '.cfg' and extent:
                        cfg_file = destination

                try:
                    from lizmap.toolbelt.lizmap import sidecar_media_dirs
                    dirs = sidecar_media_dirs(base_path_obj)
                    log_message(
                        tr('List of side-car files 2/2 : {}').format(str([str(f) for f in dirs])),
                        Qgis.MessageLevel.Info,
                        self.feedback
                    )
                    for a_dir in dirs:
                        rel_path = a_dir.relative_to(base_path_obj.parent)

                        # Quick and replace "media/js/project_A/foo.js" to "media/js/project_B/foo.js"
                        rel_path = Path(str(rel_path).replace(base_path_obj.stem, new_file_name))

                        new_dir_path = new_path.parent.joinpath(rel_path)
                        new_dir_path.mkdir(parents=True, exist_ok=True)

                        copytree(a_dir, new_dir_path, dirs_exist_ok=True)

                        # log_message(
                        #     tr('Copy of directory : {}').format(str(rel_path)),
                        #     Qgis.Info,
                        #     self.feedback,
                        # )
                except ImportError:
                    log_message(
                        tr('No latest Lizmap plugin installed, if it is needed in your case.'),
                        Qgis.MessageLevel.Info,
                        self.feedback,
                    )


            log_message(tr('Project written to new file name {}').format(new_path.name), Qgis.MessageLevel.Info, self.feedback)
            self.project.setFileName(str(new_path))
            self.project.write()
            self.project.setFileName(base_path)

            if cfg_file:
                # Specific for Lizmap file
                try:
                    with open(cfg_file, 'r') as f:
                        content = json.load(f)
                    content['options']['bbox'] = extent
                    content['options']['initialExtent'] = [float(f) for f in extent]
                    with open(cfg_file, 'w') as f:
                        json.dump(content, f, sort_keys=False, indent=4)
                        f.write("\n")
                    log_message(
                        tr('updating Lizmap configuration file about the extent'),
                        Qgis.MessageLevel.Info,
                        self.feedback,
                    )
                except Exception as e:
                    log_message(
                        tr('Error with the Lizmap configuration file : {}').format(e),
                        Qgis.MessageLevel.Critical,
                        self.feedback,
                    )

            if self.feedback:
                self.feedback.setProgress(int(i * total))

        if self.feedback:
            # Should be OK without it, but let's increase it manually.
            self.feedback.setProgress(100)
        return True
