# -*- coding: utf-8 -*-
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
from PyQt4.QtCore import Qt, QSettings, QTranslator, qVersion, QCoreApplication
from PyQt4.QtGui import QAction, QIcon,QTableWidgetItem, QTextCursor, qApp
from PyQt4.QtXml import QDomDocument,QDomElement
from qgis.core import QgsMapLayerRegistry, QgsMapLayer, QgsProject
from qgis.utils import iface

import os.path
import sys
import re

class dynamicLayersTools():

    def searchAndReplaceStringByDictionary(self, string='', dictionary={}):
        '''
        Get the string,
        Replace variable such as {$VAR} with passed data,
        And returns the updated string
        '''
        # Check everything is ok
        if not string:
            return ''
        if not dictionary or not isinstance( dictionary, dict ):
            return string

        # Create new datasource uri from template
        for k, v in dictionary.items():
            # Replace search string by value
            if v:
                r = re.compile('\{\$%s\}' % k, re.MULTILINE)
                string = r.sub( '%s' % v, string )

        return string


class layerDataSourceModifier():

    # Content of the dynamic datasource
    dynamicDatasourceContent = None

    # Datasource can be changed from dynamicDatasourceContent or not
    dynamicDatasourceActive = False

    def __init__(
            self,
            layer
        ):
        '''
        Initialize class instance
        '''
        if not layer:
            return
        self.layer = layer

        self.dynamicDatasourceActive = layer.customProperty('dynamicDatasourceActive') == 'True'
        self.dynamicDatasourceContent = layer.customProperty( 'dynamicDatasourceContent')


    def setNewSourceUriFromDict( self, searchAndReplaceDictionary={} ):
        '''
        Get the dynamic datasource template,
        Replace variable with passed data,
        And set the layer datasource from this content if possible
        '''
        # Get template uri
        uriTemplate = self.dynamicDatasourceContent

        # Set the new uri
        t = dynamicLayersTools()
        newUri = t.searchAndReplaceStringByDictionary( uriTemplate, searchAndReplaceDictionary )

        # Set the layer datasource
        self.setDataSource( newUri )


    def setDataSource( self, newSourceUri):
        '''
        Method to apply a new datasource to a vector Layer
        '''
        layer = self.layer
        newDS, newUri = self.splitSource(newSourceUri)
        newDatasourceType = newDS or layer.dataProvider().name()

        # read layer definition
        XMLDocument = QDomDocument("style")
        XMLMapLayers = QDomElement()
        XMLMapLayers = XMLDocument.createElement("maplayers")
        XMLMapLayer = QDomElement()
        XMLMapLayer = XMLDocument.createElement("maplayer")
        layer.writeLayerXML(XMLMapLayer,XMLDocument)

        # apply layer definition
        XMLMapLayer.firstChildElement("datasource").firstChild().setNodeValue(newUri)
        XMLMapLayer.firstChildElement("provider").firstChild().setNodeValue(newDatasourceType)
        XMLMapLayers.appendChild(XMLMapLayer)
        XMLDocument.appendChild(XMLMapLayers)
        layer.readLayerXML(XMLMapLayer)

        layer.updateExtents()
        layer.reload()

    def splitSource (self,source):
        '''
        Split QGIS datasource into meaningfull components
        '''
        if "|" in source:
            datasourceType = source.split("|")[0]
            uri = source.split("|")[1].replace('\\','/')
        else:
            datasourceType = None
            uri = source.replace('\\','/')
        return (datasourceType,uri)


