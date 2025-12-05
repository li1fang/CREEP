import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List

from jsonschema import Draft7Validator, FormatChecker


@dataclass
class AssetEventValidationError(Exception):
    """Structured validation error carrying an observable error code."""

    error_code: str
    message: str
    path: List[str]

    def __str__(self) -> str:  # pragma: no cover - dataclass adds repr
        return self.message


class AssetEventValidator:
    """Validates AssetEvent payloads against the canonical JSON Schema."""

    def __init__(self, schema_path: Path | str | None = None) -> None:
        base_path = Path(schema_path) if schema_path else Path(__file__).resolve().parents[2]
        self.schema_path = base_path / "schemas" / "v1.0" / "AssetEvent.json"
        with self.schema_path.open("r", encoding="utf-8") as f:
            self.schema = json.load(f)

        self.format_checker = FormatChecker()

        @self.format_checker.checks("date-time")
        def _validate_datetime(value: str) -> bool:  # noqa: ANN001 - signature required by decorator
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
            except ValueError:
                return False

        self.validator = Draft7Validator(
            self.schema, format_checker=self.format_checker
        )

    def validate(self, payload: dict[str, Any]) -> None:
        errors = sorted(self.validator.iter_errors(payload), key=lambda e: e.path)
        if errors:
            first = errors[0]
            path = self._stringify_path(first.path)
            if first.validator == "required" and first.message.startswith("'"):
                path = [first.message.split("'", 2)[1]]
            raise AssetEventValidationError(
                error_code=self._map_error(first),
                message=first.message,
                path=path,
            )

    @staticmethod
    def _stringify_path(path: Iterable[Any]) -> List[str]:
        return [str(part) for part in path]

    @staticmethod
    def _map_error(error: Any) -> str:
        """Map jsonschema validation errors to observable error codes."""

        if error.validator == "required":
            return "E_SCHEMA_REQUIRED"
        if error.validator == "additionalProperties":
            return "E_SCHEMA_ADDITIONAL_PROPERTY"
        if error.validator == "format":
            return "E_SCHEMA_FORMAT"
        if error.validator == "type":
            return "E_SCHEMA_TYPE"
        if error.validator in {"minimum", "maximum"}:
            return "E_SCHEMA_RANGE"
        return "E_SCHEMA_INVALID"


class AssetEventService:
    """Service layer for ingesting AssetEvent payloads.

    The ingest endpoint should surface validation errors with standardized
    error codes to assist observability and client-side retries.
    """

    def __init__(self, validator: AssetEventValidator | None = None) -> None:
        self.validator = validator or AssetEventValidator()

    def ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            self.validator.validate(payload)
        except AssetEventValidationError as exc:
            error_path = ".".join(exc.path) if exc.path else "<root>"
            error_message = (
                f"{error_path}: {exc.message}" if error_path else exc.message
            )
            return {
                "ok": False,
                "error_code": exc.error_code,
                "error_message": error_message,
                "error_path": error_path,
            }

        return {"ok": True, "status": "accepted"}
