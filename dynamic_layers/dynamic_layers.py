__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import re

from functools import partial
from pathlib import Path
from typing import Optional

from qgis import processing
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsIconUtils,
    QgsMapLayer,
    QgsMapLayerProxyModel,
    QgsMessageLog,
    QgsProcessingException,
    QgsProject,
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QTextCursor
from qgis.PyQt.QtWidgets import (
    QAction,
    QDialogButtonBox,
    QHeaderView,
    QMenu,
    QMessageBox,
    QTableWidgetItem,
    qApp,
)
from qgis.utils import OverrideCursor

from dynamic_layers.core.dynamic_layers_engine import DynamicLayersEngine
from dynamic_layers.definitions import (
    PLUGIN_MESSAGE,
    PLUGIN_SCOPE,
    PLUGIN_SCOPE_KEY,
    CustomProperty,
    LayerPropertiesXml,
    PluginProjectProperty,
    QtVar,
    WidgetType,
    WmsProjectProperty,
)
from dynamic_layers.dynamic_layers_dialog import DynamicLayersDialog
from dynamic_layers.processing_provider.provider import Provider
from dynamic_layers.tools import plugin_path, resources_path, tr


class DynamicLayers:
    """QGIS Plugin Implementation."""

    def __init__(self, iface: QgisInterface):
        """Constructor."""
        self.projectPropertiesInputs = None
        self.layerPropertiesInputs = None
        self.initDone = None
        # Save reference to the QGIS interface
        self.iface = iface
        self.provider = None

        self.main_icon = QIcon(str(resources_path('icons', 'icon.png')))
        self.help_action_about_menu = None
        self.menu = None
        self.main_dialog_action = None
        self.generate_projects_action = None

        # initialize plugin directory
        self.plugin_dir = Path(__file__).resolve().parent
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = plugin_path('i18n', f'qgis_plugin_{locale}.qm')
        if locale_path.exists():
            # noinspection PyArgumentList
            self.translator = QTranslator()
            self.translator.load(str(locale_path))
            # noinspection PyUnresolvedReferences
            QgsMessageLog.logMessage(f'Translation file {locale_path} found', PLUGIN_MESSAGE, Qgis.Success)
            # noinspection PyArgumentList
            QCoreApplication.installTranslator(self.translator)

        # noinspection PyArgumentList
        self.project = QgsProject.instance()

        # Create the dialog (after translation) and keep reference
        self.dlg = DynamicLayersDialog()
        self.is_expression = self.dlg.is_expression

        # Layers attribute that can be shown and optionally changed in the plugin
        self.layersTable = [
            {
                'key': 'name',
                'display': tr('Name'),
                'editable': False,
                'type': 'string'
            }, {
                'key': 'dynamicDatasourceActive',
                'display': tr('Dynamic Datasource Active'),
                'editable': False,
                'type': 'string'
            },
        ]

        # Keep record of style widget
        self.selectedLayerWidget = None
        self.selectedLayer = None

        # Variables
        self.variableList = []

    # noinspection PyPep8Naming
    def initProcessing(self):
        self.provider = Provider()
        # noinspection PyArgumentList
        QgsApplication.processingRegistry().addProvider(self.provider)

    # noinspection PyPep8Naming
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.menu = QMenu("Dynamic Layers")
        self.menu.setIcon(self.main_icon)

        self.main_dialog_action = QAction(self.main_icon, tr("Setup the project"), self.iface.mainWindow())
        # noinspection PyUnresolvedReferences
        self.main_dialog_action.triggered.connect(self.run)
        self.menu.addAction(self.main_dialog_action)

        # noinspection PyArgumentList
        self.generate_projects_action = QAction(
            QIcon(QgsApplication.iconPath("processingAlgorithm.svg")),
            tr("Generate projects"),
            self.iface.mainWindow()
        )
        # noinspection PyUnresolvedReferences
        self.generate_projects_action.triggered.connect(self.generate_projects_clicked)
        self.menu.addAction(self.generate_projects_action)

        self.iface.pluginMenu().addMenu(self.menu)

        self.initProcessing()

        # Open the online help
        self.help_action_about_menu = QAction(self.main_icon, tr('Project generator'), self.iface.mainWindow())
        self.iface.pluginHelpMenu().addAction(self.help_action_about_menu)
        # noinspection PyUnresolvedReferences
        self.help_action_about_menu.triggered.connect(self.open_help)

        # slots/signals
        ###############
        self.initDone = False

        # Actions when row selection changes
        self.dlg.twLayers.selectionModel().selectionChanged.connect(self.on_row_selection_changed)

        # Actions when the layer properties are changed panel
        self.dlg.cbDatasourceActive.stateChanged.connect(self.on_cb_datasource_active_change)
        self.dlg.btCopyFromLayer.clicked.connect(self.on_copy_from_layer)

        self.layerPropertiesInputs = {
            'datasource': {
                'widget': self.dlg.dynamicDatasourceContent,
                'wType': WidgetType.PlainText,
                'xml': LayerPropertiesXml.DynamicDatasourceContent,
            },
            'name': {
                'widget': self.dlg.dynamic_name_content,
                'wType': WidgetType.Text,
                'xml': LayerPropertiesXml.NameTemplate,
            },
            'title': {
                'widget': self.dlg.titleTemplate,
                'wType': WidgetType.Text,
                'xml': LayerPropertiesXml.TitleTemplate,
            },
            'abstract': {
                'widget': self.dlg.abstractTemplate,
                'wType': WidgetType.PlainText,
                'xml': LayerPropertiesXml.AbstractTemplate,
            },
        }
        for key, item in self.layerPropertiesInputs.items():
            control = item['widget']
            slot = partial(self.on_layer_property_change, key)
            control.textChanged.connect(slot)

        # Actions of the Variable tab
        self.dlg.btAddVariable.clicked.connect(self.on_add_variable_clicked)
        self.dlg.btRemoveVariable.clicked.connect(self.on_remove_variable_clicked)

        self.dlg.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.on_apply_variables_clicked)
        self.dlg.button_box.button(QDialogButtonBox.Help).clicked.connect(self.open_help)

        # Project properties tab
        self.dlg.btCopyFromProject.clicked.connect(self.on_copy_from_project_clicked)

        self.projectPropertiesInputs = {
            'title': {
                'widget': self.dlg.inProjectTitle,
                'wType': WidgetType.Text,
                'xml': PluginProjectProperty.Title,
            },
            'abstract': {
                'widget': self.dlg.inProjectAbstract,
                'wType': WidgetType.PlainText,
                'xml': PluginProjectProperty.Abstract,
            },
            'shortname': {
                'widget': self.dlg.inProjectShortName,
                'wType': WidgetType.Text,
                'xml': PluginProjectProperty.ShortName,
            },
            'extentLayer': {
                'widget': self.dlg.inExtentLayer,
                'wType': WidgetType.List,
                'xml': PluginProjectProperty.ExtentLayer,
            },
            'extentMargin': {
                'widget': self.dlg.inExtentMargin,
                'wType': WidgetType.SpinBox,
                'xml': PluginProjectProperty.ExtentMargin,
            },
            'variableSourceLayer': {
                'widget': self.dlg.inVariableSourceLayer,
                'wType': WidgetType.List,
                'xml': PluginProjectProperty.VariableSourceLayer,
            },
            'variableSourceLayerExpression': {
                'widget': self.dlg.inVariableSourceLayerExpression,
                'wType': WidgetType.Text,
                'xml': PluginProjectProperty.VariableSourceLayerExpression,
            },
        }
        for key, item in self.projectPropertiesInputs.items():
            slot = partial(self.on_project_property_changed, key)
            control = item['widget']
            if item['wType'] in (WidgetType.Text, WidgetType.SpinBox):
                control.editingFinished.connect(slot)
            elif item['wType'] == WidgetType.PlainText:
                control.textChanged.connect(slot)
            elif item['wType'] == WidgetType.List:
                control.currentIndexChanged.connect(slot)

        # Log
        self.dlg.btClearLog.clicked.connect(self.clear_log)

    @staticmethod
    def open_help():
        """Opens the html help file content with default browser"""
        # noinspection PyArgumentList
        QDesktopServices.openUrl(QUrl("https://docs.3liz.org/QgisDynamicLayersPlugin/"))

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        if self.provider:
            # noinspection PyArgumentList
            QgsApplication.processingRegistry().removeProvider(self.provider)

        if self.generate_projects_action:
            self.iface.removePluginMenu("Dynamic Layers", self.generate_projects_action)
            del self.generate_projects_action

        if self.main_dialog_action:
            self.iface.removePluginMenu("Dynamic Layers", self.main_dialog_action)
            del self.main_dialog_action

        if self.help_action_about_menu:
            self.iface.pluginHelpMenu().removeAction(self.help_action_about_menu)
            del self.help_action_about_menu

    def clear_log(self):
        """ Clear the log. """
        self.dlg.txtLog.clear()

    def update_log(self, msg: str):
        """ Update the log. """
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
        header = self.dlg.twLayers.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        # load content from project layers
        for layer in self.project.mapLayers().values():

            line_data = []

            # Set row and column count
            tw_row_count = self.dlg.twLayers.rowCount()
            # add a new line
            self.dlg.twLayers.setRowCount(tw_row_count + 1)
            self.dlg.twLayers.setColumnCount(col_count)

            custom_property = layer.customProperty(CustomProperty.DynamicDatasourceActive)
            if isinstance(custom_property, str):
                # Temporary to migrate old projects containing string variables
                # Now, only boolean variables are saved as custom property
                custom_property = True if custom_property == str(True) else False

            if custom_property:
                bg = QtVar.Green
            else:
                bg = QtVar.Transparent

            # get information
            for i, attr in enumerate(self.layersTable):
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
                if attr['key'] == 'dynamicDatasourceActive':
                    value = '✔' if value else ''
                new_item.setData(QtVar.EditRole, value)
                if attr['key'] == 'name':
                    # noinspection PyArgumentList
                    new_item.setIcon(QgsIconUtils.iconForLayer(layer))
                    new_item.setData(QtVar.UserRole, layer.id())
                    new_item.setToolTip(layer.id())

                # Add cell data to lineData
                # encode it in the file system encoding, only if needed
                line_data.append(value)

                # Add item
                self.dlg.twLayers.setItem(tw_row_count, i, new_item)

    @staticmethod
    def get_layer_property(layer: QgsMapLayer, prop: str) -> Optional[str]:
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
            layer_id = self.dlg.twLayers.item(row, 0).data(QtVar.UserRole)
            layer = self.project.mapLayer(layer_id)
            if not layer:
                show_layer_properties = False
            else:
                self.selectedLayer = layer

        if not lines or len(lines) != 1:
            show_layer_properties = False

        # Toggle the layer properties group
        self.dlg.gbLayerDynamicProperties.setEnabled(show_layer_properties)

        if not layer:
            return

        # Set the content of the layer properties inputs
        # dynamic datasource text input content
        for key, item in self.layerPropertiesInputs.items():
            widget = item['widget']
            val = layer.customProperty(item['xml'])
            if not val:
                val = ''
            if item['wType'] == WidgetType.Text:
                widget.setText(val)
            elif item['wType'] == WidgetType.PlainText:
                widget.setPlainText(val)
            elif item['wType'] == WidgetType.SpinBox:
                widget.setValue(int(val))
            elif item['wType'] == WidgetType.List:
                list_dic = {widget.itemData(i): i for i in range(widget.count())}
                if val in list_dic:
                    widget.setCurrentIndex(list_dic[val])

        # "active" checkbox
        is_active = layer.customProperty(CustomProperty.DynamicDatasourceActive)
        if is_active is None:
            is_active = False

        if isinstance(is_active, str):
            # Temporary to migrate old projects containing string variables
            # Now, only boolean variables are saved as custom property
            is_active = True if is_active == str(True) else False

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
        input_value = self.dlg.cbDatasourceActive.isChecked()

        # Change layer line background color in the table
        if self.dlg.cbDatasourceActive.isChecked():
            bg = QtVar.Green
        else:
            bg = QtVar.Transparent

        for i in range(0, len(self.layerPropertiesInputs) - 2):
            self.dlg.twLayers.item(row, i).setBackground(bg)

        # Change data for the corresponding column in the layers table
        self.dlg.twLayers.item(row, 1).setData(QtVar.EditRole, '✔' if input_value else '')

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
        if item['wType'] == WidgetType.PlainText:
            input_value = item['widget'].toPlainText()
        if item['wType'] == WidgetType.Text:
            input_value = item['widget'].text()

        if input_value == "''":
            input_value = ''

        # Record the new value in the project
        self.selectedLayer.setCustomProperty(item['xml'], input_value.strip())
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
        name = self.selectedLayer.name()

        # Previous values
        previous_uri = self.dlg.dynamicDatasourceContent.toPlainText()
        previous_abstract = self.dlg.abstractTemplate.toPlainText()
        previous_title = self.dlg.titleTemplate.text()
        previous_name = self.dlg.titleTemplate.text()

        ask = False
        if previous_uri != '' and previous_uri != uri:
            ask = True
        if previous_abstract != '' and previous_abstract != abstract:
            ask = True
        if previous_name != '' and previous_name != name:
            ask = True
        if previous_title != '' and previous_title != title:
            ask = True

        if ask:
            box = QMessageBox(self.dlg)
            box.setIcon(QMessageBox.Question)
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(tr('Replace settings by layer properties'))
            box.setText(tr(
                'You have already set some values for this layer, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            result = box.exec_()
            if result == QMessageBox.No:
                return

        # Set the dynamic datasource content input
        self.dlg.dynamicDatasourceContent.setPlainText(f"'{uri}'" if self.is_expression else uri)

        # Set templates for title and abstract
        self.dlg.abstractTemplate.setPlainText(f"'{abstract}'" if self.is_expression else abstract)

        self.dlg.titleTemplate.setText(f"'{title}'" if self.is_expression else title)

        self.dlg.dynamic_name_content.setText(f"'{name}'" if self.is_expression else name)

    ##
    # Variables tab
    ##
    def populate_variable_table(self):
        """
        Fill the variable table
        """
        # Get the list of variable from the project
        variable_list = self.project.readListEntry(PLUGIN_SCOPE, PluginProjectProperty.VariableList)
        if not variable_list:
            return

        # empty previous content
        for row in range(self.dlg.twVariableList.rowCount()):
            self.dlg.twVariableList.removeRow(row)
        self.dlg.twVariableList.setRowCount(0)
        self.dlg.twVariableList.setColumnCount(2)

        header = self.dlg.twVariableList.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        # Fill the table
        for i, variable in enumerate(variable_list[0]):
            self.dlg.twVariableList.setRowCount(i + 1)

            # Set name item
            new_item = QTableWidgetItem(variable)
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)
            self.dlg.twVariableList.setItem(i, 0, new_item)

            # Set empty value item
            new_item = QTableWidgetItem()
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
            self.dlg.twVariableList.setItem(i, 1, new_item)

        # Set the variable list
        self.variableList = variable_list[0]

    def on_add_variable_clicked(self):
        """
        Add a variable to the list from the text input
        when the user clicks on the corresponding button
        """
        if not self.initDone:
            self.update_log(tr('Init was not finished'))
            return

        # Get table and row count
        tw_row_count = self.dlg.twVariableList.rowCount()

        # Get input data
        v_name = self.dlg.inVariableName.text().strip(' \t')
        v_value = self.dlg.inVariableValue.text().strip(' \t')

        # Check if the variable is not already in the list
        if v_name in self.variableList:
            self.update_log(tr('This variable is already in the list'))
            return

        # Add constraint of possible input values
        project = re.compile('^[a-zA-Z]+$')
        if not project.match(v_name):
            self.update_log(tr('The variable must contain only lower case ASCII letters !'))
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
        self.project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.VariableList, self.variableList)
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
        self.project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.VariableList, self.variableList)
        self.project.setDirty(True)

        # Remove selected lines
        self.dlg.twVariableList.removeRow(self.dlg.twVariableList.currentRow())

    def on_variable_item_changed(self, item):
        """ Change the variable item. """
        # Get row and column
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
        if self.project.readEntry(PluginProjectProperty.Title, PLUGIN_SCOPE_KEY):
            p_title = self.project.readEntry(PluginProjectProperty.Title, PLUGIN_SCOPE_KEY)[0]
        if not p_title and self.project.readEntry(WmsProjectProperty.Title, "/"):
            p_title = self.project.readEntry(WmsProjectProperty.Title, "/")[0]

        # Shortname
        p_shortname = ''
        if self.project.readEntry(PluginProjectProperty.ShortName, PLUGIN_SCOPE_KEY):
            p_shortname = self.project.readEntry(PluginProjectProperty.ShortName, PLUGIN_SCOPE_KEY)[0]
        if not p_shortname and self.project.readEntry(WmsProjectProperty.ShortName, "/"):
            p_shortname = self.project.readEntry(WmsProjectProperty.ShortName, "/")[0]

        # Abstract
        p_abstract = ''
        if self.project.readEntry(PluginProjectProperty.Abstract, PLUGIN_SCOPE_KEY):
            p_abstract = self.project.readEntry(PluginProjectProperty.Abstract, PLUGIN_SCOPE_KEY)[0]
        if not p_abstract and self.project.readEntry(WmsProjectProperty.Abstract, "/"):
            p_abstract = self.project.readEntry(WmsProjectProperty.Abstract, "/")[0]

        ask = False
        previous_title = self.dlg.inProjectTitle.text()
        if previous_title != '' and previous_title != p_title:
            ask = True

        previous_shortname = self.dlg.inProjectShortName.text()
        if previous_shortname != '' and previous_shortname != p_shortname:
            ask = True

        previous_abstract = self.dlg.inProjectAbstract.toPlainText()
        if previous_abstract != '' and previous_abstract != p_abstract:
            ask = True

        if ask:
            box = QMessageBox(self.dlg)
            box.setIcon(QMessageBox.Question)
            # noinspection PyArgumentList
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(tr('Replace settings by project properties'))
            box.setText(tr(
                'You have already set some values for this project, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            box.setDefaultButton(QMessageBox.No)
            result = box.exec_()
            if result == QMessageBox.No:
                return

        if not self.project.readEntry(WmsProjectProperty.Capabilities, "/")[1]:
            self.project.writeEntry(WmsProjectProperty.Capabilities, "/", True)

        self.dlg.inProjectTitle.setText(f"'{p_title}'" if self.is_expression else p_title)
        self.dlg.inProjectAbstract.setPlainText(f"'{p_abstract}'" if self.is_expression else p_abstract)

    def on_project_property_changed(self, prop: str) -> Optional[str]:
        """
        Save project dynamic property in the project
        when the user changes the content
        """
        if not self.initDone:
            return None

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
                return None
        elif prop == 'extentMargin':
            val = widget.value()
        else:
            return None

        # Store value into the project
        xml = self.projectPropertiesInputs[prop]['xml']
        self.project.writeEntry(PLUGIN_SCOPE, xml, val)
        self.project.setDirty(True)

    def populate_project_properties(self):
        """ Fill in the project properties item from XML. """
        # Fill the property from the PluginDynamicLayers XML
        for prop, item in self.projectPropertiesInputs.items():
            widget = item['widget']
            xml = self.projectPropertiesInputs[prop]['xml']
            val = self.project.readEntry(PLUGIN_SCOPE, xml)
            if val:
                val = val[0]
            if not val:
                continue
            if item['wType'] == WidgetType.Text:
                widget.setText(val)
            elif item['wType'] == WidgetType.PlainText:
                widget.setPlainText(val)
            elif item['wType'] == WidgetType.SpinBox:
                widget.setValue(int(val))
            elif item['wType'] == WidgetType.List:
                list_dic = {widget.itemData(i): i for i in range(widget.count())}
                if val in list_dic:
                    widget.setCurrentIndex(list_dic[val])

    ##
    # Global actions
    ##
    def on_apply_variables_clicked(self):
        """
        Replace layers datasource with new datasource created
        by replace variables in dynamicDatasource
        """
        if not self.initDone:
            self.dlg.message_bar.pushCritical(tr("Fail"), tr("Initialisation was not finished"))
            return

        try:
            with OverrideCursor(QtVar.WaitCursor):

                # Use the engine class to do the job
                engine = DynamicLayersEngine()

                # Set the dynamic layers list
                engine.discover_dynamic_layers_from_project(self.project)

                # Set search and replace dictionary
                # Collect variables names and values
                if self.dlg.is_table_variable_based:
                    engine.variables = self.dlg.variables()
                else:
                    layer = self.dlg.inVariableSourceLayer.currentLayer()
                    exp = self.dlg.inVariableSourceLayerExpression.text()
                    engine.set_layer_and_expression(layer, exp)

                # Change layers datasource
                engine.update_dynamic_layers_datasource()

                # Set project properties
                engine.update_dynamic_project_properties()

                # Set extent layer
                engine.extent_layer = self.dlg.inExtentLayer.currentLayer()

                # Set extent margin
                engine.extent_margin = self.dlg.inExtentMargin.value()

                # Set new extent
                engine.update_project_extent()
        except QgsProcessingException as e:
            self.dlg.message_bar.pushCritical(tr("Parsing expression error"), str(e))
            return

        # Set project as dirty
        self.project.setDirty(True)
        self.dlg.message_bar.pushSuccess("👍", tr("Current project has been updated"))

    @staticmethod
    def generate_projects_clicked():
        """ Open the Processing algorithm dialog. """
        # noinspection PyUnresolvedReferences
        processing.execAlgorithmDialog(
            "dynamic_layers:generate_projects",
            {}
        )

    def run(self):
        """Run method that performs all the real work"""
        self.initDone = False

        # Populate the layers table
        self.populate_layer_table()

        # Populate the variable table
        self.populate_variable_table()

        # Populate the extent layer list
        self.dlg.inExtentLayer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.dlg.inExtentLayer.setAllowEmptyLayer(True)

        # Populate the variable source layer combobox
        self.dlg.inVariableSourceLayer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.dlg.inVariableSourceLayer.setAllowEmptyLayer(False)

        # Copy project properties to corresponding tab
        self.populate_project_properties()

        self.initDone = True

        # show the dialog
        self.dlg.show()
        self.dlg.exec()
