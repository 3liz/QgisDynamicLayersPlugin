__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import typing

from qgis.core import (
    QgsMapLayer,
    QgsProject,
    QgsExpression,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsVectorLayer,
    QgsRectangle,
)

from dynamic_layers.core.layer_datasource_modifier import LayerDataSourceModifier
from dynamic_layers.definitions import CustomProperty
from dynamic_layers.tools import string_substitution

from qgis.utils import iface


class DynamicLayersEngine:
    """
    Changes the layers datasource by using dynamicDatasourceContent
    as a template and replace variable with data given by the user
    """

    # Layer with the location to zoom in
    extent_layer = None

    # margin around the extent layer
    extent_margin = None

    # List of dynamic layers
    dynamic_layers: typing.ClassVar = {}

    # Search and replace dictionary
    search_and_replace_dictionary: typing.ClassVar = {}

    def __init__(
            self,
            dynamic_layers: dict = None,
            search_and_replace_dictionary: dict = None,
            extent_layer: list = None,
            extent_margin: int = None,
    ):
        """
        Dynamic Layers Engine constructor
        """
        if dynamic_layers is None:
            dynamic_layers = {}
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}
        self.extent_layer = extent_layer
        self.extent_margin = extent_margin
        self.dynamic_layers = dynamic_layers
        self.search_and_replace_dictionary = search_and_replace_dictionary
        self.iface = iface

    def set_extent_layer(self, layer: QgsMapLayer):
        """
        Set the extent layer.
        If a layer is set, the project extent will be changed to this extent
        """
        self.extent_layer = layer

    def set_extent_margin(self, margin: int):
        """
        Set the extent margin
        """
        margin = int(margin)
        if not margin:
            return
        self.extent_margin = margin

    def set_search_and_replace_dictionary(self, search_and_replace_dictionary: dict):
        """
        Set the search and replace dictionary
        """
        self.search_and_replace_dictionary = search_and_replace_dictionary

    def set_search_and_replace_dictionary_from_layer(self, layer: QgsVectorLayer, expression: str):
        """
        Set the search and replace dictionary
        from a given layer
        and an expression.
        The first found features is the data source
        """
        search_and_replace_dictionary = {}

        # Get and validate expression
        q_exp = QgsExpression(expression)
        if not q_exp.hasParserError():
            q_req = QgsFeatureRequest(q_exp)
            features = layer.getFeatures(q_req)
        else:
            QgsMessageLog.logMessage(
                f'An error occurred while parsing the given expression: {q_exp.parserErrorString()}')
            features = layer.getFeatures()

        # Take only first feature
        for feat in features:
            # Build dictionary
            search_and_replace_dictionary = dict(zip(layer.fields().names(), feat.attributes()))
            break

        self.search_and_replace_dictionary = search_and_replace_dictionary

    def set_dynamic_layers_list(self, project: QgsProject):
        """
        Add the passed layers to the dynamic layers dictionary
        """
        # Get the layers with dynamicDatasourceActive enable
        self.dynamic_layers = {
            lid: layer for lid, layer in project.mapLayers().items() if
            layer.customProperty(CustomProperty.DynamicDatasourceActive) == str(True) and layer.customProperty(
                CustomProperty.DynamicDatasourceContent)
        }

    def set_dynamic_layers_datasource_from_dic(self):
        """
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionary
        """

        if not self.search_and_replace_dictionary or not isinstance(self.search_and_replace_dictionary, dict):
            return

        for lid, layer in self.dynamic_layers.items():
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

    def set_dynamic_project_properties(self, project: QgsProject, title: str = None, abstract: str = None):
        """
        Set some project properties : title, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        """
        # Make sure WMS Service is active
        if not project.readEntry('WMSServiceCapabilities', "/")[1]:
            project.writeEntry('WMSServiceCapabilities', "/", "True")

        # title
        if not title:
            xml = 'ProjectTitle'
            val = project.readEntry('PluginDynamicLayers', xml)
            if val:
                title = val[0]
        self.set_project_property(project, 'title', title)

        # abstract
        if not abstract:
            xml = 'ProjectAbstract'
            val = project.readEntry('PluginDynamicLayers', xml)
            if val:
                abstract = val[0]
        self.set_project_property(project, 'abstract', abstract)

    def set_project_property(self, project: QgsProject, prop: str, val: str):
        """
        Set a project property
        And replace variable if found in the properties
        """
        # Replace variable in given val via dictionary
        val = string_substitution(val, self.search_and_replace_dictionary)

        # Title
        if prop == 'title':
            project.writeEntry('WMSServiceTitle', '', val)

        # Abstract
        elif prop == 'abstract':
            project.writeEntry('WMSServiceAbstract', '', val)

    def set_project_extent(self, project: QgsProject) -> QgsRectangle:
        """
        Sets the project extent
        and corresponding XML property
        """
        # Get extent from extent layer (if given)
        p_extent = None
        if self.extent_layer:
            self.extent_layer.updateExtents()
            p_extent = self.extent_layer.extent()
        else:
            if self.iface:
                p_extent = self.iface.mapCanvas().extent()
        if p_extent and p_extent.width() <= 0 and self.iface:
            p_extent = self.iface.mapCanvas().extent()

        # Add a margin
        if p_extent:
            if self.extent_margin:
                margin_x = p_extent.width() * self.extent_margin / 100
                margin_y = p_extent.height() * self.extent_margin / 100
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
            project.writeEntry('WMSExtent', '', p_wms_extent)

            # Zoom canvas to extent
            if self.iface:
                iface.mapCanvas().setExtent(p_extent)

        return p_extent
