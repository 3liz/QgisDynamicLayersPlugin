__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import string
import unittest

from pathlib import Path

from qgis.core import QgsFeature, QgsProject, QgsVectorLayer, edit

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.definitions import (
    PLUGIN_SCOPE,
    CustomProperty,
    PluginProjectProperty,
    WmsProjectProperty,
)
from dynamic_layers.tools import string_substitution
from tests.base_tests import BaseTests


class TestBasicReplacement(BaseTests):

    def test_replacement_map_layer(self):
        """ Test datasource can be replaced. """
        # noinspection PyArgumentList
        project = QgsProject()

        token = '@x'

        # Empty short name
        self.assertTupleEqual(('', False), project.readEntry(WmsProjectProperty.ShortName, "/"))

        # Set a short name template
        project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.ShortName, f"concat('Shortname ', @x)")
        project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.Abstract, f"concat('Abstract ', @x)")
        project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.Title, f"concat('Title ', @x)")

        vector = QgsVectorLayer(str(Path(f"fixtures/folder_1/lines_1.geojson")), f"Layer folder_1")
        self.assertTrue(vector.isValid())
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        engine = DynamicLayersEngine()
        engine.set_dynamic_layers_from_project(project)
        self.assertDictEqual({}, engine._dynamic_layers)

        vector.setCustomProperty(CustomProperty.DynamicDatasourceActive, True)
        dynamic_source = vector.source()

        self.assertIn('folder_1', dynamic_source)
        self.assertNotIn('folder_2', dynamic_source)
        self.assertNotIn(token, dynamic_source)

        # It must be a QGIS expression
        dynamic_source = f"concat('fixtures/folder_', @x, '/lines_', @x, '.geojson')"
        vector.setCustomProperty(CustomProperty.DynamicDatasourceContent, dynamic_source)
        vector.setCustomProperty(CustomProperty.NameTemplate, f"concat('Custom layer name ', @x)")
        vector.setCustomProperty(CustomProperty.TitleTemplate, f"concat('Custom layer title ', @x)")
        vector.setCustomProperty(CustomProperty.AbstractTemplate, f"concat('Custom layer abstract ', @x)")

        engine.set_dynamic_layers_from_project(project)
        self.assertDictEqual(
            {
                vector.id(): vector
            },
            engine._dynamic_layers
        )

        # Replace
        engine.search_and_replace_dictionary = {
            'x': '2',
        }

        engine.set_dynamic_layers_datasource_from_dict()
        engine.set_dynamic_project_properties(project)

        self.assertIn('folder_2', vector.source())
        self.assertNotIn('folder_1', vector.source())
        self.assertNotIn(token, vector.source())
        self.assertTrue(vector.isValid())

        # Layer properties
        self.assertEqual(f"Custom layer name 2", vector.name())
        self.assertEqual(f"Custom layer title 2", vector.title())
        self.assertEqual(f"Custom layer abstract 2", vector.abstract())

        # Project properties
        # Short name
        self.assertTupleEqual(
            (f'Shortname 2', True),
            project.readEntry(WmsProjectProperty.ShortName, "/")
        )
        # Abstract
        self.assertTupleEqual(
            (f'Abstract 2', True),
            project.readEntry(WmsProjectProperty.Abstract, "/")
        )
        # WMS
        self.assertTupleEqual(
            ('1', True),
            project.readEntry(WmsProjectProperty.Capabilities, "/")
        )

    def test_generate_projects(self):
        """ Test generate a bunch of projects. """
        # noinspection PyArgumentList
        project = QgsProject()

        template_destination = "concat('project_', @folder, ' ', @name, '.qgs')"
        layer_name = "Layer 1"

        vector_path = Path(__file__).parent.joinpath(f"fixtures/folder_1/lines_1.geojson")
        self.assertTrue(vector_path.exists(), str(vector_path))
        vector = QgsVectorLayer(str(vector_path), layer_name)
        vector.setCustomProperty(CustomProperty.DynamicDatasourceActive, True)
        vector.setCustomProperty(
            CustomProperty.DynamicDatasourceContent,
            "concat('fixtures/folder_', @folder, '/lines_', @folder, '.geojson')"
        )
        project.addMapLayer(vector)
        self.assertEqual(1, len(project.mapLayers()))

        parent_project = Path(self.temp_dir).joinpath("parent.qgs")
        side_car = Path(self.temp_dir).joinpath("parent.qgs.png")
        side_car.touch()

        # Set abstract template
        project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.Abstract, "concat('Abstract ', @folder)")

        project.setFileName(str(parent_project))
        self.assertTrue(project.write())
        self.assertTrue(parent_project.exists())

        field = "folder"
        name = "name"
        coverage = QgsVectorLayer(
            f"None?&"
            f"field=id:integer&"
            f"field={field}:string(20)&"
            f"field={name}:string(20)&"
            f"index=yes", "coverage", "memory")
        with edit(coverage):
            feature = QgsFeature(coverage.fields())
            feature.setAttributes([1, "folder_1", "Name 1"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([2, "folder_2", "Name 2"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

            feature = QgsFeature(coverage.fields())
            feature.setAttributes([3, "folder_3", "Name 3"])
            # noinspection PyArgumentList
            coverage.addFeature(feature)

        self.assertEqual(3, coverage.featureCount())

        field_name = coverage.fields().at(1).name()
        generator = GenerateProjects(
            project, coverage, field_name, template_destination, Path(self.temp_dir), True)

        self.assertTrue(generator.process())

        unique_values = coverage.uniqueValues(coverage.fields().indexFromName(field_name))
        self.assertSetEqual({'folder_1', 'folder_2', 'folder_3'}, unique_values)

        for feature in coverage.getFeatures():
            expected_project = string_substitution(
                template_destination,
                {
                        'folder': feature[field],
                        'name': feature[name],
                    }
                )
            expected_path = Path(self.temp_dir).joinpath(expected_project)
            self.assertTrue(
                expected_path.exists(),
                f"In folder {self.temp_dir}, {expected_project} for value = {feature[field]} does not exist")

            # Test sidecar
            side = Path(str(expected_path) + ".png")
            self.assertTrue(
                side.exists(),
                f"In folder {self.temp_dir}, {side} for value = {feature[field]} does not exist for the side car file")

            child_project = QgsProject()
            child_project.read(str(expected_path))
            layer = child_project.mapLayersByName(layer_name)[0]
            self.assertTrue(feature[field] in layer.source())

            # Check short name
            self.assertTupleEqual(
                (f'Abstract {feature[field]}', True),
                child_project.readEntry(WmsProjectProperty.Abstract, "/")
            )


if __name__ == '__main__':
    unittest.main()
