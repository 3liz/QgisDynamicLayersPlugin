"""
/***************************************************************************
 DynamicLayers
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
from qgis.PyQt.QtCore import Qt, QSettings, QTranslator, qVersion, QCoreApplication
from qgis.PyQt.QtGui import QAction, QIcon, QTextCursor, QColor
from qgis.PyQt.QtWidgets import QTableWidgetItem, qApp
from qgis.core import QgsMapLayer, QgsProject, QgsFeatureRequest, QgsExpression, QgsMessageLog, QgsLogger

# Import the code for the dialog
from dynamic_layers.dynamic_layers_dialog import DynamicLayersDialog
import os.path
import datetime
from functools import partial
import sys
import re
try:
    from qgis.server import *
except:
    pass

from dynamic_layers.dynamic_layers_engine import *


class DynamicLayers:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'DynamicLayers_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = DynamicLayersDialog()

        # Layers attribute that can be shown and optionally changed in the plugin
        self.layersTable =  {
            'tableWidget': self.dlg.twLayers,
            'attributes': [
                {'key': 'id', 'editable': False },
                {'key': 'name', 'editable': False, 'type': 'string'},
                {'key': 'dynamicDatasourceActive', 'editable': False, 'type': 'string'}
            ]
        }

        # Keep record of style widget
        self.selectedLayerWidget = None
        self.selectedLayer = None

        # Variables
        self.variableList = []

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Dynamic Layers')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'DynamicLayers')
        self.toolbar.setObjectName(u'DynamicLayers')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('DynamicLayers', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/DynamicLayers/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Dynamic Layers'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # slots/signals
        ###############
        self.initDone = False

        # Actions when row selection changes
        slot = self.onRowSelectionChanged
        table = self.layersTable['tableWidget']
        sm = table.selectionModel()
        sm.selectionChanged.connect( slot )

        # Actions when the layer properties are changed panel
        self.dlg.cbDatasourceActive.stateChanged.connect( self.onCbDatasourceActiveChange )
        self.dlg.btCopyFromLayer.clicked.connect( self.onCopyFromLayer )

        self.layerPropertiesInputs = {
            'datasource': {
                'widget': self.dlg.dynamicDatasourceContent,
                'wType': 'textarea',
                'xml': 'dynamicDatasourceContent'
            },
            'title': {
                'widget': self.dlg.titleTemplate,
                'wType': 'text',
                'xml': 'titleTemplate'
            },
            'abstract': {
                'widget': self.dlg.abstractTemplate,
                'wType': 'textarea',
                'xml': 'abstractTemplate'
            }
        }
        for key, item in self.layerPropertiesInputs.items():
            control = item['widget']
            slot = partial( self.onLayerPropertyChange, key )
            control.textChanged.connect( slot )


        # Actions of the Variable tab
        self.dlg.btAddVariable.clicked.connect( self.onAddVariableClicked )
        self.dlg.btRemoveVariable.clicked.connect( self.onRemoveVariableClicked )

        # Apply buttons
        slot = partial( self.onApplyVariablesClicked, 'table' )
        self.dlg.btApplyVariables.clicked.connect( slot )
        slot = partial( self.onApplyVariablesClicked, 'layer' )
        self.dlg.btApplyFromLayer.clicked.connect( slot )

        # Project properties tab
        self.dlg.btCopyFromProject.clicked.connect( self.onCopyFromProjectClicked )

        self.projectPropertiesInputs = {
            'title' : {
                'widget' : self.dlg.inProjectTitle,
                'wType': 'text',
                'xml': 'ProjectTitle'
            },
            'abstract' : {
                'widget' : self.dlg.inProjectAbstract,
                'wType': 'textarea',
                'xml': 'ProjectAbstract'
            },
            'extentLayer' : {
                'widget' : self.dlg.inExtentLayer,
                'wType': 'list',
                'xml': 'ExtentLayer'
            },
            'extentMargin' : {
                'widget' : self.dlg.inExtentMargin,
                'wType': 'spinbox',
                'xml': 'ExtentMargin'
            },
            'variableSourceLayer' : {
                'widget' : self.dlg.inVariableSourceLayer,
                'wType': 'list',
                'xml': 'VariableSourceLayer'
            },
            'variableSourceLayerExpression' : {
                'widget' : self.dlg.inVariableSourceLayerExpression,
                'wType': 'text',
                'xml': 'VariableSourceLayerExpression'
            },
        }
        for key, item in self.projectPropertiesInputs.items():
            slot = partial( self.onProjectPropertyChanged, key )
            control = item['widget']
            if item['wType'] in ('text', 'spinbox'):
                control.editingFinished.connect(slot)
            elif item['wType'] == 'textarea':
                control.textChanged.connect(slot)
            elif item['wType'] == 'checkbox':
                control.stateChanged.connect(slot)
            elif item['wType'] == 'list':
                control.currentIndexChanged.connect(slot)

        # Log
        self.dlg.btClearLog.clicked.connect( self.clearLog )


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Dynamic Layers'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def clearLog(self):
        '''
        Clear the log
        '''
        self.dlg.txtLog.clear()

    def updateLog(self, msg):
        '''
        Update the log
        '''
        t = self.dlg.txtLog
        t.ensureCursorVisible()
        prefix = '<span style="font-weight:normal;">'
        suffix = '</span>'
        t.append( '%s %s %s' % (prefix, msg, suffix) )
        c = t.textCursor()
        c.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)
        t.setTextCursor(c)
        qApp.processEvents()

    def populateLayerTable( self ):
        """
        Fill the table for a given layer type
        """
        # Get parameters for the widget
        lt = self.layersTable
        table = lt['tableWidget']

        attributes = lt['attributes']

        headerData = [ a['key'] for a in attributes ]

        # empty previous content
        for row in range(table.rowCount()):
            table.removeRow(row)
        table.setRowCount(0)

        # create columns and header row
        columns = [ a['key'] for a in attributes ]
        colCount = len( columns )
        table.setColumnCount( colCount )
        table.setHorizontalHeaderLabels( tuple( columns ) )

        # load content from project layers
        lr = QgsProject.instance()
        for lid in lr.mapLayers():
            layer = lr.mapLayer( lid )

            lineData = []

            # Set row and column count
            twRowCount = table.rowCount()
            # add a new line
            table.setRowCount( twRowCount + 1 )
            table.setColumnCount( colCount )
            i=0

            if layer.customProperty('dynamicDatasourceActive') == 'True':
                bg = QColor(175, 208, 126)
            else:
                bg = Qt.transparent

            # get information
            for attr in attributes:
                newItem = QTableWidgetItem( )

                # Is editable or not
                if( attr['editable'] ):
                    newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled )
                else:
                    newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled  )

                # background
                newItem.setBackground( bg )

                # Item value
                value = self.getLayerProperty( layer, attr['key'] )
                newItem.setData( Qt.EditRole, value )

                # Add cell data to lineData
                # encode it in the file system encoding, only if needed
                if hasattr( value, 'encode' ):
                    value = value.encode( sys.getfilesystemencoding() )
                lineData.append( value )

                # Add item
                table.setItem(twRowCount, i, newItem)
                i+=1


    def getLayerProperty( self, layer, prop ):
        """
        Get a layer property
        """

        if prop == 'id':
            return layer.id()

        if prop == 'name':
            return layer.name()

        elif prop == 'uri':
            return layer.dataProvider().dataSourceUri().split('|')[0]

        elif prop == 'dynamicDatasourceActive':
            a = layer.customProperty( 'dynamicDatasourceActive')
            return a

        elif prop == 'dynamicDatasourceContent':
            a = layer.customProperty( 'dynamicDatasourceContent')
            return a

        else:
            return None

    def onRowSelectionChanged( self ):
        '''
        Change content of dynamic properties group inputs
        When the user selects a layer in the table
        '''
        if not self.initDone:
            return

        showLayerProperties = True

        # Get layers table
        lt = self.layersTable
        table = lt['tableWidget']

        # Get selected lines
        sm = table.selectionModel()
        lines = sm.selectedRows()
        if not lines:
            return

        layer = None
        self.selectedLayer = None
        isActive = False

        if showLayerProperties:
            row = lines[0].row()

            # Get layer
            layerId = table.item( row, 0 ).data( Qt.EditRole )
            lr = QgsProject.instance()
            layer = lr.mapLayer( layerId )
            if not layer:
                showLayerProperties = False
            else:
                self.selectedLayer = layer

        if len( lines ) != 1:
            showLayerProperties = False

        # Toggle the layer properties group
        self.dlg.gbLayerDynamicProperties.setEnabled( showLayerProperties )

        # Set the content of the layer properties inputs
        # dynamic datasource text input content
        if layer:
            isActive = layer.customProperty('dynamicDatasourceActive') == 'True'
            for key, item in self.layerPropertiesInputs.items():
                widget = item['widget']
                val = layer.customProperty( item['xml'] )
                if not val:
                    val = ''
                if item['wType'] in ('text'):
                    widget.setText( val )
                elif item['wType'] == 'textarea':
                    widget.setPlainText(val)
                elif item['wType'] == 'spinbox':
                    widget.setValue(int(val))
                elif item['wType'] == 'checkbox':
                    widget.setChecked(val)
                elif item['wType'] == 'list':
                    listDic = { widget.itemData(i):i for i in range( widget.count() ) }
                    if val in listDic:
                        widget.setCurrentIndex( listDic[val] )

        # "active" checkbox
        self.dlg.cbDatasourceActive.setChecked( isActive )


    def onCbDatasourceActiveChange(self):
        '''
        Toggle the status "dynamicDatasourceActive" for the selected layer
        when the user uses the checkbox
        '''
        if not self.initDone:
            return

        if not self.selectedLayer:
            return

        # Get layers table
        lt = self.layersTable
        table = lt['tableWidget']

        # Get selected lines
        sm = table.selectionModel()
        lines = sm.selectedRows()
        if not lines:
            return
        if len( lines ) != 1:
            return
        for index in lines:
            row = index.row()

        # Get the status of active checkbox
        inputValue = str(self.dlg.cbDatasourceActive.isChecked())

        # Change layer line background color in the table
        if self.dlg.cbDatasourceActive.isChecked():
            bg = QColor(175, 208, 126)
        else:
            bg = Qt.transparent
        for i in range(0,3):
            table.item( row, i ).setBackground( bg )

        # Change data for the corresponding column in the layers table
        table.item( row, 2 ).setData( Qt.EditRole, inputValue )

        # Record the new value in the project
        self.selectedLayer.setCustomProperty( 'dynamicDatasourceActive', inputValue )
        p = QgsProject.instance()
        p.setDirty( True )


    def onLayerPropertyChange(self, key):
        '''
        Set the layer template property
        when the user change the content
        of the corresponding text input
        '''
        if not self.initDone:
            return
        if not self.selectedLayer:
            return

        # Get changed item
        item  = self.layerPropertiesInputs[key]
        widget = item['widget']

        # Get the new value
        inputValue = u''
        if item['wType'] == 'textarea':
            inputValue = widget.toPlainText()
        if item['wType'] == 'text':
            inputValue = widget.text()

        # Record the new value in the project
        self.selectedLayer.setCustomProperty( item['xml'], inputValue )
        p = QgsProject.instance()
        p.setDirty( True )

    def onCopyFromLayer(self):
        '''
        Get the layer datasource and copy it in the dynamic datasource text input
        '''
        if not self.initDone:
            return
        if not self.selectedLayer:
            return

        # Get the layer datasource
        uri = self.selectedLayer.dataProvider().dataSourceUri().split('|')[0]

        # Set the dynamic datasource content input
        self.dlg.dynamicDatasourceContent.setPlainText( uri )

        # Set templates for title and abstract
        self.dlg.abstractTemplate.setPlainText( self.selectedLayer.abstract() )
        self.dlg.titleTemplate.setText( self.selectedLayer.title() )



    ##
    # Variables tab
    ##
    def populateVariableTable(self):
        '''
        Fill the variable table
        '''
        # Get the list of variable from the project
        p = QgsProject.instance()
        variableList = p.readListEntry(  'PluginDynamicLayers' , 'VariableList')
        if not variableList:
            return

        # Get table
        tw = self.dlg.twVariableList

        # empty previous content
        for row in range(tw.rowCount()):
            tw.removeRow(row)
        tw.setRowCount(0)
        tw.setColumnCount( 2 )

        # Fill the table
        i = 0
        for variable in variableList[0]:
            tw.setRowCount( i +1 )

            # Set name item
            newItem = QTableWidgetItem( variable )
            newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled  )
            tw.setItem( i, 0, newItem )

            # Set empty value item
            newItem = QTableWidgetItem()
            newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled )
            tw.setItem( i, 1, newItem )

            # Set the new row count
            i+=1

        # Set the variable list
        self.variableList = variableList[0]


    def onAddVariableClicked(self):
        '''
        Add a variable to the list from the text input
        when the user clicks on the corresponding button
        '''
        if not self.initDone:
            return

        # Get table and row count
        tw = self.dlg.twVariableList
        twRowCount = tw.rowCount()

        # Get input data
        vname = str(self.dlg.inVariableName.text()).strip(' \t')
        vvalue = str(self.dlg.inVariableValue.text()).strip(' \t')

        # Check if the variable if not already in the list
        if vname in self.variableList:
            self.updateLog( self.tr(u'This variable is already in the list') )
            return

        # Add constraint of possible input values
        p = re.compile('^[a-zA-Z]+$')
        if not p.match( vname ):
            self.updateLog( self.tr(u'The variable must contain only lower case ascii letters !') )
            return

        # Set table properties
        tw.setRowCount(twRowCount + 1)
        tw.setColumnCount( 2 )

        # Empty the name text input
        self.dlg.inVariableName.setText(u'')

        # Add the new "variable" item to the table
        # name
        newItem = QTableWidgetItem()
        newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEnabled  )
        newItem.setData( Qt.EditRole, vname )
        tw.setItem(twRowCount, 0, newItem)

        # value
        newItem = QTableWidgetItem()
        newItem.setFlags( Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled )
        newItem.setData( Qt.EditRole, vvalue )
        tw.setItem(twRowCount, 1, newItem)

        # Add variable to the list
        self.variableList.append( vname )

        # Add variable to the project
        p = QgsProject.instance()
        p.writeEntry( 'PluginDynamicLayers', 'VariableList', self.variableList )
        p.setDirty( True )


    def onRemoveVariableClicked(self):
        '''
        Remove a variable from the table
        When the users clicks on the remove button
        '''
        if not self.initDone:
            return

        # Get selected lines
        tw = self.dlg.twVariableList
        sm = tw.selectionModel()
        lines = sm.selectedRows()
        if not lines or len(lines) != 1:
            return

        row = lines[0].row()

        # Get variable name
        vname = tw.item( row, 0 ).data( Qt.EditRole )

        # Remove variable name from list
        self.variableList.remove( vname )

        # Update project
        p = QgsProject.instance()
        p.writeEntry( 'PluginDynamicLayers', 'VariableList', self.variableList )
        p.setDirty( True )

        # Remove selected lines
        tw = self.dlg.twVariableList
        tw.removeRow( tw.currentRow() )


    def onVariableItemChanged(self, item):
        '''
        if not self.initDone:
            return
        Change the variable item
        '''
        if not self.initDone:
            return

        # Get row and column
        tw = self.dlg.twVariableList
        row = item.row()
        col = item.column()

        # Only allow edition of value
        if col != 1:
            return

        # Unselect row and item
        tw.clearSelection()

        # Get changed property
        data = tw.item( row, col ).data( Qt.EditRole )



    ##
    # Project properties tab
    ##

    def onCopyFromProjectClicked(self):
        '''
        Get project properties and set the input of the project tab
        '''
        if not self.initDone:
            return

        # Check if project has got some WMS capabilities
        p = QgsProject.instance()
        if not p.readEntry('WMSServiceCapabilities', "/")[1]:
            p.writeEntry('WMSServiceCapabilities', "/", "True")

        # Title
        pTitle = u''
        if p.readEntry('ProjectTitle', '/PluginDynamicLayers'):
            pTitle = p.readEntry('ProjectTitle', '/PluginDynamicLayers')[0]
        if not pTitle and p.readEntry('WMSServiceTitle', "/"):
            pTitle = p.readEntry('WMSServiceTitle', "/")[0]
        self.dlg.inProjectTitle.setText( str(pTitle) )

        # Abstract
        pAbstract = u''
        if p.readEntry('ProjectAbstract', '/PluginDynamicLayers'):
            pAbstract = p.readEntry('ProjectAbstract', '/PluginDynamicLayers')[0]
        if not pAbstract and  p.readEntry('WMSServiceAbstract', "/"):
            pAbstract = p.readEntry('WMSServiceAbstract', "/")[0]
        self.dlg.inProjectAbstract.setText( str(pAbstract) )


    def onProjectPropertyChanged(self, prop):
        '''
        Save project dynamic property in the project
        when the user changes the content
        '''
        if not self.initDone:
            return

        widget = self.projectPropertiesInputs[prop]['widget']
        if prop in ('title', 'variableSourceLayerExpression'):
            val = widget.text()
        elif prop == 'abstract':
            val = widget.toPlainText()
        elif prop in ('extentLayer', 'variableSourceLayer'):
            var = None
            layer = self.getQgisLayerByNameFromCombobox( widget )
            if layer:
                val = layer.id()
            else:
                return
        elif prop == 'extentMargin':
            val = widget.value()
        else:
            return

        p = QgsProject.instance()

        # Store value into the project
        xml = self.projectPropertiesInputs[prop]['xml']
        p.writeEntry( 'PluginDynamicLayers', xml, val )
        p.setDirty( True )


    def populateProjectProperties(self):
        '''
        Fill in the project properties item
        from XML
        '''

        p = QgsProject.instance()
        lr = QgsProject.instance()
        # Fill the property from the PluginDynamicLayers XML
        for prop, item in self.projectPropertiesInputs.items():
            widget = item['widget']
            xml = self.projectPropertiesInputs[prop]['xml']
            val = p.readEntry('PluginDynamicLayers' , xml)
            if val:
                val = val[0]
            if not val:
                continue
            if item['wType'] in ('text', 'textarea'):
                widget.setText( val )
            elif item['wType'] == 'spinbox':
                widget.setValue(int(val))
            elif item['wType'] == 'checkbox':
                widget.setChecked(val)
            elif item['wType'] == 'list':
                listDic = { widget.itemData(i):i for i in range( widget.count() ) }
                if val in listDic:
                    widget.setCurrentIndex( listDic[val] )


    ##
    # Initialization
    ##

    def populateLayerCombobox(self, combobox, ltype='all', providerTypeList=['all'], addEmptyItem=True):
        '''
            Get the list of layers and add them to a combo box
            * ltype can be : all, vector, raster
            * providerTypeList is a list and can be : ['all'] or a list of provider keys
            as ['spatialite', 'postgres'] or ['ogr', 'postgres'], etc.
        '''
        # empty combobox
        combobox.clear()
        if addEmptyItem:
            # add empty item
            combobox.addItem ( '---', -1)
        # loop though the layers
        for layer in QgsProject.instance().mapLayers().values():
            layerId = layer.id()
            # vector
            if layer.type() == QgsMapLayer.VectorLayer and ltype in ('all', 'vector'):
                if not hasattr(layer, 'providerType'):
                    continue
                if 'all' in providerTypeList or layer.providerType() in providerTypeList:
                    combobox.addItem ( layer.name(), str(layerId))
            # raster
            if layer.type() == QgsMapLayer.RasterLayer and ltype in ('all', 'raster'):
                combobox.addItem ( layer.name(), str(layerId))


    def getQgisLayerByNameFromCombobox(self, layerComboBox):
        '''Get a layer chosen in a combobox'''
        returnLayer = None
        uniqueId = str( layerComboBox.itemData( layerComboBox.currentIndex() ) )
        try:
            lr = QgsProject.instance()
            layer = lr.mapLayer( uniqueId )
            if layer:
                if layer.isValid():
                    returnLayer = layer
        except:
            returnLayer = None
        return returnLayer



    ##
    # Global actions
    ##
    def onApplyVariablesClicked(self, source='table'):
        '''
        Replace layers datasource with new datasource created
        by replace variables in dynamicDatasource
        '''
        if not self.initDone:
            return

        ok = True

        # Use the engine class to do the job
        dle = DynamicLayersEngine()

        # Set the dynamic layers list
        dle.setDynamicLayersList()

        # Set search and replace dictionary
        # Collect variables names and values
        if source == 'table':
            searchAndReplaceDictionary = {}
            tw = self.dlg.twVariableList
            for row in range( tw.rowCount() ):
                vname = tw.item( row, 0 ).data( Qt.EditRole )
                vvalue = tw.item( row, 1 ).data( Qt.EditRole )
                searchAndReplaceDictionary[vname] = vvalue
            dle.setSearchAndReplaceDictionary( searchAndReplaceDictionary )
        else:
            layer = self.getQgisLayerByNameFromCombobox( self.dlg.inVariableSourceLayer )
            exp = self.dlg.inVariableSourceLayerExpression.text()
            dle.setSearchAndReplaceDictionaryFromLayer( layer, exp )

        # Change layers datasource
        dle.setDynamicLayersDatasourceFromDic( )

        # Set project properties
        dle.setDynamicProjectProperties()

        # Set extent layer
        extentLayer = self.getQgisLayerByNameFromCombobox( self.dlg.inExtentLayer )
        if extentLayer:
            dle.setExtentLayer( extentLayer )

        # Set extent margin
        extentMargin = self.dlg.inExtentMargin.value()
        if extentMargin:
            dle.setExtentMargin( extentMargin )

        # Set new extent
        dle.setProjectExtent()

        # Set project as dirty
        p = QgsProject.instance()
        p.setDirty( True )


    def run(self):
        """Run method that performs all the real work"""

        self.initDone = False

        # Popuplate the layers table
        self.populateLayerTable()

        # Populate the variable table
        self.populateVariableTable()

        # Populate the extent layer list
        self.populateLayerCombobox( self.dlg.inExtentLayer, 'vector', 'all', False )

        # Populate the variable source layer combobox
        self.populateLayerCombobox(self.dlg.inVariableSourceLayer, 'vector', 'all', False )

        # Copy project propertie to corresponding tab
        self.populateProjectProperties()

        self.initDone = True

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass



class DynamicLayersServer:
    """Plugin for QGIS server
    this plugin loads DynamicLayersFilter"""

    def __init__(self, serverIface):
        # Save reference to the QGIS server interface
        self.serverIface = serverIface
        QgsMessageLog.logMessage("SUCCESS - DynamicLayersServer init", 'plugin', QgsMessageLog.INFO)

        from filters.DynamicLayersFilter import DynamicLayersFilter
        try:
            serverIface.registerFilter( DynamicLayersFilter(serverIface), 100 )
        except Exception as e:
            QgsLogger.debug("DynamicLayersServer - Error loading filter DynamicLayersServer : %s" % e )
