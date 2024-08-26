__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from functools import partial
from pathlib import Path
from typing import Union

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsMessageLog,
    QgsProject,
)
from qgis.gui import QgsExpressionBuilderDialog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from dynamic_layers.definitions import PLUGIN_MESSAGE, QtVar
from dynamic_layers.tools import tr

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
        self.tab_widget.setCurrentIndex(0)
        self.is_expression = True
        self.button_box.button(QDialogButtonBox.Close).clicked.connect(self.close)

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

        help_variables_layer = tr(
            "Choose a vector layer and then filter the layer with a QGIS expression to have a single feature. In this "
            "case, each field will be used as a variable name with its according field value for the content of the "
            "variable."
        )
        widgets = (
            self.radio_variables_from_layer,
            self.inVariableSourceLayer,
            self.inVariableSourceLayerExpression,
            self.inVariableSourceLayerExpression_exp,
        )
        for widget in widgets:
            widget: QWidget
            widget.setToolTip(help_variables_layer)

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

        self.is_table_variable_based = True
        self.radio_variables_from_table.setChecked(self.is_table_variable_based)
        self.radio_variables_from_layer.toggled.connect(self.origin_variable_toggled)
        self.origin_variable_toggled()

        self.expression_widgets = [
            # Variables
            self.inVariableSourceLayerExpression_exp,
        ]
        temporary_list_expressions = [
            # Project
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

    def origin_variable_toggled(self):
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
                widget.addAction(icon, QLineEdit.LeadingPosition)
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

        if result != QDialog.Accepted:
            return

        content = dialog.expressionText()

        if isinstance(widget, QLineEdit):
            widget.setText(content)
        else:
            widget.setPlainText(content)

    def input_expression_widget(self, source) -> Union[QLineEdit, QTextEdit]:
        """ Return the associated input text widget associated with an expression button. """
        return getattr(self, source.replace("_exp", ""))
