import unittest
from trading_platform.cli import validate_config


class ConfigurationTests(unittest.TestCase):
    def config(self):
        return {"schema_version": 1, "instance_id": "test", "strategy": "fixture@1",
                "mode": "paper", "universe": ["TEST"]}

    def test_valid_config_is_explicitly_non_executable(self):
        self.assertFalse(validate_config(self.config())["runtime_implemented"])

    def test_live_mode_rejected(self):
        data = self.config()
        data["mode"] = "live"
        with self.assertRaises(ValueError):
            validate_config(data)

    def test_invalid_shapes_rejected(self):
        for field, value in [("schema_version", True), ("universe", []),
                             ("universe", ["TEST", "TEST"]), ("strategy", "")]:
            with self.subTest(field=field, value=value):
                data = self.config()
                data[field] = value
                with self.assertRaises(ValueError):
                    validate_config(data)

    def test_unknown_fields_rejected(self):
        data = self.config()
        data["secret"] = "not-allowed"
        with self.assertRaises(ValueError):
            validate_config(data)


if __name__ == "__main__":
    unittest.main()
