__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox
from qgis.core import QgsApplication
from qgis.gui import QgsExpressionBuilderDialog


folder = Path(__file__).resolve().parent
ui_file = folder / 'dynamic_layers_dialog_base.ui'
FORM_CLASS, _ = uic.loadUiType(ui_file)


class DynamicLayersDialog(QDialog, FORM_CLASS):
    def __init__(self, parent: QDialog = None):
        """Constructor."""
        super().__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.button_box.button(QDialogButtonBox.Close).clicked.connect(self.close)

        self.btAddVariable.setText("")
        self.btAddVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyAdd.svg')))
        self.btAddVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))
        self.btRemoveVariable.setText("")
        self.btRemoveVariable.setToolTip("")

        self.btRemoveVariable.setIcon(QIcon(QgsApplication.iconPath('symbologyRemove.svg')))

        self.btClearLog.setIcon(QIcon(QgsApplication.iconPath('iconClearConsole.svg')))

        self.bt_open_expression.setText("")
        self.bt_open_expression.setToolTip("")
        self.bt_open_expression.setIcon(QIcon(QgsApplication.iconPath('mIconExpression.svg')))
        self.bt_open_expression.clicked.connect(self.open_expression_builder)

        self.inProjectShortName.setVisible(False)
        self.label_5.setVisible(False)

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
