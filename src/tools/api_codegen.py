"""Generate OpenAPI and Proto specs from the AssetEvent schema."""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "v1.0" / "AssetEvent.json"
OUTPUT_OPENAPI = Path(__file__).resolve().parents[2] / "deploy" / "api" / "asset_event_ingest.openapi.json"
OUTPUT_PROTO = Path(__file__).resolve().parents[2] / "deploy" / "api" / "asset_event_ingest.proto"
TAGS_LOCKFILE = Path(__file__).resolve().parents[2] / "deploy" / "api" / "asset_event.tags.json"


def load_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_openapi(schema: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "AssetEvent Ingest API",
            "version": "1.0.0",
            "description": "Append-only ingest endpoint aligned with schemas/v1.0/AssetEvent.json",
        },
        "paths": {
            "/api/v1/asset-events": {
                "post": {
                    "summary": "Ingest an AssetEvent",
                    "operationId": "postAssetEvent",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AssetEvent"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Accepted",
                            "content": {
                                "application/json": {
                                    "example": {"ok": True, "status": "accepted"}
                                }
                            },
                        },
                        "400": {
                            "description": "Schema validation failed",
                            "content": {
                                "application/json": {
                                    "example": {
                                        "ok": False,
                                        "error_code": "E_SCHEMA_REQUIRED",
                                        "error_message": "event_id: 'event_id' is a required property",
                                        "error_path": "event_id",
                                    }
                                }
                            },
                        },
                    },
                }
            }
        },
        "components": {"schemas": {"AssetEvent": schema}},
    }


def map_type(property_def: Dict[str, Any]) -> str:
    type_name = property_def.get("type")
    if type_name == "integer":
        return "int64"
    if type_name == "boolean":
        return "bool"
    if type_name == "array":
        return f"repeated {map_type(property_def.get('items', {}))}"
    if type_name == "object":
        # We intentionally degrade arbitrary JSON objects to a JSON string in proto to avoid
        # pulling in google.protobuf.Struct. Callers must serialize/deserialize as needed.
        return "string"
    return "string"


def load_tag_registry(lockfile: Path | None = None) -> Dict[str, int]:
    """Load the persistent field -> tag registry.

    The lockfile never removes historical entries so that tags are permanently
    reserved even if a field is removed from the schema. This prevents tag reuse
    that would corrupt binary compatibility.
    """

    registry_path = lockfile or TAGS_LOCKFILE
    if not registry_path.exists():
        return {}

    with registry_path.open("r", encoding="utf-8") as f:
        return {k: int(v) for k, v in json.load(f).items()}


def assign_tags(schema: Dict[str, Any], existing_tags: Dict[str, int]) -> Dict[str, int]:
    tags = dict(existing_tags)
    max_tag = max(tags.values(), default=0)

    for name in sorted(schema.get("properties", {}).keys()):
        if name in tags:
            continue
        max_tag += 1
        tags[name] = max_tag

    return tags


def build_proto(schema: Dict[str, Any], lockfile: Path | None = None) -> Tuple[str, Dict[str, int]]:
    tags = assign_tags(schema, load_tag_registry(lockfile))
    numbered_fields = []

    for name, prop in schema.get("properties", {}).items():
        numbered_fields.append((tags[name], name, prop))

    numbered_fields.sort(key=lambda item: item[0])

    lines = [
        "syntax = \"proto3\";",
        "package creep.asset.v1;",
        "",
        "// Generated from schemas/v1.0/AssetEvent.json, do not edit by hand.",
        "message AssetEvent {",
    ]

    for tag, name, prop in numbered_fields:
        lines.append(f"  {map_type(prop)} {name} = {tag};")

    lines.extend(
        [
            "}",
            "",
            "message AssetEventIngestResponse {",
            "  bool ok = 1;",
            "  string status = 2;",
            "  string error_code = 3;",
            "  string error_message = 4;",
            "  string error_path = 5;",
            "}",
            "",
            "service AssetEventIngestService {",
            "  rpc PostAssetEvent(AssetEvent) returns (AssetEventIngestResponse);",
            "}",
            "",
        ]
    )

    return "\n".join(lines), tags


def write_openapi(openapi: Dict[str, Any]) -> None:
    OUTPUT_OPENAPI.write_text(json.dumps(openapi, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_proto(proto: str) -> None:
    OUTPUT_PROTO.write_text(proto + "\n", encoding="utf-8")


def check_mode() -> int:
    schema = load_schema()
    openapi = build_openapi(schema)
    proto, tags = build_proto(schema)

    desired_openapi = json.dumps(openapi, indent=2, sort_keys=True) + "\n"
    desired_proto = proto + "\n"
    desired_tags = json.dumps(tags, indent=2, sort_keys=True) + "\n"

    current_openapi = OUTPUT_OPENAPI.read_text(encoding="utf-8") if OUTPUT_OPENAPI.exists() else ""
    current_proto = OUTPUT_PROTO.read_text(encoding="utf-8") if OUTPUT_PROTO.exists() else ""
    current_tags = TAGS_LOCKFILE.read_text(encoding="utf-8") if TAGS_LOCKFILE.exists() else ""

    mismatches: list[str] = []
    if current_openapi != desired_openapi:
        mismatches.append(str(OUTPUT_OPENAPI))
    if current_proto != desired_proto:
        mismatches.append(str(OUTPUT_PROTO))
    if current_tags != desired_tags:
        mismatches.append(str(TAGS_LOCKFILE))

    if mismatches:
        print("Outdated artifacts:")
        for file in mismatches:
            print(f" - {file}")
        print("Run `python src/tools/api_codegen.py --write` to update them.")
        return 1
    return 0


def write_mode() -> None:
    schema = load_schema()
    write_openapi(build_openapi(schema))
    proto, tags = build_proto(schema)
    write_proto(proto)
    TAGS_LOCKFILE.write_text(json.dumps(tags, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate API specs for AssetEvent ingest")
    parser.add_argument("--check", action="store_true", help="Only check drift without writing files")
    parser.add_argument("--write", action="store_true", help="Write artifacts to disk")
    args = parser.parse_args()

    if args.check:
        return check_mode()
    if args.write:
        write_mode()
        return 0

    parser.error("No action specified; use --check or --write")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
