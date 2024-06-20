__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import unittest

from qgis.core import QgsApplication


class BaseTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.qgs = QgsApplication([], False)
        cls.qgs.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.qgs.exitQgis()
