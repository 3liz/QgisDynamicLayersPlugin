__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFolderDestination,
)
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.tools import resources_path, tr


class GenerateProjectsAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    COPY_SIDE_CAR_FILES = "COPY_SIDE_CAR_FILES"
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

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
                tr('Copy all project side-car files'),
            )
        )

        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT,
                tr('Destination folder')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )
        output_dir = Path(self.parameterAsString(parameters, self.OUTPUT, context))

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        field = self.parameterAsString(parameters, self.FIELD, context)
        index = source.fields().indexFromName(field)
        unique_values = source.uniqueValues(index)
        feedback.pushInfo(tr("Generating {} projects in {}").format(len(unique_values), output_dir))
        feedback.pushDebugInfo(tr("List of uniques values") + " : " + ', '.join([str(i) for i in unique_values]))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )
        _ = sink
        _ = dest_id

        generator = GenerateProjects(context.project(), source, field, feedback)
        generator.process()

        return {self.OUTPUT: dest_id}
