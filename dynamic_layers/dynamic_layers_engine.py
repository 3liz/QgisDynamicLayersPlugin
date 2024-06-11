"""
/***************************************************************************
 DynamicLayersEngine
                                 A QGIS plugin
 This plugin helps to change the datasource of chosen layers dynamically by searching and replacing user defined variables.
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
from qgis.PyQt.QtXml import QDomDocument
from qgis.core import QgsMapLayer, QgsProject, QgsExpression, QgsFeatureRequest, QgsMessageLog

try:
    from qgis.utils import iface
except Exception:
    iface = None

import re


class DynamicLayersTools:

    @staticmethod
    def search_and_replace_string_by_dictionary(string='', dictionary=None):
        """
        Get the string,
        Replace variable such as {$VAR} with passed data,
        And returns the updated string
        """
        if dictionary is None:
            dictionary = {}
        # Check everything is ok
        if not string:
            return ''
        if not dictionary or not isinstance(dictionary, dict):
            return string

        # Create new string from original string by replacing via dic
        for k, v in dictionary.items():
            # Replace search string by value
            if v:
                r = re.compile('\{\$%s\}' % k, re.MULTILINE)
                string = r.sub('%s' % v, string)

        return string


class LayerDataSourceModifier:
    # Content of the dynamic datasource
    dynamic_datasource_content = None

    # Datasource can be changed from dynamicDatasourceContent or not
    dynamic_datasource_active = False

    def __init__(
            self,
            layer
    ):
        """
        Initialize class instance
        """
        if not layer:
            return

        self.layer = layer
        self.dynamic_datasource_active = (layer.customProperty('dynamicDatasourceActive') == 'True')
        self.dynamic_datasource_content = layer.customProperty('dynamicDatasourceContent')

    def set_new_source_uri_from_dict(self, search_and_replace_dictionary=None):
        """
        Get the dynamic datasource template,
        Replace variable with passed data,
        And set the layer datasource from this content if possible
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}
        # Get template uri
        uri_template = self.dynamic_datasource_content

        # Set the new uri
        t = DynamicLayersTools()
        new_uri = t.search_and_replace_string_by_dictionary(uri_template, search_and_replace_dictionary)

        # Set the layer datasource
        self.set_data_source(new_uri)

        # Set other properties
        self.set_dynamic_layer_properties(search_and_replace_dictionary)

    def set_data_source(self, new_source_uri):
        """
        Method to apply a new datasource to a vector Layer
        """
        layer = self.layer
        new_ds, new_uri = self.split_source(new_source_uri)
        new_datasource_type = new_ds or layer.dataProvider().name()

        # read layer definition
        xml_document = QDomDocument("style")
        # XMLMapLayers = QDomElement()
        xml_map_layers = xml_document.createElement("maplayers")
        # XMLMapLayer = QDomElement()
        xml_map_layer = xml_document.createElement("maplayer")
        layer.writeLayerXML(xml_map_layer, xml_document)

        # apply layer definition
        xml_map_layer.firstChildElement("datasource").firstChild().setNodeValue(new_uri)
        xml_map_layer.firstChildElement("provider").firstChild().setNodeValue(new_datasource_type)
        xml_map_layers.appendChild(xml_map_layer)
        xml_document.appendChild(xml_map_layers)
        layer.readLayerXML(xml_map_layer)

        # Update layer extent
        layer.updateExtents()

        # Update graduated symbol renderer
        if layer.rendererV2().type() == u'graduatedSymbol':
            if len(layer.rendererV2().ranges()) == 1:
                layer.rendererV2().updateClasses(layer, layer.rendererV2().mode(), len(layer.rendererV2().ranges()))

        # Reload layer
        layer.reload()

    @staticmethod
    def split_source(source):
        """
        Split QGIS datasource into meaningful components
        """
        if "|" in source:
            datasource_type = source.split("|")[0]
            uri = source.split("|")[1].replace('\\', '/')
        else:
            datasource_type = None
            uri = source.replace('\\', '/')
        return datasource_type, uri

    def set_dynamic_layer_properties(self, search_and_replace_dictionary=None):
        """
        Set layer title, abstract,
        and field aliases (for vector layers only)
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}
        layer = self.layer
        t = DynamicLayersTools()

        # Layer title
        # First check that we have a title
        source_title = layer.name().strip()
        if layer.title().strip() != '':
            source_title = layer.title().strip()
        if layer.customProperty('titleTemplate') and layer.customProperty('titleTemplate').strip() != '':
            source_title = layer.customProperty('titleTemplate').strip()
        # Search and replace content
        layer.setTitle(
            u"%s" % t.search_and_replace_string_by_dictionary(
                source_title,
                search_and_replace_dictionary
            )
        )

        # Abstract
        source_abstract = ''
        if layer.abstract().strip() != '':
            source_abstract = layer.abstract().strip()
        if layer.customProperty('abstractTemplate') and layer.customProperty('abstractTemplate').strip() != '':
            source_abstract = layer.customProperty('abstractTemplate').strip()
        layer.setAbstract(
            u"%s" % t.search_and_replace_string_by_dictionary(
                source_abstract,
                search_and_replace_dictionary
            )
        )

        # Set fields aliases
        if layer.type() == QgsMapLayer.VectorLayer:
            for fid, field in enumerate(layer.pendingFields()):
                alias = layer.attributeAlias(fid)
                if not alias:
                    continue
                new_alias = t.search_and_replace_string_by_dictionary(
                    alias,
                    search_and_replace_dictionary
                )
                layer.addAttributeAlias(fid, new_alias)


class DynamicLayersEngine:
    """
    Changes the layers datasource by using dynamicDatasourceContent
    as a template and replace variable with data given by the user
    """

    # Layer with the location to zoom in
    extentLayer = None

    # margin around the extent layer
    extentMargin = None

    # List of dynamic layers
    dynamicLayers = {}

    # Search and replace dictionary
    searchAndReplaceDictionary = {}

    def __init__(
            self,
            dynamic_layers=None,
            search_and_replace_dictionary=None,
            extent_layer=None,
            extent_margin=None
    ):
        """
        Dynamic Layers Engine constructor
        """
        if dynamic_layers is None:
            dynamic_layers = {}
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}
        self.extentLayer = extent_layer
        self.extentMargin = extent_margin
        self.dynamicLayers = dynamic_layers
        self.searchAndReplaceDictionary = search_and_replace_dictionary
        self.iface = iface

    def set_extent_layer(self, layer):
        """
        Set the extent layer.
        If a layer is set, the project extent will be changed to this extent
        """
        self.extentLayer = layer

    def set_extent_margin(self, margin):
        """
        Set the extent margin
        """
        margin = int(margin)
        if not margin:
            return
        self.extentMargin = margin

    def set_search_and_replace_dictionary(self, search_and_replace_dictionary):
        """
        Set the search and replace dictionary
        """
        self.searchAndReplaceDictionary = search_and_replace_dictionary

    def set_search_and_replace_dictionary_from_layer(self, layer, expression):
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
                'An error occurred while parsing the given expression: %s' % q_exp.parserErrorString())
            features = layer.getFeatures()

        # Get layer fields name
        fields = layer.pendingFields()
        field_names = [field.name() for field in fields]

        # Take only first feature
        for feat in features:
            # Build dictionary
            search_and_replace_dictionary = dict(zip(field_names, feat.attributes()))
            break

        self.searchAndReplaceDictionary = search_and_replace_dictionary

    def set_dynamic_layers_list(self):
        """
        Add the passed layers to the dynamic layers dictionary
        """
        # Get the layers with dynamicDatasourceActive enable
        lr = QgsProject.instance()
        self.dynamicLayers = dict([(lid, layer) for lid, layer in lr.mapLayers().items() if
                                   layer.customProperty('dynamicDatasourceActive') == 'True' and layer.customProperty(
                                       'dynamicDatasourceContent')])

    def set_dynamic_layers_datasource_from_dic(self):
        """
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionary
        """

        if not self.searchAndReplaceDictionary or not isinstance(self.searchAndReplaceDictionary, dict):
            return

        for lid, layer in self.dynamicLayers.items():
            # Change datasource
            a = LayerDataSourceModifier(layer)
            a.set_new_source_uri_from_dict(self.searchAndReplaceDictionary)

            if self.iface and layer.rendererV2().type() == u'graduatedSymbol':
                layer.triggerRepaint()

        if self.iface:
            self.iface.actionDraw().trigger()
            self.iface.mapCanvas().refresh()

    def set_dynamic_project_properties(self, title=None, abstract=None):
        """
        Set some project properties : title, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        """
        # Get project instance
        p = QgsProject.instance()

        # Make sure WMS Service is active
        if not p.readEntry('WMSServiceCapabilities', "/")[1]:
            p.writeEntry('WMSServiceCapabilities', "/", "True")

        # title
        if not title:
            xml = 'ProjectTitle'
            val = p.readEntry('PluginDynamicLayers', xml)
            if val:
                title = val[0]
        self.set_project_property('title', title)

        # abstract
        if not abstract:
            xml = 'ProjectAbstract'
            val = p.readEntry('PluginDynamicLayers', xml)
            if val:
                abstract = val[0]
        self.set_project_property('abstract', abstract)

    def set_project_property(self, prop, val):
        """
        Set a project property
        And replace variable if found in the properties
        """
        # Get project instance
        p = QgsProject.instance()

        # Replace variable in given val via dictionary
        t = DynamicLayersTools()
        val = t.search_and_replace_string_by_dictionary(val, self.searchAndReplaceDictionary)

        # Title
        if prop == 'title':
            p.writeEntry('WMSServiceTitle', '', u'%s' % val)

        # Abstract
        elif prop == 'abstract':
            p.writeEntry('WMSServiceAbstract', '', u'%s' % val)

    def set_project_extent(self):
        """
        Sets the project extent
        and corresponding XML property
        """
        p = QgsProject.instance()

        # Get extent from extent layer (if given)
        p_extent = None
        if self.extentLayer:
            self.extentLayer.updateExtents()
            p_extent = self.extentLayer.extent()
        else:
            if self.iface:
                p_extent = self.iface.mapCanvas().extent()
        if p_extent and p_extent.width() <= 0 and self.iface:
            p_extent = self.iface.mapCanvas().extent()

        # Add a margin
        if p_extent:
            if self.extentMargin:
                margin_x = p_extent.width() * self.extentMargin / 100
                margin_y = p_extent.height() * self.extentMargin / 100
                margin = max(margin_x, margin_y)
                p_extent = p_extent.buffer(margin)

            # Modify OWS WMS extent
            p_wms_extent = [
                u'%s' % p_extent.xMinimum(),
                u'%s' % p_extent.yMinimum(),
                u'%s' % p_extent.xMaximum(),
                u'%s' % p_extent.yMaximum(),
            ]
            p.writeEntry('WMSExtent', '', p_wms_extent)

            # Zoom canvas to extent
            if self.iface:
                iface.mapCanvas().setExtent(p_extent)

        return p_extent
