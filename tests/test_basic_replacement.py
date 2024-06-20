__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import unittest

from pathlib import Path

from qgis.core import QgsVectorLayer
from qgis.core import QgsProject

from tests.base_tests import BaseTests


class TestBasicReplacement(BaseTests):

    def test_replacement_map_layer(self):
        """ Test datasource can be replaced. """
        project = QgsProject()

        vector = QgsVectorLayer(str(Path("fixtures/folder_1/lines.geojson")), "Layer 1")
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))


if __name__ == '__main__':
    unittest.main()
