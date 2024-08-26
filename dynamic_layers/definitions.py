__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor


class CustomProperty:
    DynamicDatasourceActive = 'dynamicDatasourceActive'
    DynamicDatasourceContent = 'dynamicDatasourceContent'
    NameTemplate = 'nameTemplate'
    TitleTemplate = 'titleTemplate'
    AbstractTemplate = 'abstractTemplate'


class WmsProjectProperty:
    Abstract = 'WMSServiceAbstract'
    Title = 'WMSServiceTitle'
    ShortName = 'WMSRootName'
    Extent = 'WMSExtent'
    Capabilities = 'WMSServiceCapabilities'


class PluginProjectProperty:
    Title = 'ProjectTitle'
    Abstract = 'ProjectAbstract'
    ShortName = 'ProjectShortName'
    ExtentLayer = 'ExtentLayer'
    ExtentMargin = 'ExtentMargin'
    VariableSourceLayer = 'VariableSourceLayer'
    VariableSourceLayerExpression = 'VariableSourceLayerExpression'
    VariableList = 'VariableList'


class WidgetType:
    PlainText = 'PlainText'
    Text = 'Text'
    List = 'List'
    SpinBox = 'SpinBox'


class LayerPropertiesXml:
    DynamicDatasourceContent = 'dynamicDatasourceContent'
    NameTemplate = 'nameTemplate'
    TitleTemplate = 'titleTemplate'
    AbstractTemplate = 'abstractTemplate'


PLUGIN_SCOPE = 'PluginDynamicLayers'
PLUGIN_SCOPE_KEY = f'/{PLUGIN_SCOPE}'
PLUGIN_MESSAGE = 'DynamicLayers'


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
