{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "$id": "schema://creep/AssetGraph.v1.0",
  "title": "AssetGraph",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "edge_id": {
      "type": "string",
      "format": "uuid"
    },
    "tenant_id": {
      "type": "string",
      "minLength": 1
    },
    "project_id": {
      "type": "string"
    },
    "env": {
      "type": "string"
    },
    "from_asset_id": {
      "type": "string",
      "format": "uuid"
    },
    "to_asset_id": {
      "type": "string",
      "format": "uuid"
    },
    "edge_type": {
      "type": "string",
      "minLength": 1
    },
    "role": {
      "type": "string"
    },
    "graph_scope": {
      "type": "string"
    },
    "quantity": {
      "type": "number",
      "minimum": 0
    },
    "unit": {
      "type": "string"
    },
    "binding_type": {
      "type": "string",
      "enum": [
        "HARD",
        "SOFT",
        "EPHEMERAL"
      ]
    },
    "binding_strength": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "valid_from": {
      "type": "string",
      "format": "date-time"
    },
    "valid_until": {
      "type": "string",
      "format": "date-time"
    },
    "order_index": {
      "type": "integer",
      "minimum": 0
    },
    "tags": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "meta": {
      "type": "object"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    },
    "edge_version": {
      "type": "integer",
      "minimum": 1
    }
  },
  "required": [
    "edge_id",
    "tenant_id",
    "env",
    "from_asset_id",
    "to_asset_id",
    "edge_type",
    "created_at",
    "updated_at",
    "edge_version"
  ]
}
