import unittest
import uuid
from datetime import datetime, timezone

from src.tools.asset_event_validator import (
    AssetEventService,
    AssetEventValidationError,
    AssetEventValidator,
)


class AssetEventValidatorTests(unittest.TestCase):
    def build_valid_event(self):
        now = datetime.now(timezone.utc).isoformat()
        return {
            "event_id": str(uuid.uuid4()),
            "tenant_id": "tenant_x",
            "asset_id": str(uuid.uuid4()),
            "event_type": "TASK_SUCCESS",
            "occurred_at": now,
            "recorded_at": now,
            "version": 1,
        }

    def test_validator_accepts_valid_payload(self):
        validator = AssetEventValidator()
        validator.validate(self.build_valid_event())

    def test_validator_rejects_missing_required_field(self):
        validator = AssetEventValidator()
        event = self.build_valid_event()
        del event["event_id"]

        with self.assertRaises(AssetEventValidationError) as ctx:
            validator.validate(event)

        self.assertEqual(ctx.exception.error_code, "E_SCHEMA_REQUIRED")
        self.assertIn("event_id", ctx.exception.message)
        self.assertEqual(ctx.exception.path, ["event_id"])

    def test_validator_rejects_additional_property(self):
        validator = AssetEventValidator()
        event = self.build_valid_event()
        event["unexpected"] = "nope"

        with self.assertRaises(AssetEventValidationError) as ctx:
            validator.validate(event)

        self.assertEqual(ctx.exception.error_code, "E_SCHEMA_ADDITIONAL_PROPERTY")
        self.assertIn("unexpected", ctx.exception.message)

    def test_service_surfaces_error_codes(self):
        service = AssetEventService()
        event = self.build_valid_event()
        event["occurred_at"] = "not-a-datetime"

        result = service.ingest(event)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "E_SCHEMA_FORMAT")
        self.assertIn("occurred_at", result["error_message"])
        self.assertEqual(result["error_path"], "occurred_at")


if __name__ == "__main__":
    unittest.main()
