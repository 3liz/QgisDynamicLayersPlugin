from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from dynamic_layers.processing_provider.generate_projects import (
    GenerateProjectsAlgorithm,
)
from dynamic_layers.tools import resources_path


class Provider(QgsProcessingProvider):

    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(GenerateProjectsAlgorithm())

    def id(self, *args, **kwargs):
        return 'dynamic_layers'

    def name(self, *args, **kwargs):
        return 'Dynamic layers'

    def icon(self):
        return QIcon(str(resources_path('icons', 'icon.png')))
