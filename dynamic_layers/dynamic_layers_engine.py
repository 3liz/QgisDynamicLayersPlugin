"""
/***************************************************************************
 DynamicLayersEngine
                                 A QGIS plugin
 This plugin helps to change the datasource of chosen layers dynamically by searching and replacing user defined
 variables.
                              -------------------
        begin                : 2015-07-21
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Michaël Douchin - 3liz
        email                : mdouchin@3liz.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import typing
from string import Template

from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    QgsMapLayer,
    QgsProject,
    QgsExpression,
    QgsFeatureRequest,
    QgsMessageLog,
    QgsReadWriteContext,
    QgsVectorLayer,
    QgsRectangle,
)

from dynamic_layers.definitions import CustomProperty

try:
    from qgis.utils import iface
except Exception:
    iface = None

import re


class DynamicLayersTools:

    @staticmethod
    def search_and_replace_string_by_dictionary(string: str, dictionary: dict) -> str:
        """ String substitution. """
        return Template(string).substitute(dictionary)


class LayerDataSourceModifier:
    # Content of the dynamic datasource
    dynamic_datasource_content = None

    # Datasource can be changed from dynamicDatasourceContent or not
    dynamic_datasource_active = False

    def __init__(
            self,
            layer: QgsMapLayer,
    ):
        """
        Initialize class instance
        """
        if not layer:
            return

        self.layer = layer
        self.dynamic_datasource_active = layer.customProperty(CustomProperty.DynamicDatasourceActive) == str(True)
        self.dynamic_datasource_content = layer.customProperty(CustomProperty.DynamicDatasourceContent)

    def set_new_source_uri_from_dict(self, search_and_replace_dictionary: dict = None):
        """
        Get the dynamic datasource template,
        Replace variable with passed data,
        And set the layer datasource from this content if possible
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}

        # Set the new uri
        new_uri = DynamicLayersTools.search_and_replace_string_by_dictionary(
            self.dynamic_datasource_content, search_and_replace_dictionary)

        # Set the layer datasource
        self.set_data_source(new_uri)

        # Set other properties
        self.set_dynamic_layer_properties(search_and_replace_dictionary)

    def set_data_source(self, new_source_uri: str):
        """
        Method to apply a new datasource to a vector Layer
        """
        context = QgsReadWriteContext()
        new_ds, new_uri = self.split_source(new_source_uri)
        new_datasource_type = new_ds or self.layer.dataProvider().name()

        # read layer definition
        xml_document = QDomDocument("style")
        # XMLMapLayers = QDomElement()
        xml_map_layers = xml_document.createElement("maplayers")
        # XMLMapLayer = QDomElement()
        xml_map_layer = xml_document.createElement("maplayer")
        self.layer.writeLayerXml(xml_map_layer, xml_document, context)

        # apply layer definition
        xml_map_layer.firstChildElement("datasource").firstChild().setNodeValue(new_uri)
        xml_map_layer.firstChildElement("provider").firstChild().setNodeValue(new_datasource_type)
        xml_map_layers.appendChild(xml_map_layer)
        xml_document.appendChild(xml_map_layers)
        self.layer.readLayerXml(xml_map_layer, context)

        # Update layer extent
        self.layer.updateExtents()

        # Update graduated symbol renderer
        if self.layer.renderer() and self.layer.renderer().type() == 'graduatedSymbol':
            ranges = self.layer.renderer().ranges()
            if len(ranges) == 1:
                self.layer.renderer().updateClasses(self.layer, self.layer.renderer().mode(), len(ranges))

        # Reload layer
        self.layer.reload()

    @staticmethod
    def split_source(source: str) -> typing.Tuple[str, str]:
        """
        Split QGIS datasource into meaningful components
        """
        # TODO switch to QgsProviderRegistry.instance().decodeUri(layer.dataProvider().name(), layer.source())
        if "|" in source:
            datasource_type = source.split("|")[0]
            uri = source.split("|")[1].replace('\\', '/')
        else:
            datasource_type = None
            uri = source.replace('\\', '/')
        return datasource_type, uri

    def set_dynamic_layer_properties(self, search_and_replace_dictionary: dict = None):
        """
        Set layer title, abstract,
        and field aliases (for vector layers only)
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}

        # Layer title
        # First check that we have a title
        source_title = self.layer.name().strip()
        if self.layer.title().strip() != '':
            source_title = self.layer.title().strip()
        if self.layer.customProperty('titleTemplate') and self.layer.customProperty('titleTemplate').strip() != '':
            source_title = self.layer.customProperty('titleTemplate').strip()
        # Search and replace content
        self.layer.setTitle(
            DynamicLayersTools.search_and_replace_string_by_dictionary(
                source_title,
                search_and_replace_dictionary,
            ),
        )

        # Abstract
        source_abstract = ''
        if self.layer.abstract().strip() != '':
            source_abstract = self.layer.abstract().strip()
        if self.layer.customProperty('abstractTemplate') and self.layer.customProperty('abstractTemplate').strip() != '':
            source_abstract = self.layer.customProperty('abstractTemplate').strip()
        self.layer.setAbstract(
            DynamicLayersTools.search_and_replace_string_by_dictionary(
                source_abstract,
                search_and_replace_dictionary,
            ),
        )

        # Set fields aliases
        if self.layer.type() == QgsMapLayer.VectorLayer:
            for fid, field in enumerate(self.layer.fields()):
                alias = self.layer.attributeAlias(fid)
                if not alias:
                    continue
                new_alias = DynamicLayersTools.search_and_replace_string_by_dictionary(
                    alias,
                    search_and_replace_dictionary,
                )
                self.layer.setFieldAlias(fid, new_alias)


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
        val = DynamicLayersTools.search_and_replace_string_by_dictionary(val, self.search_and_replace_dictionary)

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
