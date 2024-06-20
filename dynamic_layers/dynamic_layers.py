__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import sys
import re
from functools import partial
from pathlib import Path

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QAction, QIcon, QTextCursor
from qgis.PyQt.QtWidgets import qApp, QMessageBox, QTableWidgetItem
from qgis.core import Qgis, QgsMapLayer, QgsIconUtils, QgsProject
from qgis.utils import OverrideCursor

from dynamic_layers.dynamic_layers_dialog import DynamicLayersDialog
from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.tools import resources_path
from dynamic_layers.definitions import CustomProperty, QtVar


class DynamicLayers:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor."""
        self.projectPropertiesInputs = None
        self.layerPropertiesInputs = None
        self.initDone = None
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = Path(__file__).resolve().parent
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = self.plugin_dir / 'i18n' / f'DynamicLayers_{locale}.qm'
        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path))

            QCoreApplication.installTranslator(self.translator)

        self.project = QgsProject.instance()

        # Create the dialog (after translation) and keep reference
        self.dlg = DynamicLayersDialog()

        # Layers attribute that can be shown and optionally changed in the plugin
        self.layersTable = [
            {
                'key': 'id',
                'display': self.tr('ID'),
                'editable': False,
            }, {
                'key': 'name',
                'display': self.tr('Name'),
                'editable': False,
                'type': 'string'
            }, {
                'key': 'dynamicDatasourceActive',
                'display': self.tr('Dynamic Datasource Active'),
                'editable': False,
                'type': 'string'
            },
        ]

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
    def tr(self, message: str) -> str:
        return QCoreApplication.translate('DynamicLayers', message)

    def add_action(
            self,
            icon_path: Path,
            text: str,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
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

        :returns: The action that was created. Note that the action is also
            added to self. actions list.
        :rtype: QAction
        """

        icon = QIcon(str(icon_path))
        action = QAction(icon, text, parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

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
        sm = self.dlg.twLayers.selectionModel()
        sm.selectionChanged.connect(self.on_row_selection_changed)

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

    def update_log(self, msg: str):
        """
        Update the log
        """
        self.dlg.txtLog.ensureCursorVisible()
        prefix = '<span style="font-weight:normal;">'
        suffix = '</span>'
        self.dlg.txtLog.append(f'{prefix} {msg} {suffix}')
        c = self.dlg.txtLog.textCursor()
        c.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)
        self.dlg.txtLog.setTextCursor(c)
        qApp.processEvents()

    def populate_layer_table(self):
        """
        Fill the table for a given layer type
        """
        # empty previous content
        for row in range(self.dlg.twLayers.rowCount()):
            self.dlg.twLayers.removeRow(row)
        self.dlg.twLayers.setRowCount(0)

        # create columns and header row
        columns = [a['display'] for a in self.layersTable]
        col_count = len(columns)
        self.dlg.twLayers.setColumnCount(col_count)
        self.dlg.twLayers.setHorizontalHeaderLabels(tuple(columns))

        # load content from project layers
        for layer in self.project.mapLayers().values():

            line_data = []

            # Set row and column count
            tw_row_count = self.dlg.twLayers.rowCount()
            # add a new line
            self.dlg.twLayers.setRowCount(tw_row_count + 1)
            self.dlg.twLayers.setColumnCount(col_count)
            i = 0

            if layer.customProperty(CustomProperty.DynamicDatasourceActive) == str(True):
                bg = QtVar.Green
            else:
                bg = QtVar.Transparent

            # get information
            for attr in self.layersTable:
                new_item = QTableWidgetItem()

                # Is editable or not
                if attr['editable']:
                    new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
                else:
                    new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)

                # background
                new_item.setBackground(bg)

                # Item value
                value = self.get_layer_property(layer, attr['key'])
                new_item.setData(QtVar.EditRole, value)
                if attr['key'] == 'name':
                    new_item.setIcon(QgsIconUtils.iconForLayer(layer))

                # Add cell data to lineData
                # encode it in the file system encoding, only if needed
                if hasattr(value, 'encode'):
                    value = value.encode(sys.getfilesystemencoding())
                line_data.append(value)

                # Add item
                self.dlg.twLayers.setItem(tw_row_count, i, new_item)
                i += 1

    @staticmethod
    def get_layer_property(layer: QgsMapLayer, prop: str) -> str | None:
        """
        Get a layer property
        """

        if prop == 'id':
            return layer.id()

        if prop == 'name':
            return layer.name()

        elif prop == 'uri':
            return layer.dataProvider().dataSourceUri().split('|')[0]

        elif prop == CustomProperty.DynamicDatasourceActive:
            return layer.customProperty(CustomProperty.DynamicDatasourceActive)

        elif prop == CustomProperty.DynamicDatasourceContent:
            return layer.customProperty(CustomProperty.DynamicDatasourceContent)

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

        # Get selected lines
        lines = self.dlg.twLayers.selectionModel().selectedRows()
        if len(lines) < 1:
            return

        layer = None
        self.selectedLayer = None

        if show_layer_properties:
            row = lines[0].row()

            # Get layer
            layer_id = self.dlg.twLayers.item(row, 0).data(QtVar.EditRole)
            layer = self.project.mapLayer(layer_id)
            if not layer:
                show_layer_properties = False
            else:
                self.selectedLayer = layer

        if not lines or len(lines) != 1:
            show_layer_properties = False

        # Toggle the layer properties group
        self.dlg.gbLayerDynamicProperties.setEnabled(show_layer_properties)

        # Set the content of the layer properties inputs
        # dynamic datasource text input content
        if layer:
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
        is_active = layer.customProperty(CustomProperty.DynamicDatasourceActive) == str(True)
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

        # Get selected lines
        lines = self.dlg.twLayers.selectionModel().selectedRows()
        if len(lines) != 1:
            return

        row = lines[0].row()

        # Get the status of active checkbox
        input_value = str(self.dlg.cbDatasourceActive.isChecked())

        # Change layer line background color in the table
        if self.dlg.cbDatasourceActive.isChecked():
            bg = QtVar.Green
        else:
            bg = QtVar.Transparent
        for i in range(0, 3):
            self.dlg.twLayers.item(row, i).setBackground(bg)

        # Change data for the corresponding column in the layers table
        self.dlg.twLayers.item(row, 2).setData(QtVar.EditRole, input_value)

        # Record the new value in the project
        self.selectedLayer.setCustomProperty(CustomProperty.DynamicDatasourceActive, input_value)
        self.project.setDirty(True)

    def on_layer_property_change(self, key: str):
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

        # Get the new value
        input_value = ''
        if item['wType'] == 'textarea':
            input_value = item['widget'].toPlainText()
        if item['wType'] == 'text':
            input_value = item['widget'].text()

        # Record the new value in the project
        self.selectedLayer.setCustomProperty(item['xml'], input_value)
        self.project.setDirty(True)

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
        abstract = self.selectedLayer.abstract()
        title = self.selectedLayer.title()

        # Previous values
        previous_uri = self.dlg.dynamicDatasourceContent.toPlainText()
        previous_abstract = self.dlg.abstractTemplate.toPlainText()
        previous_title = self.dlg.titleTemplate.text()

        ask = False
        if previous_uri != '' and previous_uri != uri:
            ask = True
        if previous_abstract != '' and previous_abstract != abstract:
            ask = True
        if previous_title != '' and previous_title != title:
            ask = True

        if ask:
            box = QMessageBox(self.dlg)
            box.setIcon(QMessageBox.Question)
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(self.tr('Replace settings by layer properties'))
            box.setText(self.tr(
                'You have already set some values for this layer, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            result = box.exec_()
            if result == QMessageBox.No:
                return

        # Set the dynamic datasource content input
        self.dlg.dynamicDatasourceContent.setPlainText(uri)

        # Set templates for title and abstract
        self.dlg.abstractTemplate.setPlainText(abstract)
        self.dlg.titleTemplate.setText(title)

    ##
    # Variables tab
    ##
    def populate_variable_table(self):
        """
        Fill the variable table
        """
        # Get the list of variable from the project
        variable_list = self.project.readListEntry('PluginDynamicLayers', 'VariableList')
        if not variable_list:
            return

        # empty previous content
        for row in range(self.dlg.twVariableList.rowCount()):
            self.dlg.twVariableList.removeRow(row)
        self.dlg.twVariableList.setRowCount(0)
        self.dlg.twVariableList.setColumnCount(2)

        # Fill the table
        i = 0
        for variable in variable_list[0]:
            self.dlg.twVariableList.setRowCount(i + 1)

            # Set name item
            new_item = QTableWidgetItem(variable)
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)
            self.dlg.twVariableList.setItem(i, 0, new_item)

            # Set empty value item
            new_item = QTableWidgetItem()
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
            self.dlg.twVariableList.setItem(i, 1, new_item)

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
        tw_row_count = self.dlg.twVariableList.rowCount()

        # Get input data
        v_name = str(self.dlg.inVariableName.text()).strip(' \t')
        v_value = str(self.dlg.inVariableValue.text()).strip(' \t')

        # Check if the variable is not already in the list
        if v_name in self.variableList:
            self.update_log(self.tr('This variable is already in the list'))
            return

        # Add constraint of possible input values
        project = re.compile('^[a-zA-Z]+$')
        if not project.match(v_name):
            self.update_log(self.tr('The variable must contain only lower case ascii letters !'))
            return

        # Set table properties
        self.dlg.twVariableList.setRowCount(tw_row_count + 1)
        self.dlg.twVariableList.setColumnCount(2)

        # Empty the name text input
        self.dlg.inVariableName.setText('')

        # Add the new "variable" item to the table
        # name
        new_item = QTableWidgetItem()
        new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)
        new_item.setData(QtVar.EditRole, v_name)
        self.dlg.twVariableList.setItem(tw_row_count, 0, new_item)

        # value
        new_item = QTableWidgetItem()
        new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
        new_item.setData(QtVar.EditRole, v_value)
        self.dlg.twVariableList.setItem(tw_row_count, 1, new_item)

        # Add variable to the list
        self.variableList.append(v_name)

        # Add variable to the project
        self.project.writeEntry('PluginDynamicLayers', 'VariableList', self.variableList)
        self.project.setDirty(True)

    def on_remove_variable_clicked(self):
        """
        Remove a variable from the table
        When the users click on the remove button
        """
        if not self.initDone:
            return

        # Get selected lines
        lines = self.dlg.twVariableList.selectionModel().selectedRows()
        if len(lines) != 1:
            return

        row = lines[0].row()

        # Get variable name
        v_name = self.dlg.twVariableList.item(row, 0).data(QtVar.EditRole)

        # Remove variable name from list
        self.variableList.remove(v_name)

        # Update project
        self.project.writeEntry('PluginDynamicLayers', 'VariableList', self.variableList)
        self.project.setDirty(True)

        # Remove selected lines
        self.dlg.twVariableList.removeRow(self.dlg.twVariableList.currentRow())

    def on_variable_item_changed(self, item):
        """
        if not self.initDone:
            return
        Change the variable item
        """
        if not self.initDone:
            return

        # Get row and column
        # row = item.row()
        col = item.column()

        # Only allow edition of value
        if col != 1:
            return

        # Unselect row and item
        self.dlg.twVariableList.clearSelection()

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

        # Title
        p_title = ''
        if self.project.readEntry('ProjectTitle', '/PluginDynamicLayers'):
            p_title = self.project.readEntry('ProjectTitle', '/PluginDynamicLayers')[0]
        if not p_title and self.project.readEntry('WMSServiceTitle', "/"):
            p_title = self.project.readEntry('WMSServiceTitle', "/")[0]

        # Abstract
        p_abstract = ''
        if self.project.readEntry('ProjectAbstract', '/PluginDynamicLayers'):
            p_abstract = self.project.readEntry('ProjectAbstract', '/PluginDynamicLayers')[0]
        if not p_abstract and self.project.readEntry('WMSServiceAbstract', "/"):
            p_abstract = self.project.readEntry('WMSServiceAbstract', "/")[0]

        ask = False
        previous_title = self.dlg.inProjectTitle.text()
        if previous_title != '' and previous_title != p_title:
            ask = True

        previous_abstract = self.dlg.inProjectAbstract.toPlainText()
        if previous_abstract != '' and previous_abstract != p_abstract:
            ask = True

        if ask:
            box = QMessageBox(self.dlg)
            box.setIcon(QMessageBox.Question)
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(self.tr('Replace settings by project properties'))
            box.setText(self.tr(
                'You have already set some values for this project, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            result = box.exec_()
            if result == QMessageBox.No:
                return

        if not self.project.readEntry('WMSServiceCapabilities', "/")[1]:
            self.project.writeEntry('WMSServiceCapabilities', "/", str(True))

        self.dlg.inProjectTitle.setText(p_title)
        self.dlg.inProjectAbstract.setText(p_abstract)

    def on_project_property_changed(self, prop: str) -> str | None:
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

        # Store value into the project
        xml = self.projectPropertiesInputs[prop]['xml']
        self.project.writeEntry('PluginDynamicLayers', xml, val)
        self.project.setDirty(True)

    def populate_project_properties(self):
        """
        Fill in the project properties item
        from XML
        """
        # Fill the property from the PluginDynamicLayers XML
        for prop, item in self.projectPropertiesInputs.items():
            widget = item['widget']
            xml = self.projectPropertiesInputs[prop]['xml']
            val = self.project.readEntry('PluginDynamicLayers', xml)
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
    def on_apply_variables_clicked(self, source: str = 'table'):
        """
        Replace layers datasource with new datasource created
        by replace variables in dynamicDatasource
        """
        if not self.initDone:
            return

        with OverrideCursor(QtVar.WaitCursor):

            # Use the engine class to do the job
            engine = DynamicLayersEngine()

            # Set the dynamic layers list
            engine.set_dynamic_layers_from_project(self.project)

            # Set search and replace dictionary
            # Collect variables names and values
            if source == 'table':
                search_and_replace_dictionary = {}
                for row in range(self.dlg.twVariableList.rowCount()):
                    v_name = self.dlg.twVariableList.item(row, 0).data(QtVar.EditRole)
                    v_value = self.dlg.twVariableList.item(row, 1).data(QtVar.EditRole)
                    search_and_replace_dictionary[v_name] = v_value
                engine.search_and_replace_dictionary = search_and_replace_dictionary
            else:
                layer = self.dlg.inVariableSourceLayer.currentLayer()
                exp = self.dlg.inVariableSourceLayerExpression.text()
                engine.set_search_and_replace_dictionary_from_layer(layer, exp)

            # Change layers datasource
            engine.set_dynamic_layers_datasource_from_dic()

            # Set project properties
            engine.set_dynamic_project_properties(self.project)

            # Set extent layer
            engine.extent_layer = self.dlg.inExtentLayer.currentLayer()

            # Set extent margin
            engine.extent_margin = self.dlg.inExtentMargin.value()

            # Set new extent
            engine.set_project_extent(self.project)

            # Set project as dirty
            self.project.setDirty(True)

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
        self.dlg.exec()
