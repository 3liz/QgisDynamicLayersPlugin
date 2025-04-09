__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import re

from functools import partial
from pathlib import Path
from typing import Optional, Union

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsIconUtils,
    QgsMapLayer,
    QgsMapLayerProxyModel,
    QgsMessageLog,
    QgsProcessingException,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsExpressionBuilderDialog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon, QTextCursor
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QTableWidgetItem,
    QTextEdit,
    QWidget,
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
from dynamic_layers.tools import (
    format_expression,
    log_message,
    open_help,
    resources_path,
    tr,
)

folder = Path(__file__).resolve().parent
ui_file = folder / 'resources' / 'ui' / 'dynamic_layers_dialog_base.ui'
FORM_CLASS, _ = uic.loadUiType(ui_file)


class DynamicLayersDialog(QDialog, FORM_CLASS):
    # noinspection PyArgumentList
    def __init__(self, parent: QDialog = None):
        """Constructor."""
        # noinspection PyArgumentList
        super().__init__(parent)
        self.setupUi(self)
        self.project = QgsProject.instance()
        self.tab_widget.setCurrentIndex(0)
        self.is_expression = True
        self.button_box.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.close)

        self.btAddVariable.setText("")
        self.btAddVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyAdd.svg')))
        self.btAddVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))
        self.btRemoveVariable.setText("")
        self.btRemoveVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))

        self.btClearLog.setIcon(QIcon(":/images/themes/default/console/iconClearConsole.svg"))

        self.btCopyFromLayer.setIcon(QIcon(QgsApplication.iconPath('mActionEditCopy.svg')))
        self.btCopyFromProject.setIcon(QIcon(QgsApplication.iconPath('mActionEditCopy.svg')))

        self.inExtentLayer.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
        self.inExtentLayer.setAllowEmptyLayer(True)

        self.inVariableSourceLayer.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
        self.inVariableSourceLayer.setAllowEmptyLayer(False)

        self.selected_layer = None
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

        self.selected_layer = None

        # Variables
        self.variableList = []

        self.tab_widget.setTabIcon(
            self.tab_widget.indexOf(self.tab_layers),
            QIcon(QgsApplication.iconPath('mActionLayoutManager.svg'))
        )
        self.tab_widget.setTabIcon(
            self.tab_widget.indexOf(self.tab_project),
            QIcon(QgsApplication.iconPath('mIconFolderProject.svg'))
        )
        self.tab_widget.setTabIcon(
            self.tab_widget.indexOf(self.tab_variables),
            QIcon(QgsApplication.iconPath('mIconExpression.svg'))
        )
        self.tab_widget.setTabIcon(
            self.tab_widget.indexOf(self.tab_log),
            QIcon(QgsApplication.iconPath('mMessageLog.svg'))
        )
        self.tab_widget.setTabIcon(
            self.tab_widget.indexOf(self.tab_about),
            QIcon(QgsApplication.iconPath('mActionHelpContents.svg'))
        )

        self.inFeatureSourceLayer.setShowBrowserButtons(True)
        self.inVariableSourceLayer.layerChanged.connect(self.source_layer_changed)
        self.source_layer_changed()

        help_variables_table = tr("You can add or remove variables in the table by using the form at the bottom.")
        widgets = (
            self.radio_variables_from_table,
            self.twVariableList,
            self.label_name_variable,
            self.inVariableName,
            self.label_value_variable,
            self.inVariableValue,
            self.btAddVariable,
            self.btRemoveVariable,
        )
        for widget in widgets:
            widget: QWidget
            widget.setToolTip(help_variables_table)

        self.is_table_variable_based = False
        self.radio_variables_from_layer.setChecked(not self.is_table_variable_based)
        self.radio_variables_from_table.setChecked(self.is_table_variable_based)
        self.radio_variables_from_layer.toggled.connect(self.origin_variable_toggled)
        self.origin_variable_toggled()

        self.expression_widgets = []
        temporary_list_expressions = [
            # Project server properties
            self.inProjectTitle_exp,
            self.inProjectShortName_exp,
            self.inProjectAbstract_exp,
            # Layer
            self.dynamicDatasourceContent_exp,
            self.dynamic_name_content_exp,
            self.titleTemplate_exp,
            self.abstractTemplate_exp,
        ]
        if not self.is_expression:
            for widget in temporary_list_expressions:
                widget.setVisible(False)
        self.expression_widgets.extend(temporary_list_expressions)
        for widget in self.expression_widgets:
            widget.setText("")
            widget.setToolTip("")
            widget.setIcon(QIcon(QgsApplication.iconPath('mIconExpression.svg')))
            widget.clicked.connect(partial(self.open_expression_builder, widget.objectName()))

            widget = self.input_expression_widget(widget.objectName())
            if isinstance(widget, QLineEdit):
                # QLineEdit
                widget.editingFinished.connect(partial(self.validate_expression, widget.objectName()))
            else:
                # QPlainTextEdit
                widget.textChanged.connect(partial(self.validate_expression, widget.objectName()))

        # Log
        self.btClearLog.clicked.connect(self.clear_log)

        # slots/signals
        ###############

        # Actions when row selection changes
        self.twLayers.selectionModel().selectionChanged.connect(self.on_row_selection_changed)

        # Actions when the layer properties are changed panel
        self.cbDatasourceActive.stateChanged.connect(self.on_cb_datasource_active_change)
        self.btCopyFromLayer.clicked.connect(self.on_copy_from_layer)

        self.layerPropertiesInputs = {
            'datasource': {
                'widget': self.dynamicDatasourceContent,
                'wType': WidgetType.PlainText,
                'xml': LayerPropertiesXml.DynamicDatasourceContent,
            },
            'name': {
                'widget': self.dynamic_name_content,
                'wType': WidgetType.Text,
                'xml': LayerPropertiesXml.NameTemplate,
            },
            'title': {
                'widget': self.titleTemplate,
                'wType': WidgetType.Text,
                'xml': LayerPropertiesXml.TitleTemplate,
            },
            'abstract': {
                'widget': self.abstractTemplate,
                'wType': WidgetType.PlainText,
                'xml': LayerPropertiesXml.AbstractTemplate,
            },
        }
        for key, item in self.layerPropertiesInputs.items():
            control = item['widget']
            slot = partial(self.on_layer_property_change, key)
            control.textChanged.connect(slot)

        # Actions of the Variable tab
        self.btAddVariable.clicked.connect(self.on_add_variable_clicked)
        self.btRemoveVariable.clicked.connect(self.on_remove_variable_clicked)

        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.on_apply_variables_clicked)
        self.button_box.button(QDialogButtonBox.StandardButton.Help).clicked.connect(open_help)

        # Project properties tab
        self.btCopyFromProject.clicked.connect(self.on_copy_from_project_clicked)

        self.projectPropertiesInputs = {
            'title': {
                'widget': self.inProjectTitle,
                'wType': WidgetType.Text,
                'xml': PluginProjectProperty.Title,
            },
            'abstract': {
                'widget': self.inProjectAbstract,
                'wType': WidgetType.PlainText,
                'xml': PluginProjectProperty.Abstract,
            },
            'shortname': {
                'widget': self.inProjectShortName,
                'wType': WidgetType.Text,
                'xml': PluginProjectProperty.ShortName,
            },
            'extentLayer': {
                'widget': self.inExtentLayer,
                'wType': WidgetType.List,
                'xml': PluginProjectProperty.ExtentLayer,
            },
            'extentMargin': {
                'widget': self.inExtentMargin,
                'wType': WidgetType.SpinBox,
                'xml': PluginProjectProperty.ExtentMargin,
            },
            'variableSourceLayer': {
                'widget': self.inVariableSourceLayer,
                'wType': WidgetType.List,
                'xml': PluginProjectProperty.VariableSourceLayer,
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

    def populate_layer_table(self):
        """
        Fill the table for a given layer type
        """
        # empty previous content
        for row in range(self.twLayers.rowCount()):
            self.twLayers.removeRow(row)
        self.twLayers.setRowCount(0)

        # create columns and header row
        columns = [a['display'] for a in self.layersTable]
        col_count = len(columns)
        self.twLayers.setColumnCount(col_count)
        self.twLayers.setHorizontalHeaderLabels(tuple(columns))
        header = self.twLayers.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # load content from project layers
        for layer in self.project.mapLayers().values():

            line_data = []

            # Set row and column count
            tw_row_count = self.twLayers.rowCount()
            # add a new line
            self.twLayers.setRowCount(tw_row_count + 1)
            self.twLayers.setColumnCount(col_count)

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
                self.twLayers.setItem(tw_row_count, i, new_item)

    def on_cb_datasource_active_change(self):
        """
        Toggle the status "dynamicDatasourceActive" for the selected layer
        when the user uses the checkbox
        """
        if not self.selected_layer:
            return

        # Get selected lines
        lines = self.twLayers.selectionModel().selectedRows()
        if len(lines) != 1:
            return

        row = lines[0].row()

        # Get the status of active checkbox
        input_value = self.cbDatasourceActive.isChecked()

        # Change layer line background color in the table
        if self.cbDatasourceActive.isChecked():
            bg = QtVar.Green
        else:
            bg = QtVar.Transparent

        for i in range(0, len(self.layerPropertiesInputs) - 2):
            self.twLayers.item(row, i).setBackground(bg)

        # Change data for the corresponding column in the layers table
        self.twLayers.item(row, 1).setData(QtVar.EditRole, '✔' if input_value else '')

        # Record the new value in the project
        self.selected_layer.setCustomProperty(CustomProperty.DynamicDatasourceActive, input_value)
        self.project.setDirty(True)

    def on_layer_property_change(self, key: str):
        """
        Set the layer template property
        when the user change the content
        of the corresponding text input
        """
        if not self.selected_layer:
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
        self.selected_layer.setCustomProperty(item['xml'], input_value.strip())
        self.project.setDirty(True)

    def on_copy_from_layer(self):
        """
        Get the layer datasource and copy it in the dynamic datasource text input
        """
        if not self.selected_layer:
            return

        # Get the layer datasource
        uri = format_expression(self.selected_layer.dataProvider().dataSourceUri().split('|')[0], self.is_expression)
        abstract = format_expression(self.selected_layer.abstract(), self.is_expression)
        title = format_expression(self.selected_layer.title(), self.is_expression)
        name = format_expression(self.selected_layer.name(), self.is_expression)

        # Previous values
        previous_uri = self.dynamicDatasourceContent.toPlainText()
        previous_abstract = self.abstractTemplate.toPlainText()
        previous_title = self.titleTemplate.text()
        previous_name = self.titleTemplate.text()

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
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(tr('Replace settings by layer properties'))
            box.setText(tr(
                'You have already set some values for this layer, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            result = box.exec()
            if result == QMessageBox.StandardButton.No:
                return

        self.dynamicDatasourceContent.setPlainText(uri)
        self.abstractTemplate.setPlainText(abstract)
        self.titleTemplate.setText(title)
        self.dynamic_name_content.setText(name)

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
        for row in range(self.twVariableList.rowCount()):
            self.twVariableList.removeRow(row)
        self.twVariableList.setRowCount(0)
        self.twVariableList.setColumnCount(2)

        header = self.twVariableList.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        # Fill the table
        for i, variable in enumerate(variable_list[0]):
            self.twVariableList.setRowCount(i + 1)

            # Set name item
            new_item = QTableWidgetItem(variable)
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)
            self.twVariableList.setItem(i, 0, new_item)

            # Set empty value item
            new_item = QTableWidgetItem()
            new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
            self.twVariableList.setItem(i, 1, new_item)

        # Set the variable list
        self.variableList = variable_list[0]

    ##
    # Project properties tab
    ##

    def on_copy_from_project_clicked(self):
        """
        Get project properties and set the input of the project tab
        """
        # Check if project has got some WMS capabilities
        # Title
        p_title = ''
        if self.project.readEntry(PluginProjectProperty.Title, PLUGIN_SCOPE_KEY):
            p_title = self.project.readEntry(PluginProjectProperty.Title, PLUGIN_SCOPE_KEY)[0]
        if not p_title and self.project.readEntry(WmsProjectProperty.Title, "/"):
            p_title = self.project.readEntry(WmsProjectProperty.Title, "/")[0]

        p_title = format_expression(p_title, self.is_expression)

        # Shortname
        p_shortname = ''
        if self.project.readEntry(PluginProjectProperty.ShortName, PLUGIN_SCOPE_KEY):
            p_shortname = self.project.readEntry(PluginProjectProperty.ShortName, PLUGIN_SCOPE_KEY)[0]
        if not p_shortname and self.project.readEntry(WmsProjectProperty.ShortName, "/"):
            p_shortname = self.project.readEntry(WmsProjectProperty.ShortName, "/")[0]

        p_shortname = format_expression(p_shortname, self.is_expression)

        # Abstract
        p_abstract = ''
        if self.project.readEntry(PluginProjectProperty.Abstract, PLUGIN_SCOPE_KEY):
            p_abstract = self.project.readEntry(PluginProjectProperty.Abstract, PLUGIN_SCOPE_KEY)[0]
        if not p_abstract and self.project.readEntry(WmsProjectProperty.Abstract, "/"):
            p_abstract = self.project.readEntry(WmsProjectProperty.Abstract, "/")[0]

        p_abstract = format_expression(p_abstract, self.is_expression)

        ask = False
        previous_title = self.inProjectTitle.text()
        if previous_title != '' and previous_title != p_title:
            ask = True

        previous_shortname = self.inProjectShortName.text()
        if previous_shortname != '' and previous_shortname != p_shortname:
            ask = True

        previous_abstract = self.inProjectAbstract.toPlainText()
        if previous_abstract != '' and previous_abstract != p_abstract:
            ask = True

        if ask:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            # noinspection PyArgumentList
            box.setWindowIcon(QIcon(str(resources_path('icons', 'icon.png'))))
            box.setWindowTitle(tr('Replace settings by project properties'))
            box.setText(tr(
                'You have already set some values for this project, are you sure you want to reset these ?'))
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            result = box.exec()
            if result == QMessageBox.StandardButton.No:
                return

        if not self.project.readEntry(WmsProjectProperty.Capabilities, "/")[1]:
            self.project.writeEntry(WmsProjectProperty.Capabilities, "/", True)

        self.inProjectTitle.setText(p_title)
        self.inProjectAbstract.setPlainText(p_abstract)
        self.inProjectShortName.setText(p_shortname)

    def on_project_property_changed(self, prop: str) -> Optional[str]:
        """ Save project dynamic property in the project. """
        widget = self.projectPropertiesInputs[prop]['widget']
        if prop in ('title', 'shortname'):
            val = widget.text()
        elif prop == 'abstract':
            val = widget.toPlainText()
        elif prop in ('extentLayer', 'variableSourceLayer'):
            layer = widget.currentLayer()
            if not layer:
                return None
            val = layer.id()
        elif prop == 'extentMargin':
            val = widget.value()
        else:
            log_message(f'Unknown widget {prop}, please ask the developer', Qgis.Critical, None)
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
        # Save all values from the project level
        for key, item in self.projectPropertiesInputs.items():
            self.on_project_property_changed(key)

        try:
            with OverrideCursor(QtVar.WaitCursor):

                # Use the engine class to do the job
                engine = DynamicLayersEngine()

                # Set the dynamic layers list
                engine.discover_dynamic_layers_from_project(self.project)

                # Set search and replace dictionary
                # Collect variables names and values
                if self.is_table_variable_based:
                    engine.variables = self.variables()
                else:
                    layer = self.inVariableSourceLayer.currentLayer()
                    feature = self.inFeatureSourceLayer.feature()
                    engine.set_layer_and_feature(layer, feature)

                # Change layers datasource
                engine.update_dynamic_layers_datasource()

                # Set project properties
                engine.update_dynamic_project_properties()

                engine.force_refresh_all_layer_extents()

                # Set extent layer and margin
                engine.update_project_extent()

        except QgsProcessingException as e:
            log_message(str(e), Qgis.Critical, None)
            self.message_bar.pushCritical(tr("Parsing expression error"), str(e))
            return

        # Set project as dirty
        self.project.setDirty(True)
        self.message_bar.pushSuccess("👍", tr("Current project has been updated"))

    def origin_variable_toggled(self):
        """ Radio buttons to choose the origin of variables. """
        self.is_table_variable_based = self.radio_variables_from_table.isChecked()
        self.widget_layer.setEnabled(not self.is_table_variable_based)
        self.widget_table.setEnabled(self.is_table_variable_based)

    def variables(self) -> dict[str, str]:
        """ The list of variables in the table. """
        if not self.is_table_variable_based:
            return {}

        data: dict[str, str] = {}
        for row in range(self.twVariableList.rowCount()):
            v_name = self.twVariableList.item(row, 0).data(QtVar.EditRole)
            v_value = self.twVariableList.item(row, 1).data(QtVar.EditRole)
            data[v_name] = v_value
        return data

    def source_layer_changed(self):
        """ Update the feature picker widget when the layer has changed. """
        layer = self.inVariableSourceLayer.currentLayer()
        if not isinstance(layer, QgsVectorLayer):
            return
        self.inFeatureSourceLayer.setLayer(self.inVariableSourceLayer.currentLayer())

    @staticmethod
    def text_widget(widget) -> str:
        """ Current text in the widget. """
        if isinstance(widget, QLineEdit):
            # QLineEdit
            return widget.text()
        else:
            # QPlainTextEdit
            return widget.toPlainText()

    def validate_expression(self, source: str):
        """ Show a warning background if the expression is incorrect. """
        widget = getattr(self, source)
        text_input = self.text_widget(widget)
        expression = QgsExpression(self.text_widget(widget))
        if text_input and (expression.hasEvalError() or expression.hasParserError()):
            if isinstance(widget, QLineEdit):
                icon = QIcon(":/images/themes/default/mIconWarning.svg")
                widget.addAction(icon, QLineEdit.ActionPosition.LeadingPosition)
            else:
                widget.setStyleSheet("background-color: #55f3bc3c")
        else:
            actions = widget.actions()
            if actions:
                widget.removeAction(actions[0])
            if isinstance(widget, QPlainTextEdit):
                widget.setStyleSheet("")

    def open_expression_builder(self, source: str):
        """ Open the expression builder helper. """
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())
        context.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))

        if self.is_table_variable_based:
            layer = None
            scope = QgsExpressionContextScope()
            for key, value in self.variables().items():
                scope.addVariable(QgsExpressionContextScope.StaticVariable(key, value))
        else:
            layer = self.inVariableSourceLayer.currentLayer()
            if not layer:
                return
            scope = QgsExpressionContextUtils.layerScope(layer)

        context.appendScope(scope)

        widget = self.input_expression_widget(source)

        if layer:
            QgsMessageLog.logMessage(
                f'Layer set in the expression builder : {layer.name()}',
                PLUGIN_MESSAGE,
                Qgis.Info,
            )
        else:
            QgsMessageLog.logMessage(
                f'List of variables : {",".join([j for j in self.variables().keys()])}',
                PLUGIN_MESSAGE,
                Qgis.Info,
            )

        dialog = QgsExpressionBuilderDialog(layer, context=context)
        dialog.setExpressionText(self.text_widget(widget))
        result = dialog.exec()

        if result != QDialog.DialogCode.Accepted:
            return

        content = dialog.expressionText()

        if isinstance(widget, QLineEdit):
            widget.setText(content)
        else:
            widget.setPlainText(content)

    def input_expression_widget(self, source) -> Union[QLineEdit, QTextEdit]:
        """ Return the associated input text widget associated with an expression button. """
        return getattr(self, source.replace("_exp", ""))

    def on_row_selection_changed(self):
        """
        Change content of dynamic properties group inputs
        When the user selects a layer in the table
        """
        # Get selected lines
        lines = self.twLayers.selectionModel().selectedRows()
        if len(lines) < 1:
            return

        row = lines[0].row()
        layer_id = self.twLayers.item(row, 0).data(QtVar.UserRole)
        self.selected_layer = self.project.mapLayer(layer_id)

        # Toggle the layer properties group
        self.gbLayerDynamicProperties.setEnabled(self.selected_layer is not None)

        if not self.selected_layer:
            return

        # Set the content of the layer properties inputs
        # dynamic datasource text input content
        for key, item in self.layerPropertiesInputs.items():
            widget = item['widget']
            val = self.selected_layer.customProperty(item['xml'])
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
        is_active = self.selected_layer.customProperty(CustomProperty.DynamicDatasourceActive)
        if is_active is None:
            is_active = False

        if isinstance(is_active, str):
            # Temporary to migrate old projects containing string variables
            # Now, only boolean variables are saved as custom property
            is_active = True if is_active == str(True) else False

        self.cbDatasourceActive.setChecked(is_active)

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

    def on_add_variable_clicked(self):
        """
        Add a variable to the list from the text input
        when the user clicks on the corresponding button
        """
        # Get table and row count
        tw_row_count = self.twVariableList.rowCount()

        # Get input data
        v_name = self.inVariableName.text().strip(' \t')
        v_value = self.inVariableValue.text().strip(' \t')

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
        self.twVariableList.setRowCount(tw_row_count + 1)
        self.twVariableList.setColumnCount(2)

        # Empty the name text input
        self.inVariableName.setText('')

        # Add the new "variable" item to the table
        # name
        new_item = QTableWidgetItem()
        new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEnabled)
        new_item.setData(QtVar.EditRole, v_name)
        self.twVariableList.setItem(tw_row_count, 0, new_item)

        # value
        new_item = QTableWidgetItem()
        new_item.setFlags(QtVar.ItemIsSelectable | QtVar.ItemIsEditable | QtVar.ItemIsEnabled)
        new_item.setData(QtVar.EditRole, v_value)
        self.twVariableList.setItem(tw_row_count, 1, new_item)

        # Add variable to the list
        self.variableList.append(v_name)

        # Add variable to the project
        self.project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.VariableList, self.variableList)
        self.project.setDirty(True)

    def on_variable_item_changed(self, item):
        """ Change the variable item. """
        # Get row and column
        col = item.column()

        # Only allow edition of value
        if col != 1:
            return

        # Unselect row and item
        self.twVariableList.clearSelection()

        # Get changed property
        # data = tw.item(row, col).data(Qt.EditRole)

    def on_remove_variable_clicked(self):
        """
        Remove a variable from the table
        When the users click on the remove button
        """
        # Get selected lines
        lines = self.twVariableList.selectionModel().selectedRows()
        if len(lines) != 1:
            return

        row = lines[0].row()

        # Get variable name
        v_name = self.twVariableList.item(row, 0).data(QtVar.EditRole)

        # Remove variable name from list
        self.variableList.remove(v_name)

        # Update project
        self.project.writeEntry(PLUGIN_SCOPE, PluginProjectProperty.VariableList, self.variableList)
        self.project.setDirty(True)

        # Remove selected lines
        self.twVariableList.removeRow(self.twVariableList.currentRow())

    def clear_log(self):
        """ Clear the log. """
        self.txtLog.clear()

    def update_log(self, msg: str):
        """ Update the log. """
        # Should we deprecate this log panel and instead add a button to open the QGIS log panel ?
        # noinspection PyTypeChecker
        QgsMessageLog.logMessage(msg, PLUGIN_MESSAGE, Qgis.Success)

        self.txtLog.ensureCursorVisible()
        prefix = '<span style="font-weight:normal;">'
        suffix = '</span>'
        self.txtLog.append(f'{prefix} {msg} {suffix}')
        c = self.txtLog.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.MoveAnchor)
        self.txtLog.setTextCursor(c)
        QApplication.instance().processEvents()
