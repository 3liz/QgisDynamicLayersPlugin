__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

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

        vector = QgsVectorLayer(str(Path(f"fixtures/{folder_1}/lines.geojson")), "Layer 1")
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        parent_project = Path(self.temp_dir).joinpath("parent.qgs")

        project.setFileName(str(parent_project))
        self.assertTrue(project.write())
        self.assertTrue(parent_project.exists())

        field = "name"
        coverage = QgsVectorLayer(
            f"None?&field=id:integer&field={field}:string(20)&index=yes", "coverage", "memory")
        with edit(coverage):
            feature = QgsFeature(coverage.fields())
            feature.setAttributes([0, "1"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([0, "2"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([0, "3"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

        self.assertEqual(3, coverage.featureCount())

        field_name = coverage.fields().at(1).name()
        generator = GenerateProjects(project, coverage, field_name, Path(self.temp_dir))
        self.assertTrue(generator.process())

        unique_values = coverage.uniqueValues(coverage.fields().indexFromName(field_name))
        self.assertSetEqual({'1', '2', '3'}, unique_values)

        generator = GenerateProjects(project, coverage, field, Path(project.homePath()))
        self.assertTrue(generator.process())

        for i in unique_values:
            expected_project = "{}_{}.qgs".format(project.baseName(), i)
            self.assertTrue(
                Path(self.temp_dir).joinpath(expected_project).exists(),
                f"In folder {self.temp_dir}, {expected_project} for value = {i} does not exist")


if __name__ == '__main__':
    unittest.main()
