from PyQt5.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from dynamic_layers.processing_provider.generate_projects import GenerateProjects

from dynamic_layers.tools import resources_path


class Provider(QgsProcessingProvider):

    def loadAlgorithms(self, *args, **kwargs):
        self.addAlgorithm(GenerateProjects())

    def id(self, *args, **kwargs):
        return 'dynamic_layers'

    def name(self, *args, **kwargs):
        return 'Dynamic layers'

    def icon(self):
        return QIcon(str(resources_path('icons', 'icon.png')))
