__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path
from typing import List

from qgis.core import (
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextScope,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsProcessingException,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication

""" Tools to work with resources files. """


def string_substitution(
        input_string: str,
        variables: dict,
        project: QgsProject = None,
        layer: QgsVectorLayer = None,
        feature: QgsFeature = None,
        is_template: bool = False,
) -> str:
    """ String substitution. """
    scope = QgsExpressionContextScope()
    for key, value in variables.items():
        scope.addVariable(QgsExpressionContextScope.StaticVariable(key, value, True, True))

    context = QgsExpressionContext()
    context.appendScope(QgsExpressionContextUtils.globalScope())

    if project:
        context.appendScope(QgsExpressionContextUtils.projectScope(project))

    if layer:
        context.appendScope(QgsExpressionContextUtils.layerScope(layer))

    if feature:
        context.setFeature(feature)

    context.appendScope(scope)

    if is_template:
        output = QgsExpression.replaceExpressionText(input_string, context)
        return output

    expression = QgsExpression(input_string)
    if expression.hasEvalError() or expression.hasParserError():
        raise QgsProcessingException(f"Invalid QGIS expression : {input_string}")

    output = expression.evaluate(context)
    return output


def plugin_path(*args) -> Path:
    """Return the path to the plugin root folder."""
    path = Path(__file__).resolve().parent
    for item in args:
        path = path.joinpath(item)

    return path


def resources_path(*args) -> Path:
    """Return the path to the plugin resources folder."""
    return plugin_path("resources", *args)


def side_car_files(file_path: Path) -> List[Path]:
    """ Return a list of all side-car files, having the extension included. """
    results = []
    for iter_file in file_path.parent.iterdir():
        if iter_file.name.startswith(file_path.name) and iter_file != file_path:
            results.append(iter_file)

    results.sort()
    return results


def tr(message: str) -> str:
    return QCoreApplication.translate('DynamicLayers', message)
