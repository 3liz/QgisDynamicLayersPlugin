__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.core import QgsApplication
from qgis.gui import QgsExpressionBuilderDialog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QWidget

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
        self.button_box.button(QDialogButtonBox.Close).clicked.connect(self.close)

        self.btAddVariable.setText("")
        self.btAddVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyAdd.svg')))
        self.btAddVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))
        self.btRemoveVariable.setText("")
        self.btRemoveVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))

        self.btClearLog.setIcon(QIcon(":/images/themes/default/console/iconClearConsole.svg"))

        self.bt_open_expression.setText("")
        self.bt_open_expression.setToolTip("")
        self.bt_open_expression.setIcon(QIcon(QgsApplication.iconPath('mIconExpression.svg')))
        self.bt_open_expression.clicked.connect(self.open_expression_builder)

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

        help_template = "{}\n{}\n{} {}".format(
            tr(
                'Variables should be written either with $variable or ${variable}.'
            ),
            tr(
                'The second option is necessary if you want to concatenate a dynamic string with a fixed string.'
            ),
            tr(
                'See the Python documentation about "Template strings".'
            ),
            "https://docs.python.org/3/library/string.html#template-strings"
        )
        list_templates = (
            # Project tab
            self.projectTitleLabel,
            self.inProjectTitle,
            self.label_project_shortname_template,
            self.inProjectShortName,
            self.projectDescriptionLabel,
            self.inProjectAbstract,
            # Layers tab
            self.label_datasource_template,
            self.dynamicDatasourceContent,
            self.label_name_template,
            self.dynamic_name_content,
            self.label_title_template,
            self.titleTemplate,
            self.label_abstract_template,
            self.abstractTemplate,
        )
        for widget in list_templates:
            widget: QWidget
            widget.setToolTip(help_template)

        help_variables_layer = tr(
            "Choose a vector layer and then filter the layer with a QGIS expression to have a single feature. In this "
            "case, each field will be used as a variable name with its according field value for the content of the "
            "variable."
        )
        widgets = (
            self.radio_variables_from_layer,
            self.inVariableSourceLayer,
            self.inVariableSourceLayerExpression,
            self.bt_open_expression,
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

        self.radio_variables_from_table.setChecked(True)
        self.radio_variables_from_layer.toggled.connect(self.origin_variable_toggled)
        self.origin_variable_toggled()

    def origin_variable_toggled(self):
        self.widget_layer.setEnabled(self.radio_variables_from_layer.isChecked())
        self.widget_table.setEnabled(not self.radio_variables_from_layer.isChecked())

    def open_expression_builder(self):
        """ Open the expression builder helper. """
        layer = self.inVariableSourceLayer.currentLayer()
        if not layer:
            return

        dialog = QgsExpressionBuilderDialog(layer)
        result = dialog.exec()
        if result != QDialog.Accepted:
            return

        self.inVariableSourceLayerExpression.setText(dialog.expressionText())
