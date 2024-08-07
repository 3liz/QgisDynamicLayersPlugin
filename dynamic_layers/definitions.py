__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor


class CustomProperty:
    DynamicDatasourceActive = 'dynamicDatasourceActive'
    DynamicDatasourceContent = 'dynamicDatasourceContent'


class ProjectProperty:
    Abstract = 'WMSServiceAbstract'
    Title = 'WMSServiceTitle'
    ShortName = 'WMSRootName'
    Extent = 'WMSExtent'


PLUGIN_SCOPE = 'PluginDynamicLayers'
PLUGIN_SCOPE_KEY = f'/{PLUGIN_SCOPE}'


# noinspection PyUnresolvedReferences
class QtVar:
    Green = QColor(175, 208, 126)
    # All these variables are unknown PyQt
    Transparent = Qt.transparent
    ItemIsSelectable = Qt.ItemIsSelectable
    ItemIsEditable = Qt.ItemIsEditable
    ItemIsEnabled = Qt.ItemIsEnabled
    EditRole = Qt.EditRole
    WaitCursor = Qt.WaitCursor
    UserRole = Qt.UserRole
