# -*- coding: utf-8 -*-

"""
***************************************************************************
    QGIS Server Dynamic Layers Filters:
    This plugins builds a child project from a parent project and some
    parameters and send the new project path in the MAP parameter
    ---------------------
    Date                 : October 2015
    Copyright            : (C) 2014-2015 by Michaël DOUCHIN
    Email                : mdouchin at 3liz dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.server import *
from qgis.core import QgsProject, QgsMessageLog, QgsLogger, QgsMapLayerRegistry, QgsLayerTreeModel, QgsLayerTreeUtils, QgsComposition
from qgis.gui import QgsMapCanvas, QgsLayerTreeMapCanvasBridge, QgsLayerTreeView
from DynamicLayers.dynamic_layers_engine import DynamicLayersEngine
from PyQt4.QtCore import QFileInfo
from PyQt4.QtXml import QDomDocument
import os.path, re, json, time

class DynamicLayersFilter(QgsServerFilter):

    def __init__(self, serverIface):
        super(DynamicLayersFilter, self).__init__(serverIface)
        self.serverIface = serverIface
        self.canvas = None
        self.project = None
        self.projectPath = None
        self.childPath = None
        self.layerIdSuffix = None
        self.extent = None
        self.searchAndReplaceDictionary = None



    def responseComplete(self):
        request = self.serverIface.requestHandler()
        params = request.parameterMap( )

        # Check if dynamic layers params are passed
        # If not, do not change QGIS Server response
        if params['SERVICE'].lower() != 'dynamiclayers':
            return

        # Check if needed params are set
        if 'DLSOURCELAYER' not in params or 'DLEXPRESSION' not in params:
            # Change response
            request.clearHeaders()
            request.setInfoFormat('text/json')
            request.setHeader('Status', '200')
            request.setHeader('Content-type', 'text/json')
            request.clearBody()
            body = {
                'status': 0,
                'message': 'Missing parameters DLSOURCELAYER or DLEXPRESSION',
                'childProject': None
            }
            request.appendBody( json.dumps( body ) )
            return

        # Get layer and expression
        player = params['DLSOURCELAYER']
        pexp = params['DLEXPRESSION']
        #~ QgsMessageLog.logMessage( "DynamicLayers - layer = %s  - expression = %s" % ( player, pexp ))

        # Open project
        pmap = params['MAP']
        self.projectPath = pmap
        pfile = QFileInfo( pmap )
        p = QgsProject.instance()

        # Define canvas and layer treet root
        # Needed to write canvas and layer-tree-root in project file
        canvas = QgsMapCanvas()
        treeRoot = p.layerTreeRoot()
        bridge = QgsLayerTreeMapCanvasBridge( treeRoot, canvas )
        bridge.setCanvasLayers()
        canvas.zoomToFullExtent()
        self.canvas = canvas
        self.bridge = bridge
        self.composers = []
        self.project = p
        self.project.readProject.connect( bridge.readProject )
        self.project.readProject.connect( self.loadComposersFromProject )
        self.project.writeProject.connect( bridge.writeProject )
        self.project.writeProject.connect( self.writeOldLegend )
        self.project.writeProject.connect( self.writeComposers )
        
        # read project
        p.read( pfile )

        # Get an instance of engine class
        dle = DynamicLayersEngine()

        # Set the dynamic layers list
        dle.setDynamicLayersList()
        if not dle.dynamicLayers:
            QgsMessageLog.logMessage( "DynamicLayers - no dynamic layers found")
            # Change response
            request.clearHeaders()
            request.setInfoFormat('text/json')
            request.setHeader('Status', '200')
            request.setHeader('Content-type', 'text/json')
            request.setHeader('Content-Disposition', 'attachment; filename="DynamicLayers.json"')
            request.clearBody()
            body = {
                'status': 0,
                'message': 'No dynamic layers found in parent project',
                'childProject': None
            }
            request.appendBody( json.dumps( body ) )
            return


        # Set search and replace dictionary
        lr = QgsMapLayerRegistry.instance()
        sourceLayerList = [ layer for lname,layer in lr.mapLayers().items() if layer.name() == player ]
        if len(sourceLayerList ) != 1:
            QgsMessageLog.logMessage( "DynamicLayers - source layer not in project")
            # Change response
            request.clearHeaders()
            request.setInfoFormat('text/json')
            request.setHeader('Status', '200')
            request.setHeader('Content-type', 'text/json')
            request.setHeader('Content-Disposition', 'attachment; filename="DynamicLayers.json"')
            request.clearBody()
            body = {
                'status': 0,
                'message': 'The source layer cannot be found in the project',
                'childProject': None
            }
            request.appendBody( json.dumps( body ) )
            return

        sourceLayer = sourceLayerList[0]
        dle.setSearchAndReplaceDictionaryFromLayer( sourceLayer, pexp )
        self.searchAndReplaceDictionary = dle.searchAndReplaceDictionary

        # Get child name computed path, and check if it is already there or not
        childPath = self.getChildProjectName( pmap, player, pexp )
        self.childPath = childPath
        if os.path.exists( childPath ):
            if os.path.getmtime( childPath ) > os.path.getmtime( pmap ):
                QgsMessageLog.logMessage( 'DynamicLayer - Parent older than child : do not recreate child project')

                # Change response
                request.clearHeaders()
                request.setInfoFormat('text/json')
                request.setHeader('Status', '200')
                request.setHeader('Content-type', 'text/json')
                request.setHeader('Content-Disposition', 'attachment; filename="DynamicLayers.json"')
                request.clearBody()
                body = {
                    'status': 1,
                    'message': 'Child project is already up-to-date',
                    'childProject': os.path.basename(childPath)
                }
                request.appendBody( json.dumps( body ) )
                return
            else:
                QgsMessageLog.logMessage( 'DynamicLayer - Must recreate the child project')

        # Change layers datasource
        dle.setDynamicLayersDatasourceFromDic( )

        # Set project properties
        dle.setDynamicProjectProperties()

        # Set extent layer
        extentLayerIdGet = p.readEntry('PluginDynamicLayers' , 'ExtentLayer')
        if extentLayerIdGet:
            extentLayerId = extentLayerIdGet[0]
            extentLayerList = [ layer for lid,layer in lr.mapLayers().items() if layer.id() == extentLayerId ]

            if len(extentLayerList) == 1:
                dle.setExtentLayer( extentLayerList[0] )

                # Set extent margin
                extentMarginGet = p.readEntry('PluginDynamicLayers' , 'ExtentMargin')
                if extentMarginGet:
                    extentMargin = int( extentMarginGet[0] )
                else:
                    extentMargin = 20
                dle.setExtentMargin( extentMargin )

                # Set new extent
                newExtent = dle.setProjectExtent()
                self.extent = newExtent

                # Zoom to extent Layer
                if newExtent:
                    self.canvas.setExtent( newExtent )

        # Create suffix to append after layers id
        # prevent cache issues
        self.layerIdSuffix = int( time.time() )

        # Save child project
        childProject = self.saveChildProject()

        # Save child project lizmap configuration
        if os.path.exists( self.projectPath + '.cfg' ):
            self.writeLizmapChildProjectConfig()

        if childProject:
            # Change response
            request.clearHeaders()
            request.setInfoFormat('text/json')
            request.setHeader('Status', '200')
            request.setHeader('Content-type', 'text/json')
            request.setHeader('Content-Disposition', 'attachment; filename="DynamicLayers.json"')
            request.clearBody()
            body = {
                'status': 1,
                'message': 'Child project has been updated',
                'childProject': os.path.basename(childPath)
            }
            request.appendBody( json.dumps( body ) )
        else:
            # Change response
            request.clearHeaders()
            request.setInfoFormat('text/json')
            request.setHeader('Status', '200')
            request.setHeader('Content-type', 'text/json')
            request.setHeader('Content-Disposition', 'attachment; filename="DynamicLayers.json"')
            request.clearBody()
            body = {
                'status': 0,
                'message': 'Error while creating child project',
                'childProject': None
            }
            request.appendBody( json.dumps( body ) )

        return


    def getChildProjectName( self, pmap, player, pexp ):
        '''
        Build the child project path name
        from given parameters
        '''
        childPath = None
        pattern = re.compile('[\W_]+')
        suffix = '_' + pattern.sub( '_', player ) + '_' + pattern.sub( '', pexp )
        childPath = pmap.replace('.qgs', '_%s.qgs' % suffix )
        return childPath


    def saveChildProject( self ):
        '''
        Save a project into a new file
        '''
        path = None
        if QgsProject.instance().write( QFileInfo( self.childPath ) ):
            QgsMessageLog.logMessage( "Success writing the child project: %s" % self.childPath )
            path = self.childPath
        else:
            QgsMessageLog.logMessage( "Error while writing the child project: %s" % self.childPath )
            return None

        # Change ids
        with open( self.childPath) as fin:
            data = fin.read().decode("utf-8-sig")
            with open(self.childPath, 'w') as fout:
                data = self.replaceLayersId( data )
                data = data.encode('utf-8')
                fout.write(data)

        return path

    def writeOldLegend( self, doc ):
        '''
        Add old legend to project XML
        '''
        treeRoot = self.project.layerTreeRoot()
        oldLegendElem = QgsLayerTreeUtils.writeOldLegend( doc, treeRoot,
                        self.bridge.hasCustomLayerOrder(), self.bridge.customLayerOrder() )
        doc.firstChildElement( "qgis" ).appendChild( oldLegendElem )

    def loadComposersFromProject( self, doc ):
        '''
        Load composers from project document
        '''
        composerNodeList = doc.elementsByTagName( "Composer" );
        i = 0
        while i < composerNodeList.size() :
            composerElem = composerNodeList.at(i).toElement()
            title = composerElem.attribute( "title" )
            visible = composerElem.attribute( "visible" )
            composition = QgsComposition( self.canvas.mapSettings() );
            compositionNodeList = composerElem.elementsByTagName( "Composition" )
            if compositionNodeList.size() > 0 :
                compositionElem = compositionNodeList.at( 0 ).toElement();
                composition.readXML( compositionElem, doc );
                atlasElem = composerElem.firstChildElement( "Atlas" );
                composition.atlasComposition().readXML( atlasElem, doc );
                composition.addItemsFromXML( composerElem, doc );
                composition.atlasComposition().readXMLMapSettings( atlasElem, doc );
            self.composers.append({
                'title': title,
                'visible': visible,
                'composition': composition
            })
            i += 1

    def writeComposers( self, doc ):
        '''
        Write composers to project document
        '''
        nl = doc.elementsByTagName( "qgis" );
        if nl.count() < 1:
            return
        qgisElem = nl.at( 0 ).toElement();
        if qgisElem.isNull():
            return
        for composer in self.composers:
            composerElem = doc.createElement( "Composer" );
            composerElem.setAttribute( "title", composer['title'] );
            composerElem.setAttribute( "visible", composer['visible'] );
            qgisElem.appendChild( composerElem );
            composer['composition'].writeXML( composerElem, doc );
            composer['composition'].atlasComposition().writeXML( composerElem, doc );

    def replaceLayersId( self, projectXmlString ):
        '''
        Replace all layers ids by random ids
        to prevent server cache problems
        '''
        lr = QgsMapLayerRegistry.instance()

        for lid, layer in lr.mapLayers().items():
            if layer.customProperty('dynamicDatasourceActive') == 'True':
                r = re.compile( '%s' % lid, re.MULTILINE )
                projectXmlString = r.sub( lid + '%s' % self.layerIdSuffix, projectXmlString )

        return projectXmlString


    def writeLizmapChildProjectConfig( self ):
        '''
        Get parent project lizmap configuration
        make necessary changes
        and write the child project configuration
        '''

        lr = QgsMapLayerRegistry.instance()

        with open( self.projectPath + '.cfg' ) as fin:
            # Read as json
            data = fin.read().decode("utf-8-sig")
            sjson = json.loads( data )

            # Get new project extent
            pextent = self.canvas.extent()
            pextent = self.extent
            sjson['options']['initialExtent'] = [
                pextent.xMinimum(),
                pextent.yMinimum(),
                pextent.xMaximum(),
                pextent.yMaximum()
            ]
            sjson['options']['bbox'] = [
                pextent.xMinimum(),
                pextent.yMinimum(),
                pextent.xMaximum(),
                pextent.yMaximum()
            ]

            # Change extent for each layer
            for lid, layer in lr.mapLayers().items():
                if layer.customProperty('dynamicDatasourceActive') == 'True':
                    layer.updateExtents()
                    lExtent = layer.extent()
                    lname = "%s" % unicode( layer.name() )
                    sjson['layers'][lname]["extent"] = eval(
                        '[%s, %s, %s, %s]' % (
                            lExtent.xMinimum(),
                            lExtent.yMinimum(),
                            lExtent.xMaximum(),
                            lExtent.yMaximum()
                        )
                    )

            jsonFileContent = json.dumps(
                sjson,
                sort_keys=False,
                indent=4
            )

            # Change layer ids globally
            jsonFileContent = self.replaceLayersId( jsonFileContent )

            # Search and replace variables
            t = dynamicLayersTools()
            jsonFileContent = t.searchAndReplaceStringByDictionary( jsonFileContent, self.searchAndReplaceDictionary ) 

            # Write child project config file
            with open( self.childPath + '.cfg' , 'w') as fout:
                fout.write( jsonFileContent.encode('utf-8') )



