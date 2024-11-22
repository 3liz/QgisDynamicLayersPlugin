__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from qgis.core import Qgis, QgsApplication, QgsMessageLog
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QCoreApplication, QSettings, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu

from dynamic_layers.definitions import PLUGIN_MESSAGE
from dynamic_layers.dynamic_layers_dialog import DynamicLayersDialog
from dynamic_layers.generate_projects import GenerateProjectsDialog
from dynamic_layers.tools import open_help, plugin_path, resources_path, tr


class DynamicLayers:
    """QGIS Plugin Implementation."""

    def __init__(self, iface: QgisInterface):
        """Constructor."""
        self.iface = iface
        # self.provider = None

        self.help_action_about_menu = None
        self.menu = None
        self.main_dialog_action = None
        self.generate_projects_action = None

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

    # noinspection PyPep8Naming
    # def initProcessing(self):
    #     """ Init processing provider. """
    #     self.provider = Provider()
    #     # noinspection PyArgumentList
    #     QgsApplication.processingRegistry().addProvider(self.provider)

    # noinspection PyPep8Naming
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # noinspection PyArgumentList
        main_icon = QIcon(str(resources_path('icons', 'icon.png')))
        self.menu = QMenu("Dynamic Layers")
        self.menu.setIcon(main_icon)

        self.main_dialog_action = QAction(main_icon, tr("Setup the project"), self.iface.mainWindow())
        # noinspection PyUnresolvedReferences
        self.main_dialog_action.triggered.connect(self.open_single_project_dialog)
        self.menu.addAction(self.main_dialog_action)

        # noinspection PyArgumentList
        self.generate_projects_action = QAction(
            QIcon(QgsApplication.iconPath("processingAlgorithm.svg")),
            tr("Generate projects"),
            self.iface.mainWindow()
        )
        # noinspection PyUnresolvedReferences
        self.generate_projects_action.triggered.connect(self.open_generate_projects_dialog)
        self.menu.addAction(self.generate_projects_action)

        self.iface.pluginMenu().addMenu(self.menu)

        # self.initProcessing()

        # Open the online help
        self.help_action_about_menu = QAction(main_icon, tr('Project generator'), self.iface.mainWindow())
        self.iface.pluginHelpMenu().addAction(self.help_action_about_menu)
        # noinspection PyUnresolvedReferences
        self.help_action_about_menu.triggered.connect(open_help)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        # if self.provider:
        #     # noinspection PyArgumentList
        #     QgsApplication.processingRegistry().removeProvider(self.provider)

        if self.generate_projects_action:
            self.iface.removePluginMenu("Dynamic Layers", self.generate_projects_action)
            del self.generate_projects_action

        if self.main_dialog_action:
            self.iface.removePluginMenu("Dynamic Layers", self.main_dialog_action)
            del self.main_dialog_action

        if self.help_action_about_menu:
            self.iface.pluginHelpMenu().removeAction(self.help_action_about_menu)
            del self.help_action_about_menu

    @staticmethod
    def open_generate_projects_dialog():
        """ Open the generate projects dialog. """
        dialog = GenerateProjectsDialog()
        dialog.exec()
        del dialog

    @staticmethod
    def open_single_project_dialog():
        """ Open the single project dialog. """
        dialog = DynamicLayersDialog()
        dialog.populate_layer_table()
        dialog.populate_variable_table()
        dialog.populate_project_properties()
        dialog.exec()
        del dialog
