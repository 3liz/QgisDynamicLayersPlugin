__copyright__ = 'Copyright 2024, 3Liz'
__license__ = 'GPL version 3'
__email__ = 'info@3liz.org'

import tempfile
import unittest

from pathlib import Path

from dynamic_layers.tools import side_car_files


class TestTools(unittest.TestCase):

    def test_sidecar_files(self):
        """ Test to detect side-car files. """
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            test = Path(tmp_dir_name) / "project.qgs"
            test.touch()

            side_1 = Path(tmp_dir_name) / "project.qgs.png"
            side_1.touch()

            side_2 = Path(tmp_dir_name) / "project.qgs.cfg"
            side_2.touch()

            random_file = Path(tmp_dir_name) / "hello.qgs.png"
            random_file.touch()

            expected = [side_1, side_2]
            expected.sort()
            self.assertListEqual(expected, side_car_files(test))
