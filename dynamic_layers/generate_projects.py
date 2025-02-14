__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'


from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsMapLayerProxyModel,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProject,
)
from qgis.gui import QgsExpressionBuilderDialog, QgsFileWidget
from qgis.PyQt import uic
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QProgressBar,
)
from qgis.utils import OverrideCursor

from dynamic_layers.core.generate_projects import GenerateProjects
from dynamic_layers.definitions import QtVar
from dynamic_layers.tools import open_help, tr

folder = Path(__file__).resolve().parent
ui_file = folder / 'resources' / 'ui' / 'generate_projects.ui'
FORM_CLASS, _ = uic.loadUiType(ui_file)


class GenerateProjectsDialog(QDialog, FORM_CLASS):
    # noinspection PyArgumentList
    def __init__(self, parent: QDialog = None):
        """Constructor."""
        # noinspection PyArgumentList
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(tr("Generate many QGIS projects"))
        self.project = QgsProject.instance()

        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.generate_projects)
        self.button_box.button(QDialogButtonBox.StandardButton.Help).clicked.connect(open_help)
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.close)

        self.expression.setText("")
        self.expression.setToolTip(tr("Open the expression builder"))
        self.expression.setIcon(QIcon(QgsApplication.iconPath('mIconExpression.svg')))
        self.expression.clicked.connect(self.open_expression_builder)

        self.coverage.setFilters(QgsMapLayerProxyModel.Filter.VectorLayer)
        self.coverage.layerChanged.connect(self.layer_changed)

        self.copy_side_care_files.setChecked(True)

        self.destination.setStorageMode(QgsFileWidget.StorageMode.GetDirectory)
        self.field.setAllowEmptyFieldName(False)
        self.layer_changed()
        self.debug_limit.setValue(0)

        # DEBUG
        # self.file_name.setText('"schema" || \'/test_\' ||  "schema" || \'.qgs\'')
        # self.destination.setFilePath('/tmp/demo_cartophyl')
        # self.debug_limit.setValue(1)

    def layer_changed(self):
        self.field.setLayer(self.coverage.currentLayer())

    def open_expression_builder(self):
        """ Open the expression builder. """
        layer = self.coverage.currentLayer()
        if not layer:
            return
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())
        context.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
        context.appendScope(QgsExpressionContextUtils.layerScope(layer))

        dialog = QgsExpressionBuilderDialog(layer, context=context)
        dialog.setExpressionText(self.file_name.text())
        result = dialog.exec()

        if result != QDialog.DialogCode.Accepted:
            return

        content = dialog.expressionText()
        self.file_name.setText(content)

    def generate_projects(self):
        """The OK button to generate all projects. """
        layer = self.coverage.currentLayer()
        if not layer:
            return

        feedback = TextFeedBack(self.logs, self.progress)

        if self.project.isDirty():
            feedback.reportError(tr("You must save your project first."))

        self.button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        result = False
        with OverrideCursor(QtVar.WaitCursor):
            self.logs.clear()

            generator = GenerateProjects(
                self.project,
                layer,
                self.field.currentField(),
                self.file_name.text(),
                Path(self.destination.filePath()),
                self.copy_side_care_files.isChecked(),
                feedback,
                limit=self.debug_limit.value(),
            )

            try:
                result = generator.process()
            except QgsProcessingException as e:
                feedback.reportError(str(e))
            except Exception as e:
                feedback.reportError(str(e))

        if result:
            feedback.pushInfo(tr("End") + " 👍")
            feedback.pushInfo(tr("Dialog can be closed"))
            # In case of success, the button is not enabled again
        else:
            feedback.pushWarning(tr("End, but there was an error"))
            self.button_box.button(QDialogButtonBox.StandardButton.Apply).setEnabled(True)


class TextFeedBack(QgsProcessingFeedback):

    def __init__(self, widget: QPlainTextEdit, progress: QProgressBar):
        super().__init__()
        self.widget = widget
        self.progress = progress

    def setProgressText(self, text):
        pass

    def setProgress(self, i: int):
        self.progress.setValue(i)

    def pushInfo(self, text):
        self.widget.appendHtml(f"<p>{text}</p>")

    def pushCommandInfo(self, text):
        self.widget.appendHtml(f"<p style=\"color:grey\">{text}</p>")

    def pushDebugInfo(self, text):
        self.widget.appendHtml(f"<p style=\"color:grey\">{text}</p>")

    def pushConsoleInfo(self, text):
        self.widget.appendHtml(f"<p style=\"color:grey\">{text}</p>")

    def reportError(self, text, fatal_error=False):
        _ = fatal_error
        self.widget.appendHtml(f"<p style=\"color:red\">{text}</p>")
