__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import string

from pathlib import Path
from typing import Tuple

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterString,
)
from qgis.PyQt.QtGui import QIcon

from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.definitions import CustomProperty
from dynamic_layers.tools import resources_path, tr


class GenerateProjectsAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    COPY_SIDE_CAR_FILES = "COPY_SIDE_CAR_FILES"
    TEMPLATE_DESTINATION = "TEMPLATE_DESTINATION"
    OUTPUT = 'OUTPUT'

    def createInstance(self):
        return GenerateProjectsAlgorithm()

    def name(self):
        return 'generate_projects'

    def displayName(self):
        return tr('Generate projects')

    def icon(self):
        return QIcon(str(resources_path('icons', 'icon.png')))

    def shortHelpString(self):
        return tr("Generate all projects for all unique values in the layer")

    def initAlgorithm(self, config=None):
        # noinspection PyUnresolvedReferences
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                tr('Coverage layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD,
                tr('Field having unique values'),
                parentLayerParameterName=self.INPUT,
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.COPY_SIDE_CAR_FILES,
                tr(
                    'Copy all project side-car files, for instance copy "project_photo.qgs.png" if the file is '
                    'existing.'
                ),
                defaultValue=True,
            )
        )

        parameter = QgsProcessingParameterString(
            self.TEMPLATE_DESTINATION,
            tr('Template to use to format the final filename'),
        )
        parameter.setHelp(
            "The template must have the extension and at least one field name as a Python string template, such as "
            "'project_$province.qgs' when the layer has field called 'province'"
        )
        self.addParameter(parameter)

        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT,
                tr('Destination folder')
            )
        )

    def checkParameterValues(self, parameters, context) -> Tuple[bool, str]:
        layers = context.project().mapLayers().values()
        flag = False
        for layer in layers:
            if layer.customProperty(CustomProperty.DynamicDatasourceActive):
                flag = True
                break

        if not flag:
            # TODO check configuration, maybe only at the project level
            msg = tr("You must have at least one layer with the configuration.")
            return False, msg

        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )
        copy_side_car_files = self.parameterAsBool(parameters, self.COPY_SIDE_CAR_FILES, context)
        output_dir = Path(self.parameterAsString(parameters, self.OUTPUT, context))
        template_destination = string.Template(self.parameterAsString(parameters, self.TEMPLATE_DESTINATION, context))

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        field = self.parameterAsString(parameters, self.FIELD, context)
        index = source.fields().indexFromName(field)
        unique_values = source.uniqueValues(index)
        feedback.pushInfo(tr("Generating {} projects in {}").format(len(unique_values), output_dir))
        feedback.pushDebugInfo(tr("List of uniques values") + " : " + ', '.join([str(i) for i in unique_values]))
        feedback.pushDebugInfo(tr("Copy side car files") + " : " + str(copy_side_car_files))

        generator = GenerateProjects(
            context.project(), source, field, template_destination, output_dir, copy_side_car_files, feedback)
        generator.process()

        return {self.OUTPUT: str(output_dir)}
