__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.core import QgsApplication
from qgis.gui import QgsExpressionBuilderDialog
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox

folder = Path(__file__).resolve().parent
ui_file = folder / 'resources' / 'ui' / 'dynamic_layers_dialog_base.ui'
FORM_CLASS, _ = uic.loadUiType(ui_file)


class DynamicLayersDialog(QDialog, FORM_CLASS):
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

        # Temporary disabled
        self.inProjectShortName.setVisible(False)
        self.label_5.setVisible(False)

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
