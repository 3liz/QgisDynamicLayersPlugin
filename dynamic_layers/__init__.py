__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DynamicLayers class from file DynamicLayers.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .dynamic_layers import DynamicLayers
    return DynamicLayers(iface)
