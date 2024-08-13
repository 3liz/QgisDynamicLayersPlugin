__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from typing import Annotated

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsMapLayer,
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
        self._extent_layer = None
        self._extent_margin = None
        self._dynamic_layers: dict = {}
        self._search_and_replace_dictionary: dict = {}
        self.iface = iface

    @property
    def extent_layer(self) -> QgsMapLayer:
        return self._extent_layer

    @extent_layer.setter
    def extent_layer(self, layer: QgsMapLayer):
        self._extent_layer = layer

    @property
    def extent_margin(self) -> int:
        return self._extent_margin

    @extent_margin.setter
    def extent_margin(self, extent: int):
        self._extent_margin = extent

    @property
    def search_and_replace_dictionary(self) -> dict:
        return self._search_and_replace_dictionary

    @search_and_replace_dictionary.setter
    def search_and_replace_dictionary(self, values: dict):
        self._search_and_replace_dictionary = values

    def set_search_and_replace_dictionary_from_layer(self, layer: QgsVectorLayer, expression: str):
        """ Set the search and replace dictionary from a given layer and an expression.

        The first found features is the data source
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
        self.search_and_replace_dictionary = dict(zip(layer.fields().names(), feature.attributes()))

    def set_dynamic_layers_from_project(self, project: QgsProject):
        """ Check all maplayers in the given project which are dynamic. """
        self._dynamic_layers = {
            lid: layer for lid, layer in project.mapLayers().items() if
            layer.customProperty(CustomProperty.DynamicDatasourceActive) and layer.customProperty(
                CustomProperty.DynamicDatasourceContent)
        }

    def set_dynamic_layers_datasource_from_dict(self):
        """
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionary
        """
        if len(self.search_and_replace_dictionary) < 1:
            return

        for lid, layer in self._dynamic_layers.items():
            # Change datasource
            a = LayerDataSourceModifier(layer)
            a.set_new_source_uri_from_dict(self.search_and_replace_dictionary)

            if not self.iface:
                continue

            if layer.renderer() and layer.renderer().type() == 'graduatedSymbol':
                layer.triggerRepaint()

        if not self.iface:
            return

        self.iface.actionDraw().trigger()
        self.iface.mapCanvas().refresh()

    def set_dynamic_project_properties(self, project: QgsProject):
        """
        Set some project properties : title, short name, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        """
        # Make sure WMS Service is active
        if not project.readEntry(WmsProjectProperty.Capabilities, "/")[1]:
            project.writeEntry(WmsProjectProperty.Capabilities, "/", True)

        # Title
        val = project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Title)
        if val:
            self.set_project_property(project, WmsProjectProperty.Title, val[0])

        # Shortname
        val = project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.ShortName)
        if val:
            self.set_project_property(project, WmsProjectProperty.ShortName, val[0])

        # Abstract
        val = project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Abstract)
        if val:
            self.set_project_property(project, WmsProjectProperty.Abstract, val[0])

    def set_project_property(self, project: QgsProject, project_property: Annotated[str, WmsProjectProperty], val: str):
        """
        Set a project property
        And replace variable if found in the properties
        """
        # Replace variable in given val via dictionary
        val = string_substitution(val, self.search_and_replace_dictionary)
        project.writeEntry(project_property, '', val)

    def set_project_extent(self, project: QgsProject) -> QgsRectangle:
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
            project.writeEntry(WmsProjectProperty.Extent, '', p_wms_extent)

            # Zoom canvas to extent
            if self.iface:
                iface.mapCanvas().setExtent(p_extent)

        return p_extent
