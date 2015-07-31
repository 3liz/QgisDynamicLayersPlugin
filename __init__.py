# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DynamicLayers
                                 A QGIS plugin
 This plugin helps to change the datasource of chosen layers dynamically by searching and replacing user defined variables.
                             -------------------
        begin                : 2015-07-21
        copyright            : (C) 2015 by Michaël Douchin - 3liz
        email                : mdouchin@3liz.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DynamicLayers class from file DynamicLayers.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .dynamic_layers import DynamicLayers
    return DynamicLayers(iface)
