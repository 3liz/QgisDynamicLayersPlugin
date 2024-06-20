__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import unittest

from pathlib import Path

from qgis.core import QgsVectorLayer
from qgis.core import QgsProject

from dynamic_layers.definitions import CustomProperty
from dynamic_layers.dynamic_layers_engine import DynamicLayersEngine
from tests.base_tests import BaseTests


class TestBasicReplacement(BaseTests):

    def test_replacement_map_layer(self):
        """ Test datasource can be replaced. """
        project = QgsProject()

        vector = QgsVectorLayer(str(Path("fixtures/folder_1/lines.geojson")), "Layer 1")
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        engine = DynamicLayersEngine()
        engine.set_dynamic_layers_list(project)
        self.assertDictEqual({}, engine.dynamic_layers)

        vector.setCustomProperty(CustomProperty.DynamicDatasourceActive, str(True))
        dynamic_source = vector.source()

        self.assertIn("folder_1", dynamic_source)
        self.assertNotIn("folder_2", dynamic_source)
        self.assertNotIn("{$folder}", dynamic_source)

        dynamic_source = dynamic_source.replace("folder_1", "{$folder}")
        vector.setCustomProperty(CustomProperty.DynamicDatasourceContent, dynamic_source)

        engine.set_dynamic_layers_list(project)
        self.assertDictEqual(
            {
                vector.id(): vector
            },
            engine.dynamic_layers
        )

        # Replace
        variables = {
            'folder': 'folder_2',
        }
        engine.set_search_and_replace_dictionary(variables)

        engine.set_dynamic_layers_datasource_from_dic()
        engine.set_dynamic_project_properties(project, "Test title", "Test abstract")

        self.assertIn("folder_2", vector.source())
        self.assertNotIn("folder_1", vector.source())
        self.assertNotIn("{$folder}", vector.source())


if __name__ == '__main__':
    unittest.main()
