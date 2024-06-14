"""
/***************************************************************************
 DynamicLayers
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
import os.path
import sys
import re
from functools import partial

from qgis.PyQt.QtCore import Qt, QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QAction, QIcon, QTextCursor, QColor
from qgis.PyQt.QtWidgets import qApp, QTableWidgetItem
from qgis.core import Qgis, QgsProject
from qgis.utils import OverrideCursor

from dynamic_layers.dynamic_layers_dialog import DynamicLayersDialog
from dynamic_layers.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.tools import resources_path


class DynamicLayers:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        self.projectPropertiesInputs = None
        self.layerPropertiesInputs = None
        self.initDone = None
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'DynamicLayers_{locale}.qm')

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = DynamicLayersDialog()

        # Layers attribute that can be shown and optionally changed in the plugin
        self.layersTable = {
            'tableWidget': self.dlg.twLayers,
            'attributes': [
                {'key': 'id', 'editable': False},
                {'key': 'name', 'editable': False, 'type': 'string'},
                {'key': 'dynamicDatasourceActive', 'editable': False, 'type': 'string'},
            ],
        }

        # Keep record of style widget
        self.selectedLayerWidget = None
        self.selectedLayer = None

        # Variables
        self.variableList = []

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr('&Dynamic Layers')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar('DynamicLayers')
        self.toolbar.setObjectName('DynamicLayers')

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
        :type icon_path: Path

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

        icon = QIcon(str(icon_path))
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

    # noinspection PyPep8Naming
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.add_action(
            resources_path('icons', 'icon.png'),
            text=self.tr('Dynamic Layers'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # slots/signals
        ###############
        self.initDone = False

        # Actions when row selection changes
        slot = self.on_row_selection_changed
        table = self.layersTable['tableWidget']
        sm = table.selectionModel()
        sm.selectionChanged.connect(slot)

        # Actions when the layer properties are changed panel
        self.dlg.cbDatasourceActive.stateChanged.connect(self.on_cb_datasource_active_change)
        self.dlg.btCopyFromLayer.clicked.connect(self.on_copy_from_layer)

        self.layerPropertiesInputs = {
            'datasource': {
                'widget': self.dlg.dynamicDatasourceContent,
                'wType': 'textarea',
                'xml': 'dynamicDatasourceContent',
            },
            'title': {
                'widget': self.dlg.titleTemplate,
                'wType': 'text',
                'xml': 'titleTemplate',
            },
            'abstract': {
                'widget': self.dlg.abstractTemplate,
                'wType': 'textarea',
                'xml': 'abstractTemplate',
            },
        }
        for key, item in self.layerPropertiesInputs.items():
            control = item['widget']
            slot = partial(self.on_layer_property_change, key)
            control.textChanged.connect(slot)

        # Actions of the Variable tab
        self.dlg.btAddVariable.clicked.connect(self.on_add_variable_clicked)
        self.dlg.btRemoveVariable.clicked.connect(self.on_remove_variable_clicked)

        # Apply buttons
        slot = partial(self.on_apply_variables_clicked, 'table')
        self.dlg.btApplyVariables.clicked.connect(slot)
        slot = partial(self.on_apply_variables_clicked, 'layer')
        self.dlg.btApplyFromLayer.clicked.connect(slot)

        # Project properties tab
        self.dlg.btCopyFromProject.clicked.connect(self.on_copy_from_project_clicked)

        self.projectPropertiesInputs = {
            'title': {
                'widget': self.dlg.inProjectTitle,
                'wType': 'text',
                'xml': 'ProjectTitle',
            },
            'abstract': {
                'widget': self.dlg.inProjectAbstract,
                'wType': 'textarea',
                'xml': 'ProjectAbstract',
            },
            'extentLayer': {
                'widget': self.dlg.inExtentLayer,
                'wType': 'list',
                'xml': 'ExtentLayer',
            },
            'extentMargin': {
                'widget': self.dlg.inExtentMargin,
                'wType': 'spinbox',
                'xml': 'ExtentMargin',
            },
            'variableSourceLayer': {
                'widget': self.dlg.inVariableSourceLayer,
                'wType': 'list',
                'xml': 'VariableSourceLayer',
            },
            'variableSourceLayerExpression': {
                'widget': self.dlg.inVariableSourceLayerExpression,
                'wType': 'text',
                'xml': 'VariableSourceLayerExpression',
            },
        }
        for key, item in self.projectPropertiesInputs.items():
            slot = partial(self.on_project_property_changed, key)
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
        self.dlg.btClearLog.clicked.connect(self.clear_log)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr('&Dynamic Layers'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def clear_log(self):
        """
        Clear the log
        """
        self.dlg.txtLog.clear()

    def update_log(self, msg):
        """
        Update the log
        """
        t = self.dlg.txtLog
        t.ensureCursorVisible()
        prefix = '<span style="font-weight:normal;">'
        suffix = '</span>'
        t.append(f'{prefix} {msg} {suffix}')
        c = t.textCursor()
        c.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)
        t.setTextCursor(c)
        qApp.processEvents()

    def populate_layer_table(self):
        """
        Fill the table for a given layer type
        """
        # Get parameters for the widget
        lt = self.layersTable
        table = lt['tableWidget']

        attributes = lt['attributes']

        # headerData = [a['key'] for a in attributes]

        # empty previous content
        for row in range(table.rowCount()):
            table.removeRow(row)
        table.setRowCount(0)

        # create columns and header row
        columns = [a['key'] for a in attributes]
        col_count = len(columns)
        table.setColumnCount(col_count)
        table.setHorizontalHeaderLabels(tuple(columns))

        # load content from project layers
        lr = QgsProject.instance()
        for lid in lr.mapLayers():
            layer = lr.mapLayer(lid)

            line_data = []

            # Set row and column count
            tw_row_count = table.rowCount()
            # add a new line
            table.setRowCount(tw_row_count + 1)
            table.setColumnCount(col_count)
            i = 0

            if layer.customProperty('dynamicDatasourceActive') == 'True':
                bg = QColor(175, 208, 126)
            else:
                bg = Qt.transparent

            # get information
            for attr in attributes:
                new_item = QTableWidgetItem()

                # Is editable or not
                if attr['editable']:
                    new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
                else:
                    new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

                # background
                new_item.setBackground(bg)

                # Item value
                value = self.get_layer_property(layer, attr['key'])
                new_item.setData(Qt.EditRole, value)

                # Add cell data to lineData
                # encode it in the file system encoding, only if needed
                if hasattr(value, 'encode'):
                    value = value.encode(sys.getfilesystemencoding())
                line_data.append(value)

                # Add item
                table.setItem(tw_row_count, i, new_item)
                i += 1

    @staticmethod
    def get_layer_property(layer, prop):
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
            a = layer.customProperty('dynamicDatasourceActive')
            return a

        elif prop == 'dynamicDatasourceContent':
            a = layer.customProperty('dynamicDatasourceContent')
            return a

        else:
            return None

    def on_row_selection_changed(self):
        """
        Change content of dynamic properties group inputs
        When the user selects a layer in the table
        """
        if not self.initDone:
            return

        show_layer_properties = True

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
        is_active = False

        if show_layer_properties:
            row = lines[0].row()

            # Get layer
            layer_id = table.item(row, 0).data(Qt.EditRole)
            lr = QgsProject.instance()
            layer = lr.mapLayer(layer_id)
            if not layer:
                show_layer_properties = False
            else:
                self.selectedLayer = layer

        if len(lines) != 1:
            show_layer_properties = False

        # Toggle the layer properties group
        self.dlg.gbLayerDynamicProperties.setEnabled(show_layer_properties)

        # Set the content of the layer properties inputs
        # dynamic datasource text input content
        if layer:
            is_active = layer.customProperty('dynamicDatasourceActive') == 'True'
            for key, item in self.layerPropertiesInputs.items():
                widget = item['widget']
                val = layer.customProperty(item['xml'])
                if not val:
                    val = ''
                if item['wType'] in ('text', ):
                    widget.setText(val)
                elif item['wType'] == 'textarea':
                    widget.setPlainText(val)
                elif item['wType'] == 'spinbox':
                    widget.setValue(int(val))
                elif item['wType'] == 'checkbox':
                    widget.setChecked(val)
                elif item['wType'] == 'list':
                    list_dic = {widget.itemData(i): i for i in range(widget.count())}
                    if val in list_dic:
                        widget.setCurrentIndex(list_dic[val])

        # "active" checkbox
        self.dlg.cbDatasourceActive.setChecked(is_active)

    def on_cb_datasource_active_change(self):
        """
        Toggle the status "dynamicDatasourceActive" for the selected layer
        when the user uses the checkbox
        """
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
        if len(lines) != 1:
            return
        for index in lines:
            row = index.row()

        # Get the status of active checkbox
        input_value = str(self.dlg.cbDatasourceActive.isChecked())

        # Change layer line background color in the table
        if self.dlg.cbDatasourceActive.isChecked():
            bg = QColor(175, 208, 126)
        else:
            bg = Qt.transparent
        for i in range(0, 3):
            table.item(row, i).setBackground(bg)

        # Change data for the corresponding column in the layers table
        table.item(row, 2).setData(Qt.EditRole, input_value)

        # Record the new value in the project
        self.selectedLayer.setCustomProperty('dynamicDatasourceActive', input_value)
        p = QgsProject.instance()
        p.setDirty(True)

    def on_layer_property_change(self, key):
        """
        Set the layer template property
        when the user change the content
        of the corresponding text input
        """
        if not self.initDone:
            return
        if not self.selectedLayer:
            return

        # Get changed item
        item = self.layerPropertiesInputs[key]
        widget = item['widget']

        # Get the new value
        input_value = ''
        if item['wType'] == 'textarea':
            input_value = widget.toPlainText()
        if item['wType'] == 'text':
            input_value = widget.text()

        # Record the new value in the project
        self.selectedLayer.setCustomProperty(item['xml'], input_value)
        p = QgsProject.instance()
        p.setDirty(True)

    def on_copy_from_layer(self):
        """
        Get the layer datasource and copy it in the dynamic datasource text input
        """
        if not self.initDone:
            return
        if not self.selectedLayer:
            return

        # Get the layer datasource
        uri = self.selectedLayer.dataProvider().dataSourceUri().split('|')[0]

        # Set the dynamic datasource content input
        self.dlg.dynamicDatasourceContent.setPlainText(uri)

        # Set templates for title and abstract
        self.dlg.abstractTemplate.setPlainText(self.selectedLayer.abstract())
        self.dlg.titleTemplate.setText(self.selectedLayer.title())

    ##
    # Variables tab
    ##
    def populate_variable_table(self):
        """
        Fill the variable table
        """
        # Get the list of variable from the project
        p = QgsProject.instance()
        variable_list = p.readListEntry('PluginDynamicLayers', 'VariableList')
        if not variable_list:
            return

        # Get table
        tw = self.dlg.twVariableList

        # empty previous content
        for row in range(tw.rowCount()):
            tw.removeRow(row)
        tw.setRowCount(0)
        tw.setColumnCount(2)

        # Fill the table
        i = 0
        for variable in variable_list[0]:
            tw.setRowCount(i + 1)

            # Set name item
            new_item = QTableWidgetItem(variable)
            new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            tw.setItem(i, 0, new_item)

            # Set empty value item
            new_item = QTableWidgetItem()
            new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
            tw.setItem(i, 1, new_item)

            # Set the new row count
            i += 1

        # Set the variable list
        self.variableList = variable_list[0]

    def on_add_variable_clicked(self):
        """
        Add a variable to the list from the text input
        when the user clicks on the corresponding button
        """
        if not self.initDone:
            self.update_log(self.tr('Init was not finished'))
            return

        # Get table and row count
        tw = self.dlg.twVariableList
        tw_row_count = tw.rowCount()

        # Get input data
        v_name = str(self.dlg.inVariableName.text()).strip(' \t')
        v_value = str(self.dlg.inVariableValue.text()).strip(' \t')

        # Check if the variable is not already in the list
        if v_name in self.variableList:
            self.update_log(self.tr('This variable is already in the list'))
            return

        # Add constraint of possible input values
        p = re.compile('^[a-zA-Z]+$')
        if not p.match(v_name):
            self.update_log(self.tr('The variable must contain only lower case ascii letters !'))
            return

        # Set table properties
        tw.setRowCount(tw_row_count + 1)
        tw.setColumnCount(2)

        # Empty the name text input
        self.dlg.inVariableName.setText('')

        # Add the new "variable" item to the table
        # name
        new_item = QTableWidgetItem()
        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        new_item.setData(Qt.EditRole, v_name)
        tw.setItem(tw_row_count, 0, new_item)

        # value
        new_item = QTableWidgetItem()
        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)
        new_item.setData(Qt.EditRole, v_value)
        tw.setItem(tw_row_count, 1, new_item)

        # Add variable to the list
        self.variableList.append(v_name)

        # Add variable to the project
        p = QgsProject.instance()
        p.writeEntry('PluginDynamicLayers', 'VariableList', self.variableList)
        p.setDirty(True)

    def on_remove_variable_clicked(self):
        """
        Remove a variable from the table
        When the users click on the remove button
        """
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
        v_name = tw.item(row, 0).data(Qt.EditRole)

        # Remove variable name from list
        self.variableList.remove(v_name)

        # Update project
        p = QgsProject.instance()
        p.writeEntry('PluginDynamicLayers', 'VariableList', self.variableList)
        p.setDirty(True)

        # Remove selected lines
        tw = self.dlg.twVariableList
        tw.removeRow(tw.currentRow())

    def on_variable_item_changed(self, item):
        """
        if not self.initDone:
            return
        Change the variable item
        """
        if not self.initDone:
            return

        # Get row and column
        tw = self.dlg.twVariableList
        # row = item.row()
        col = item.column()

        # Only allow edition of value
        if col != 1:
            return

        # Unselect row and item
        tw.clearSelection()

        # Get changed property
        # data = tw.item(row, col).data(Qt.EditRole)

    ##
    # Project properties tab
    ##

    def on_copy_from_project_clicked(self):
        """
        Get project properties and set the input of the project tab
        """
        if not self.initDone:
            return

        # Check if project has got some WMS capabilities
        p = QgsProject.instance()
        if not p.readEntry('WMSServiceCapabilities', "/")[1]:
            p.writeEntry('WMSServiceCapabilities', "/", "True")

        # Title
        p_title = ''
        if p.readEntry('ProjectTitle', '/PluginDynamicLayers'):
            p_title = p.readEntry('ProjectTitle', '/PluginDynamicLayers')[0]
        if not p_title and p.readEntry('WMSServiceTitle', "/"):
            p_title = p.readEntry('WMSServiceTitle', "/")[0]
        self.dlg.inProjectTitle.setText(str(p_title))

        # Abstract
        p_abstract = ''
        if p.readEntry('ProjectAbstract', '/PluginDynamicLayers'):
            p_abstract = p.readEntry('ProjectAbstract', '/PluginDynamicLayers')[0]
        if not p_abstract and p.readEntry('WMSServiceAbstract', "/"):
            p_abstract = p.readEntry('WMSServiceAbstract', "/")[0]
        self.dlg.inProjectAbstract.setText(str(p_abstract))

    def on_project_property_changed(self, prop):
        """
        Save project dynamic property in the project
        when the user changes the content
        """
        if not self.initDone:
            return

        widget = self.projectPropertiesInputs[prop]['widget']
        if prop in ('title', 'variableSourceLayerExpression'):
            val = widget.text()
        elif prop == 'abstract':
            val = widget.toPlainText()
        elif prop in ('extentLayer', 'variableSourceLayer'):
            # var = None
            layer = widget.currentLayer()
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
        p.writeEntry('PluginDynamicLayers', xml, val)
        p.setDirty(True)

    def populate_project_properties(self):
        """
        Fill in the project properties item
        from XML
        """

        p = QgsProject.instance()
        # lr = QgsProject.instance()
        # Fill the property from the PluginDynamicLayers XML
        for prop, item in self.projectPropertiesInputs.items():
            widget = item['widget']
            xml = self.projectPropertiesInputs[prop]['xml']
            val = p.readEntry('PluginDynamicLayers', xml)
            if val:
                val = val[0]
            if not val:
                continue
            if item['wType'] in ('text', 'textarea'):
                widget.setText(val)
            elif item['wType'] == 'spinbox':
                widget.setValue(int(val))
            elif item['wType'] == 'checkbox':
                widget.setChecked(val)
            elif item['wType'] == 'list':
                list_dic = {widget.itemData(i): i for i in range(widget.count())}
                if val in list_dic:
                    widget.setCurrentIndex(list_dic[val])

    ##
    # Global actions
    ##
    def on_apply_variables_clicked(self, source='table'):
        """
        Replace layers datasource with new datasource created
        by replace variables in dynamicDatasource
        """
        if not self.initDone:
            return

        with OverrideCursor(Qt.WaitCursor):

            # Use the engine class to do the job
            dle = DynamicLayersEngine()

            # Set the dynamic layers list
            dle.set_dynamic_layers_list()

            # Set search and replace dictionary
            # Collect variables names and values
            if source == 'table':
                search_and_replace_dictionary = {}
                tw = self.dlg.twVariableList
                for row in range(tw.rowCount()):
                    v_name = tw.item(row, 0).data(Qt.EditRole)
                    v_value = tw.item(row, 1).data(Qt.EditRole)
                    search_and_replace_dictionary[v_name] = v_value
                dle.set_search_and_replace_dictionary(search_and_replace_dictionary)
            else:
                layer = self.dlg.inVariableSourceLayer.currentLayer()
                exp = self.dlg.inVariableSourceLayerExpression.text()
                dle.set_search_and_replace_dictionary_from_layer(layer, exp)

            # Change layers datasource
            dle.set_dynamic_layers_datasource_from_dic()

            # Set project properties
            dle.set_dynamic_project_properties()

            # Set extent layer
            extent_layer = self.dlg.inExtentLayer.currentLayer()
            if extent_layer:
                dle.set_extent_layer(extent_layer)

            # Set extent margin
            extent_margin = self.dlg.inExtentMargin.value()
            if extent_margin:
                dle.set_extent_margin(extent_margin)

            # Set new extent
            dle.set_project_extent()

            # Set project as dirty
            p = QgsProject.instance()
            p.setDirty(True)

    def run(self):
        """Run method that performs all the real work"""

        self.initDone = False

        # Populate the layers table
        self.populate_layer_table()

        # Populate the variable table
        self.populate_variable_table()

        # Populate the extent layer list
        self.dlg.inExtentLayer.setFilters(Qgis.LayerFilter.VectorLayer)
        self.dlg.inExtentLayer.setAllowEmptyLayer(False)

        # Populate the variable source layer combobox
        self.dlg.inVariableSourceLayer.setFilters(Qgis.LayerFilter.VectorLayer)
        self.dlg.inVariableSourceLayer.setAllowEmptyLayer(False)

        # Copy project properties to corresponding tab
        self.populate_project_properties()

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
