__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path
from typing import Tuple

from qgis.core import (  # QgsFeatureRequest,
    QgsExpression,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterExpression,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFolderDestination,
)
from qgis.PyQt.QtGui import QIcon

from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.definitions import CustomProperty
from dynamic_layers.tools import resources_path, tr


class GenerateProjectsAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    COPY_SIDE_CAR_FILES = "COPY_SIDE_CAR_FILES"
    EXPRESSION_DESTINATION = "TEMPLATE_DESTINATION"
    OUTPUT = 'OUTPUT'

    def createInstance(self):
        return type(self)()

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

        parameter = QgsProcessingParameterExpression(
            self.EXPRESSION_DESTINATION,
            tr('QGIS Expression to format the final filename. It must end with .qgs or .qgz.'),
            parentLayerParameterName=self.INPUT,
        )
        parameter.setHelp(tr(
            "The template must have the file extension. A set of new folder can be created on the fly by adding your "
            "folder separator in the expression."
        ))
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

        if context.project().isDirty():
            msg = tr("You must save your project first.")
            return False, msg

        # source = self.parameterAsSource(parameters, self.INPUT, context)
        # field = self.parameterAsString(parameters, self.FIELD, context)
        # index = source.fields().indexFromName(field)
        # unique_values = source.uniqueValues(index)
        # if len(unique_values) != source.featureCount():
        #
        #     request = QgsFeatureRequest()
        #     request.setSubsetOfAttributes([field], source.fields())
        #     request.addOrderBy(field)
        #     request.setFlags(QgsFeatureRequest.NoGeometry)
        #     count = {}
        #     for f in source.getFeatures(request):
        #         if f[field] not in count.keys():
        #             count[f[field]] = 0
        #         count[f[field]] += 1
        #     debug = ''
        #     for k, v in count.items():
        #         debug += f'{k} → {v},   '
        #
        #     # count = {k: v for k, v in count.items() if v >= 2}
        #     msg = tr(
        #         "You field '{}' does not have unique values within the given layer : "
        #         "{} uniques values versus {} features : {}"
        #     ).format(
        #         field,
        #         len(unique_values),
        #         source.featureCount(),
        #         debug
        #     )
        #     return False, msg

        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsVectorLayer(
            parameters,
            self.INPUT,
            context
        )
        copy_side_car_files = self.parameterAsBool(parameters, self.COPY_SIDE_CAR_FILES, context)
        output_dir = Path(self.parameterAsString(parameters, self.OUTPUT, context))
        expression_destination = self.parameterAsExpression(parameters, self.EXPRESSION_DESTINATION, context)
        expression = QgsExpression(expression_destination)
        if expression.hasParserError():
            raise QgsProcessingException(expression.parserErrorString())

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        field = self.parameterAsString(parameters, self.FIELD, context)
        unique_values = source.uniqueValues(source.fields().indexFromName(field))
        feedback.pushInfo(tr("Generating {} projects in {}").format(len(unique_values), output_dir))
        feedback.pushDebugInfo(tr("List of uniques values") + " : " + ', '.join([str(i) for i in unique_values]))
        feedback.pushDebugInfo(tr("Copy side car files") + " : " + str(copy_side_car_files))

        generator = GenerateProjects(
            context.project(), source, field, expression_destination, output_dir, copy_side_car_files, feedback)
        generator.process()

        return {self.OUTPUT: str(output_dir)}
