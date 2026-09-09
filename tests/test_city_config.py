import os
import unittest
from unittest.mock import patch

import already_sent
import main


class ConfigPathTest(unittest.TestCase):
    def test_default_is_praha(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(main.config_path().endswith("praha.yaml"))
            self.assertEqual(main.city_label(), "Praha")

    def test_env_overrides_city_and_path(self) -> None:
        env = {"CONFIG_PATH": "config/kolin.yaml", "CITY": "Kolín"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(main.config_path(), "config/kolin.yaml")
            self.assertEqual(main.city_label(), "Kolín")

    def test_empty_kolin_config_refuses_to_send(self) -> None:
        env = {"CONFIG_PATH": "config/kolin.yaml", "CITY": "Kolín"}
        with patch.dict(os.environ, env, clear=True), patch("sys.argv", ["main.py"]):
            with self.assertRaises(SystemExit) as caught:
                main.main()
            self.assertEqual(caught.exception.code, 1)


class WorkflowFileTest(unittest.TestCase):
    def test_defaults_to_praha_workflow(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(already_sent.workflow_file(), "daily-menu.yml")

    def test_kolin_uses_its_own_workflow(self) -> None:
        with patch.dict(os.environ, {"WORKFLOW_FILE": "daily-menu-kolin.yml"}, clear=True):
            self.assertEqual(already_sent.workflow_file(), "daily-menu-kolin.yml")


if __name__ == "__main__":
    unittest.main()
