__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from typing import Annotated

from qgis.core import (
    Qgis,
    QgsFeature,
    QgsProcessingFeedback,
    QgsProject,
    QgsReferencedRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import NULL
from qgis.utils import iface

from dynamic_layers.core.layer_datasource_modifier import (
    LayerDataSourceModifier,
)
from dynamic_layers.definitions import (
    PLUGIN_SCOPE,
    CustomProperty,
    PluginProjectProperty,
    WmsProjectProperty,
)
from dynamic_layers.tools import log_message, string_substitution, tr


class DynamicLayersEngine:

    def __init__(self, feedback: QgsProcessingFeedback = None):
        """ Dynamic Layers Engine constructor. """
        self.dynamic_layers: dict = {}
        self.variables: dict = {}
        self.iface = iface
        self.feedback = feedback

        # For expressions
        self.project = None
        self.layer = None
        self.feature = None

    def set_layer_and_feature(self, layer: QgsVectorLayer, feature: QgsFeature):
        """ Set a feature for the dictionary. """
        self.layer = layer
        self.feature = feature

    def discover_dynamic_layers_from_project(self, project: QgsProject):
        """ Check all maplayers in the given project which are dynamic. """
        self.project = project
        self.dynamic_layers = {
            lid: layer for lid, layer in project.mapLayers().items() if
            layer.customProperty(CustomProperty.DynamicDatasourceActive) and layer.customProperty(
                CustomProperty.DynamicDatasourceContent)
        }

    def update_dynamic_layers_datasource(self):
        """
        For each layers with "active" status,
        Change the datasource by using the dynamicDatasourceContent
        And the given search&replace dictionary
        """
        for layer in self.dynamic_layers.values():
            a = LayerDataSourceModifier(layer, self.project, self.layer, self.feature, self.feedback)
            a.compute_new_uri(self.variables)

            if not self.iface:
                continue

            if layer.renderer() and layer.renderer().type() == 'graduatedSymbol':
                layer.triggerRepaint()

            layer.updateExtents(True)

        if not self.iface:
            return

        # self.iface.actionDraw().trigger()
        # self.iface.mapCanvas().refresh()

    def update_dynamic_project_properties(self):
        """
        Set some project properties : title, short name, abstract
        based on the templates stored in the project file in <PluginDynamicLayers>
        and by using the search and replace dictionary
        """
        # Make sure WMS Service is active
        if not self.project.readEntry(WmsProjectProperty.Capabilities, "/")[1]:
            self.project.writeEntry(WmsProjectProperty.Capabilities, "/", True)

        # Title
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Title)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.Title, val[0])

        # Shortname
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.ShortName)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.ShortName, val[0])

        # Abstract
        val = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.Abstract)
        if val[1] and val[0]:
            self.set_project_property(WmsProjectProperty.Abstract, val[0])

    def set_project_property(self, project_property: Annotated[str, WmsProjectProperty], val: str):
        """
        Set a project property
        And replace variable if found in the properties
        """
        log_message(tr("Compute new project property for {}").format(project_property), Qgis.Info, self.feedback)
        # Replace variable in given val via dictionary
        val = string_substitution(
            input_string=val,
            variables=self.variables,
            project=self.project,
            layer=self.layer,
            feature=self.feature,
        )
        if val is None or val == NULL:
            log_message(
                f'The expression evaluation "{val}" for the project property "{project_property}" was None/NULL, '
                f'it has been set to an empty string.',
                Qgis.Warning,
                self.feedback,
            )
            val = ""
        self.project.writeEntry(project_property, '', val)

    def force_refresh_all_layer_extents(self):
        for layer in self.project.mapLayers().values():
            if hasattr(layer, 'updateExtents'):
                layer.updateExtents(True)

    def update_project_extent(self):
        """ Update the project extent. """
        log_message(tr("Update project extent"), Qgis.Info, self.feedback)

        extent_layer = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.ExtentLayer)
        if extent_layer:
            extent_layer = extent_layer[0]
        extent_layer = self.project.mapLayer(extent_layer)

        extent_margin = self.project.readEntry(PLUGIN_SCOPE, PluginProjectProperty.ExtentMargin)
        if extent_margin and extent_margin[0]:
            extent_margin = int(extent_margin[0])

        p_extent = None
        if extent_layer:
            extent_layer.updateExtents(True)
            p_extent = extent_layer.extent()
            log_message(tr("Extent from layer : {}").format(extent_layer.name()), Qgis.Info, self.feedback)

        if p_extent and p_extent.width() <= 0 and self.iface:
            log_message(tr("Extent from iface"), Qgis.Info, self.feedback)
            p_extent = self.iface.mapCanvas().extent()

        if not p_extent:
            return

        if extent_margin:
            margin_x = p_extent.width() * extent_margin / 100
            margin_y = p_extent.height() * extent_margin / 100
            margin = max(margin_x, margin_y)
            p_extent = p_extent.buffered(margin)
            # TODO add unit
            log_message(
                tr("with a margin of {}, unit {}").format(margin, extent_layer.crs().mapUnits()),
                Qgis.Info,
                self.feedback,
            )

        # Modify WMS extent
        p_wms_extent = [p_extent.xMinimum(), p_extent.yMinimum(), p_extent.xMaximum(), p_extent.yMaximum()]
        p_wms_extent = [str(i) for i in p_wms_extent]
        self.project.writeEntry(WmsProjectProperty.Extent, '', p_wms_extent)
        log_message(tr("Writing the new extent to {}").format(WmsProjectProperty.Extent), Qgis.Info, self.feedback)

        if extent_layer:
            georef_rectangle = QgsReferencedRectangle(p_extent, extent_layer.crs())
        else:
            georef_rectangle = QgsReferencedRectangle(p_extent, iface.mapCanvas().mapSettings().destinationCrs())
        self.project.viewSettings().setDefaultViewExtent(georef_rectangle)

        # Zoom canvas to extent
        if self.iface:
            log_message(tr("Refresh map canvas"), Qgis.Info, self.feedback)
            self.iface.mapCanvas().setExtent(p_extent)
            self.iface.mapCanvas().refresh()
