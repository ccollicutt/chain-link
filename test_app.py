import unittest
from unittest.mock import patch, MagicMock
import json
from app import app, get_service_urls


class TestApp(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()

        self.mock_file = MagicMock()
        self.mock_file.path = "/etc/chain-link.conf.d/services.json"
        self.mock_file.read.return_value = json.dumps(
            ["service-a", "service-b", "service-c", "service-d"]
        )

        self.mock_open = patch("builtins.open", return_value=self.mock_file).start()

    def tearDown(self):
        self.mock_open.stop()

    def test_get_service_urls(self):
        self.assertEqual(
            get_service_urls(), ["service-a", "service-b", "service-c", "service-d"]
        )


if __name__ == "__main__":
    unittest.main()
