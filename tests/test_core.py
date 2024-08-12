__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import string
import unittest

from pathlib import Path

from qgis.core import QgsFeature, QgsProject, QgsVectorLayer, edit

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.definitions import CustomProperty
from tests.base_tests import BaseTests


class TestBasicReplacement(BaseTests):

    def test_replacement_map_layer(self):
        """ Test datasource can be replaced. """
        # noinspection PyArgumentList
        project = QgsProject()

        folder_1 = 'folder_1'
        folder_2 = 'folder_2'
        folder_token = '$folder'

        vector = QgsVectorLayer(str(Path(f"fixtures/{folder_1}/lines.geojson")), "Layer 1")
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        engine = DynamicLayersEngine()
        engine.set_dynamic_layers_from_project(project)
        self.assertDictEqual({}, engine._dynamic_layers)

        vector.setCustomProperty(CustomProperty.DynamicDatasourceActive, True)
        dynamic_source = vector.source()

        self.assertIn(folder_1, dynamic_source)
        self.assertNotIn(folder_2, dynamic_source)
        self.assertNotIn(folder_token, dynamic_source)

        dynamic_source = dynamic_source.replace(folder_1, folder_token)
        vector.setCustomProperty(CustomProperty.DynamicDatasourceContent, dynamic_source)

        engine.set_dynamic_layers_from_project(project)
        self.assertDictEqual(
            {
                vector.id(): vector
            },
            engine._dynamic_layers
        )

        # Replace
        engine.search_and_replace_dictionary = {
            'folder': folder_2,
        }

        engine.set_dynamic_layers_datasource_from_dict()
        engine.set_dynamic_project_properties(project, "Test title", "Test abstract")

        self.assertIn(folder_2, vector.source())
        self.assertNotIn(folder_1, vector.source())
        self.assertNotIn(folder_token, vector.source())

    def test_generate_projects(self):
        """ Test generate a bunch of projects. """
        # noinspection PyArgumentList
        project = QgsProject()

        folder_1 = 'folder_1'
        folder_2 = 'folder_2'
        folder_3 = 'folder_3'
        folder_token = '$folder'
        template_destination = string.Template('test_${folder}_test.qgs')
        layer_name = "Layer 1"

        vector_path = Path(__file__).parent.joinpath(f"fixtures/{folder_1}/lines_1.geojson")
        self.assertTrue(vector_path.exists(), str(vector_path))
        vector = QgsVectorLayer(str(vector_path), layer_name)
        vector.setCustomProperty(CustomProperty.DynamicDatasourceActive, True)
        vector.setCustomProperty(
            CustomProperty.DynamicDatasourceContent,
            str(vector_path).replace(folder_1, folder_token))
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        parent_project = Path(self.temp_dir).joinpath("parent.qgs")

        project.setFileName(str(parent_project))
        self.assertTrue(project.write())
        self.assertTrue(parent_project.exists())

        field = "folder"
        coverage = QgsVectorLayer(
            f"None?&field=id:integer&field={field}:string(20)&index=yes", "coverage", "memory")
        with edit(coverage):
            feature = QgsFeature(coverage.fields())
            feature.setAttributes([1, folder_1])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([2, folder_2])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([3, folder_3])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

        self.assertEqual(3, coverage.featureCount())

        field_name = coverage.fields().at(1).name()
        generator = GenerateProjects(project, coverage, field_name, template_destination, Path(self.temp_dir))

        # TODO With Python 3.11, switch to get_identifiers()
        self.assertListEqual(['folder'], generator.project_path_identifiers())

        self.assertTrue(generator.process())

        unique_values = coverage.uniqueValues(coverage.fields().indexFromName(field_name))
        self.assertSetEqual({'folder_1', 'folder_2', 'folder_3'}, unique_values)

        # generator = GenerateProjects(project, coverage, field, Path(project.homePath()))
        # self.assertTrue(generator.process())

        for i in unique_values:
            expected_project = template_destination.substitute({'folder': i})
            expected_path = Path(self.temp_dir).joinpath(expected_project)
            self.assertTrue(
                expected_path.exists(),
                f"In folder {self.temp_dir}, {expected_project} for value = {i} does not exist")

            child_project = QgsProject()
            child_project.read(str(expected_path))
            layer = child_project.mapLayersByName(layer_name)[0]
            self.assertTrue(i in layer.source())


if __name__ == '__main__':
    unittest.main()