class DynamicLayersEngine():
    '''
    Changes the layers datasource by using dynamicDatasourceContent
    as a template and replace variable with data given by the user
    '''

    # Layer with the location to zoom in
    extentLayer = None

    # margin around the extent layer
    extentMargin = None

    # List of dynamic layers
    dynamicLayers = {}

    # Search and replace dictionnary
    searchAndReplaceDictionary = {}

    def __init__(
            self,
            dynamicLayers={},
            searchAndReplaceDictionary={},
            extentLayer=None,
            extentMargin=None
        ):
        '''
        Dynamic Layers Engine constructor
        '''
        self.extentLayer = extentLayer
        self.extentMargin = extentMargin
        self.dynamicLayers = dynamicLayers
        self.searchAndReplaceDictionary = searchAndReplaceDictionary
        self.iface = iface


    def setExtentLayer( self, layer ):
        '''
        Set the extent layer.
        If a layer is set, the project extent will be changed to this extent
        '''
        self.extentLayer = layer

    def setExtentMargin( self, margin ):
        '''
        Set the extent margin
        '''
        margin = int(margin)
        if not margin:
            return
        self.extentMargin = margin

    def setSearchAndReplaceDictionary(self, searchAndReplaceDictionary):
        '''
        Set the search and replace dictionary
        '''
        self.searchAndReplaceDictionary = searchAndReplaceDictionary


    def setDynamicLayersList( self, layers=[] ):
        '''
        Add the passed layers to the dynamic layers dictionnary
        '''
        for layer in layers:
            if layer.id() not in self.dynamicLayers:
                self.dynamicLayers[ layer.id() ] = layer


    def setDynamicLayersDatasourceFromDic(self ):
        '''
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionnary
        '''

        if not self.searchAndReplaceDictionary or not isinstance(self.searchAndReplaceDictionary, dict):
            return

        for id,layer in self.dynamicLayers.items():
            print layer.name()
            a = layerDataSourceModifier( layer )
            a.setNewSourceUriFromDict( self.searchAndReplaceDictionary )

        self.iface.actionDraw().trigger()
        self.iface.mapCanvas().refresh()


    def setDynamicProjectProperties(self):
        '''
        Set some project properties : title, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        '''
        # Get project instance
        p = QgsProject.instance()

        # Make sure WMS Service is active
        if not p.readEntry('WMSServiceCapabilities', "/")[1]:
            p.writeEntry('WMSServiceCapabilities', "/", "True")

        # title
        xml = 'ProjectTitle'
        val = p.readEntry('PluginDynamicLayers' , xml)
        if val:
            val = val[0]
            self.setProjectProperty( 'title', val)

        # abstract
        xml = 'ProjectAbstract'
        val = p.readEntry('PluginDynamicLayers' , xml)
        if val:
            val = val[0]
            self.setProjectProperty( 'abstract', val)


    def setProjectProperty( self, prop, val):
        '''
        Set a project property
        And replace variable if found in the properties
        '''
        # Get project instance
        p = QgsProject.instance()

        # Replace variable in given val via dictionary
        t = dynamicLayersTools()
        val = t.searchAndReplaceStringByDictionary( val, self.searchAndReplaceDictionary )

        # Title
        if prop == 'title':
            p.writeEntry('WMSServiceTitle', '', u'%s' % val)

        # Abstract
        elif prop == 'abstract':
            p.writeEntry('WMSServiceAbstract', '', u'%s' % val)



    def setProjectExtent( self ):
        '''
        Sets the project extent
        and corresponding XML property
        '''
        p = QgsProject.instance()

        # Get extent from extent layer (if given)
        pextent = None
        if self.extentLayer:
            pextent = self.extentLayer.extent()
        else:
            pextent = self.iface.mapCanvas().extent()
        if pextent.width() <= 0:
            pextent = self.iface.mapCanvas().extent()

        # Add a margin
        if self.extentMargin:
            marginX = pextent.width() * self.extentMargin / 100
            marginY = pextent.height() * self.extentMargin / 100
            margin = max( marginX, marginY )
            pextent = pextent.buffer( margin )

        # Modify OWS WMS extent
        pWmsExtent = []
        pWmsExtent.append(u'%s' % pextent.xMinimum())
        pWmsExtent.append(u'%s' % pextent.yMinimum())
        pWmsExtent.append(u'%s' % pextent.xMaximum())
        pWmsExtent.append(u'%s' % pextent.yMaximum())
        p.writeEntry('WMSExtent', '', pWmsExtent)

        # Zoom canvas to extent
        iface.mapCanvas().setExtent( pextent )


    def saveChildProject( self ):
        '''
        Save a project into a new file
        '''
        origFileName = QgsProject.instance().fileName()
        if origFileName:
            suffix = '_'.join( ["%s_%s" % (k,v) for k,v in self.searchAndReplaceDictionary.items()] )
            newFileName = origFileName.replace('.qgs', '_%s.qgs' % suffix )

            QgsProject.instance().setFileName( newFileName )
            QgsProject.instance().write()
            QgsProject.instance().setFileName(origFileName)
            QgsProject.instance().dirty(0)
