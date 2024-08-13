__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import typing

from qgis.core import QgsMapLayer, QgsReadWriteContext
from qgis.PyQt.QtXml import QDomDocument

from dynamic_layers.definitions import CustomProperty
from dynamic_layers.tools import string_substitution


class LayerDataSourceModifier:

    # Content of the dynamic datasource
    dynamic_datasource_content = None

    # Datasource can be changed from dynamicDatasourceContent or not
    dynamic_datasource_active = False

    def __init__(self, layer: QgsMapLayer):
        """
        Initialize class instance
        """
        self.layer = layer
        self.dynamic_datasource_active = layer.customProperty(CustomProperty.DynamicDatasourceActive)
        self.dynamic_datasource_content = layer.customProperty(CustomProperty.DynamicDatasourceContent)

    def set_new_source_uri_from_dict(self, search_and_replace_dictionary: dict = None):
        """
        Get the dynamic datasource template,
        Replace variable with passed data,
        And set the layer datasource from this content if possible
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}

        # Set the new uri
        new_uri = string_substitution(
            self.dynamic_datasource_content, search_and_replace_dictionary)

        # Set the layer datasource
        self.set_data_source(new_uri)

        # Set other properties
        self.set_dynamic_layer_properties(search_and_replace_dictionary)

    def set_data_source(self, new_source_uri: str):
        """
        Method to apply a new datasource to a vector Layer
        """
        context = QgsReadWriteContext()
        new_ds, new_uri = self.split_source(new_source_uri)
        new_datasource_type = new_ds or self.layer.dataProvider().name()

        # read layer definition
        xml_document = QDomDocument("style")
        # XMLMapLayers = QDomElement()
        xml_map_layers = xml_document.createElement("maplayers")
        # XMLMapLayer = QDomElement()
        xml_map_layer = xml_document.createElement("maplayer")
        self.layer.writeLayerXml(xml_map_layer, xml_document, context)

        # apply layer definition
        xml_map_layer.firstChildElement("datasource").firstChild().setNodeValue(new_uri)
        xml_map_layer.firstChildElement("provider").firstChild().setNodeValue(new_datasource_type)
        xml_map_layers.appendChild(xml_map_layer)
        xml_document.appendChild(xml_map_layers)
        self.layer.readLayerXml(xml_map_layer, context)

        # Update layer extent
        self.layer.updateExtents()

        # Update graduated symbol renderer
        if self.layer.renderer() and self.layer.renderer().type() == 'graduatedSymbol':
            ranges = self.layer.renderer().ranges()
            if len(ranges) == 1:
                self.layer.renderer().updateClasses(self.layer, self.layer.renderer().mode(), len(ranges))

        # Reload layer
        self.layer.reload()

    @staticmethod
    def split_source(source: str) -> typing.Tuple[str, str]:
        """
        Split QGIS datasource into meaningful components
        """
        # TODO switch to QgsProviderRegistry.instance().decodeUri(layer.dataProvider().name(), layer.source())
        if "|" in source:
            datasource_type = source.split("|")[0]
            uri = source.split("|")[1].replace('\\', '/')
        else:
            datasource_type = None
            uri = source.replace('\\', '/')
        return datasource_type, uri

    def set_dynamic_layer_properties(self, search_and_replace_dictionary: dict = None):
        """
        Set layer title, abstract,
        and field aliases (for vector layers only)
        """
        if search_and_replace_dictionary is None:
            search_and_replace_dictionary = {}

        # Layer title
        # First check that we have a title
        source_title = self.layer.name().strip()
        title = self.layer.title().strip()
        if title != '':
            source_title = title

        source_title = f"'{source_title}'"

        title_template = self.layer.customProperty(CustomProperty.TitleTemplate)
        if title_template and title_template not in ("", "''"):
            source_title = title_template

        # Search and replace content
        self.layer.setTitle(
            string_substitution(
                source_title,
                search_and_replace_dictionary,
            ),
        )

        # Name
        source_name = self.layer.name().strip()
        source_name = f"'{source_name}'"
        name_template = self.layer.customProperty(CustomProperty.NameTemplate)
        if name_template and name_template not in ("", "''"):
            source_name = name_template

        # Search and replace content
        self.layer.setName(
            string_substitution(
                source_name,
                search_and_replace_dictionary,
            ),
        )

        # Abstract
        source_abstract = ''
        if self.layer.abstract().strip() != '':
            source_abstract = self.layer.abstract().strip()
        source_abstract = f"'{source_abstract}'"

        abstract_template = self.layer.customProperty(CustomProperty.AbstractTemplate)
        if abstract_template and abstract_template not in ("", "''"):
            source_abstract = abstract_template

        self.layer.setAbstract(
            string_substitution(
                source_abstract,
                search_and_replace_dictionary,
            ),
        )

        # Set fields aliases
        if self.layer.type() == QgsMapLayer.VectorLayer:
            for fid, field in enumerate(self.layer.fields()):
                alias = self.layer.attributeAlias(fid)
                if not alias:
                    continue

                new_alias = string_substitution(
                    alias,
                    search_and_replace_dictionary,
                )
                self.layer.setFieldAlias(fid, new_alias)
