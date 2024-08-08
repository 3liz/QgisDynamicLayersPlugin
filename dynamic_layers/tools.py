__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

from pathlib import Path
from string import Template
from typing import List

from qgis.PyQt.QtCore import QCoreApplication

""" Tools to work with resources files. """


def string_substitution(string: str, dictionary: dict) -> str:
    """ String substitution. """
    return Template(string).safe_substitute(dictionary)


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
