__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.core import QgsField, QgsProject, QgsVectorLayer


class GenerateProjects:

    def __init__(self, project: QgsProject, coverage: QgsVectorLayer, field: QgsField, destination: Path):
        self.project = project
        self.coverage = coverage
        self.field = field
        self.destination = destination

    def process(self) -> bool:
        return True
