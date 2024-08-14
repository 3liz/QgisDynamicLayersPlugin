__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from typing import Annotated

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.utils import iface

from dynamic_layers.core.layer_datasource_modifier import (
    LayerDataSourceModifier,
)
from dynamic_layers.definitions import (
    PLUGIN_SCOPE,
    CustomProperty,
    PluginProjectProperty,
    WmsProjectProperty,
)
from dynamic_layers.tools import string_substitution


class DynamicLayersEngine:

    def __init__(self):
        """ Dynamic Layers Engine constructor. """
        self.extent_layer = None
        self.extent_margin = None
        self.dynamic_layers: dict = {}
        self.variables: dict = {}
        self.iface = iface

        # For expressions
        self.project = None
        self.layer = None
        self.feature = None

    def set_layer_and_expression(self, layer: QgsVectorLayer, expression: str):
        """ Set the search and replace dictionary from a given layer and an expression.

        The first found feature is the data source
        """
        q_exp = QgsExpression(expression)
        if not q_exp.hasParserError():
            q_req = QgsFeatureRequest(q_exp)
            features = layer.getFeatures(q_req)
        else:
            # noinspection PyArgumentList
            QgsMessageLog.logMessage(
                f'An error occurred while parsing the given expression: {q_exp.parserErrorString()}')
            features = layer.getFeatures()

        # Take only first feature
        feature = QgsFeature()
        features.nextFeature(feature)
        self.set_layer_and_feature(layer, feature)

    def set_layer_and_feature(self, layer: QgsVectorLayer, feature: QgsFeature):
        """ Set a feature for the dictionary. """
        self.layer = layer
        self.feature = feature

    def discover_dynamic_layers_from_project(self, project: QgsProject):
        """ Check all maplayers in the given project which are dynamic. """
        self.project = project
        self.dynamic_layers = {
            lid: layer for lid, layer in project.mapLayers().items() if
            layer.customProperty(CustomProperty.DynamicDatasourceActive) and layer.customProperty(
                CustomProperty.DynamicDatasourceContent)
        }

    def update_dynamic_layers_datasource(self):
        """
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionary
        """
        for layer in self.dynamic_layers.values():
            a = LayerDataSourceModifier(layer, self.project, self.layer, self.feature)
            a.compute_new_uri(self.variables)

            if not self.iface:
                continue

            if layer.renderer() and layer.renderer().type() == 'graduatedSymbol':
                layer.triggerRepaint()

        if not self.iface:
            return

        self.iface.actionDraw().trigger()
        self.iface.mapCanvas().refresh()

    def update_dynamic_project_properties(self):
        """
        Set some project properties : title, short name, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        """
        # Make sure WMS Service is active
        if not self.project.readEntry(WmsProjectProperty.Capabilities, "/")[1]:
            self.project.writeEntry(WmsProjectProperty.Capabilities, "/", True)

        # Title
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Title)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.Title, val[0])

        # Shortname
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.ShortName)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.ShortName, val[0])

        # Abstract
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Abstract)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.Abstract, val[0])

    def set_project_property(self, project_property: Annotated[str, WmsProjectProperty], val: str):
        """
        Set a project property
        And replace variable if found in the properties
        """
        # Replace variable in given val via dictionary
        val = string_substitution(
            input_string=val,
            variables=self.variables,
            project=self.project,
            layer=self.layer,
            feature=self.feature,
        )
        self.project.writeEntry(project_property, '', val)

    def update_project_extent(self) -> QgsRectangle:
        """
        Sets the project extent
        and corresponding XML property
        """
        # Get extent from extent layer (if given)
        p_extent = None
        if self._extent_layer:
            self._extent_layer.updateExtents()
            p_extent = self._extent_layer.extent()
        else:
            if self.iface:
                p_extent = self.iface.mapCanvas().extent()
        if p_extent and p_extent.width() <= 0 and self.iface:
            p_extent = self.iface.mapCanvas().extent()

        # Add a margin
        if p_extent:
            if self._extent_margin:
                margin_x = p_extent.width() * self._extent_margin / 100
                margin_y = p_extent.height() * self._extent_margin / 100
                margin = max(margin_x, margin_y)
                p_extent = p_extent.buffered(margin)

            # Modify OWS WMS extent
            p_wms_extent = [
                p_extent.xMinimum(),
                p_extent.yMinimum(),
                p_extent.xMaximum(),
                p_extent.yMaximum(),
            ]
            p_wms_extent = [str(i) for i in p_wms_extent]
            self.project.writeEntry(WmsProjectProperty.Extent, '', p_wms_extent)

            # Zoom canvas to extent
            if self.iface:
                iface.mapCanvas().setExtent(p_extent)

        return p_extent
