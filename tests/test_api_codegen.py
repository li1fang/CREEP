import tempfile
import unittest
from pathlib import Path

from src.tools import api_codegen


class ApiCodegenProtoTagTests(unittest.TestCase):
    def test_proto_tags_stable_when_schema_reorders_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = Path(tmpdir) / "asset_event.tags.json"
            lockfile.write_text('{"event_id": 1, "tenant_id": 2}\n', encoding="utf-8")

            original_lockfile = api_codegen.TAGS_LOCKFILE
            api_codegen.TAGS_LOCKFILE = lockfile
            try:
                schema = {
                    "properties": {
                        "tenant_id": {"type": "string"},
                        "event_id": {"type": "string"},
                        "new_field": {"type": "string"},
                    }
                }

                proto, tags = api_codegen.build_proto(schema, lockfile=lockfile)

                self.assertIn("string event_id = 1;", proto)
                self.assertIn("string tenant_id = 2;", proto)
                self.assertIn("string new_field = 3;", proto)
                self.assertEqual({"event_id": 1, "tenant_id": 2, "new_field": 3}, tags)
            finally:
                api_codegen.TAGS_LOCKFILE = original_lockfile

    def test_removed_fields_remain_reserved_in_lockfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = Path(tmpdir) / "asset_event.tags.json"
            lockfile.write_text('{"field_a": 1, "field_b": 2}\n', encoding="utf-8")

            original_lockfile = api_codegen.TAGS_LOCKFILE
            api_codegen.TAGS_LOCKFILE = lockfile
            try:
                schema = {"properties": {"field_a": {"type": "string"}, "field_c": {"type": "string"}}}

                proto, tags = api_codegen.build_proto(schema, lockfile=lockfile)

                self.assertIn("string field_a = 1;", proto)
                self.assertIn("string field_c = 3;", proto)
                self.assertNotIn("field_b", proto)
                self.assertEqual({"field_a": 1, "field_b": 2, "field_c": 3}, tags)
            finally:
                api_codegen.TAGS_LOCKFILE = original_lockfile


if __name__ == "__main__":
    unittest.main()
