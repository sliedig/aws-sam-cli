"""Custom C# code generation from EventBridge JSON Schemas.

The EventBridge Schemas API does not support C# as a code binding language.
This module generates C# source files (AWSEvent.cs, detail POCO, Marshaller.cs)
from raw JSON Schema definitions fetched via DescribeSchema.
"""

import json
import logging
import os
import re
import zipfile

LOG = logging.getLogger(__name__)

# JSON Schema type -> C# type mapping
JSON_SCHEMA_TO_CSHARP_TYPE = {
    "string": "string",
    "integer": "int",
    "number": "double",
    "boolean": "bool",
}


def generate_dotnet_code_binding(schema_content, schema_name, download_location):
    """
    Generate C# code bindings from an EventBridge JSON Schema and write them
    as a ZIP to the download location (compatible with do_extract_and_merge_schemas_code).

    Parameters
    ----------
    schema_content : str
        Raw JSON Schema content from DescribeSchema
    schema_name : str
        Full schema name (e.g., "aws.ec2@EC2InstanceStateChangeNotification")
    download_location : file-like
        Writable file object where the ZIP archive will be written
    """
    content = json.loads(schema_content) if isinstance(schema_content, str) else schema_content
    schemas = content.get("components", {}).get("schemas", {})

    # Identify the root schema class name and detail properties
    schema_root_name, detail_schema = _resolve_detail_schema(schemas)
    namespace, namespace_dir = _derive_namespace(schema_name)

    # Generate C# source files
    aws_event_cs = _generate_aws_event(namespace)
    detail_cs = _generate_detail_class(namespace, schema_root_name, detail_schema, schemas)
    marshaller_cs = _generate_marshaller(namespace)

    # Write all files as a ZIP archive
    _write_zip(download_location, namespace_dir, schema_root_name, aws_event_cs, detail_cs, marshaller_cs)


def _resolve_detail_schema(schemas):
    """
    Find the root detail schema from the components.schemas section.
    If an AWSEvent wrapper exists, follow its detail $ref to find the root.

    Returns
    -------
    tuple of (schema_root_name: str, detail_properties: dict)
    """
    aws_event = schemas.get("AWSEvent")
    if aws_event is not None:
        detail_ref = aws_event.get("properties", {}).get("detail", {}).get("$ref", "")
        ref_name = detail_ref.split("/")[-1] if detail_ref else ""
        if ref_name and ref_name in schemas:
            return ref_name, schemas[ref_name]

    # No AWSEvent wrapper — use the first non-AWSEvent schema
    for name, schema_def in schemas.items():
        if name != "AWSEvent":
            return name, schema_def

    return "UnknownEvent", {}


def _derive_namespace(schema_name):
    """
    Derive the C# namespace and directory from the schema name.

    For schema name "aws.ec2@EC2InstanceStateChangeNotification":
    - Package hierarchy segments: ["aws", "ec2"]
    - Namespace: "Model.Aws.Ec2"
    - Directory: "Model/Aws/Ec2"

    Returns
    -------
    tuple of (namespace: str, directory_path: str)
    """
    # Sanitize: replace @ with . for splitting
    name = schema_name.replace("@", ".")

    # Split into segments, drop the last segment (that's the class name)
    parts = name.split(".")
    if len(parts) > 1:
        namespace_parts = parts[:-1]
    else:
        namespace_parts = parts

    pascal_parts = [_to_pascal_case(p) for p in namespace_parts]
    namespace = "Model." + ".".join(pascal_parts)
    directory = os.path.join("Model", *pascal_parts)
    return namespace, directory


def _to_pascal_case(s):
    """Convert a string to PascalCase."""
    # Split on non-alphanumeric characters
    words = re.split(r"[^a-zA-Z0-9]", s)
    return "".join(word.capitalize() for word in words if word)


def _map_csharp_type(json_type, items=None, property_name=None, schemas=None):
    """
    Map a JSON Schema type to a C# type.

    Parameters
    ----------
    json_type : str
        The JSON Schema type string
    items : dict, optional
        For array types, the items schema
    property_name : str, optional
        Property name for generating nested class names
    schemas : dict, optional
        All schemas for resolving $ref

    Returns
    -------
    str
        The C# type string
    """
    if json_type in JSON_SCHEMA_TO_CSHARP_TYPE:
        return JSON_SCHEMA_TO_CSHARP_TYPE[json_type]

    if json_type == "array":
        if items:
            if "$ref" in items:
                ref_name = items["$ref"].split("/")[-1]
                return f"List<{ref_name}>"
            inner_type = _map_csharp_type(items.get("type", "string"), items=items.get("items"))
            return f"List<{inner_type}>"
        return "List<object>"

    if json_type == "object":
        if property_name:
            return _to_pascal_case(property_name)
        return "object"

    return "object"


def _generate_property_line(prop_name, prop_schema, schemas=None):
    """
    Generate C# property declaration with optional JsonPropertyName attribute.

    Returns
    -------
    str
        Lines of C# code for the property
    """
    json_type = prop_schema.get("type", "object")
    items = prop_schema.get("items")

    if "$ref" in prop_schema:
        ref_name = prop_schema["$ref"].split("/")[-1]
        csharp_type = ref_name
    else:
        csharp_type = _map_csharp_type(json_type, items=items, property_name=prop_name, schemas=schemas)

    pascal_name = _to_pascal_case(prop_name)
    lines = []

    # Add JsonPropertyName attribute if the JSON name differs from PascalCase
    if prop_name != pascal_name:
        lines.append(f'        [JsonPropertyName("{prop_name}")]')

    lines.append(f"        public {csharp_type} {pascal_name} {{ get; set; }}")
    return "\n".join(lines)


def _generate_nested_classes(detail_schema, schemas):
    """Generate nested class definitions for object-type properties."""
    classes = []
    properties = detail_schema.get("properties", {})

    for prop_name, prop_schema in properties.items():
        json_type = prop_schema.get("type", "")
        if json_type == "object" and "properties" in prop_schema:
            class_name = _to_pascal_case(prop_name)
            nested_props = []
            for nested_name, nested_schema in prop_schema.get("properties", {}).items():
                nested_props.append(_generate_property_line(nested_name, nested_schema, schemas))

            cls = f"    public class {class_name}\n    {{\n"
            cls += "\n\n".join(nested_props)
            cls += "\n    }"
            classes.append(cls)

    return classes


def _generate_aws_event(namespace):
    """Generate the AWSEvent<T> generic envelope class."""
    return f"""using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace {namespace}
{{
    public class AWSEvent<T>
    {{
        [JsonPropertyName("detail")]
        public T Detail {{ get; set; }}

        [JsonPropertyName("detail-type")]
        public string DetailType {{ get; set; }}

        [JsonPropertyName("resources")]
        public List<string> Resources {{ get; set; }}

        [JsonPropertyName("id")]
        public string Id {{ get; set; }}

        [JsonPropertyName("source")]
        public string Source {{ get; set; }}

        [JsonPropertyName("time")]
        public DateTime Time {{ get; set; }}

        [JsonPropertyName("region")]
        public string Region {{ get; set; }}

        [JsonPropertyName("version")]
        public string Version {{ get; set; }}

        [JsonPropertyName("account")]
        public string Account {{ get; set; }}
    }}
}}
"""


def _generate_detail_class(namespace, class_name, detail_schema, schemas):
    """Generate the schema-specific detail POCO class."""
    properties = detail_schema.get("properties", {})
    prop_lines = []
    for prop_name, prop_schema in properties.items():
        prop_lines.append(_generate_property_line(prop_name, prop_schema, schemas))

    nested_classes = _generate_nested_classes(detail_schema, schemas)

    props_str = "\n\n".join(prop_lines)
    nested_str = "\n\n".join(nested_classes)

    body_parts = []
    if props_str:
        body_parts.append(props_str)
    if nested_str:
        body_parts.append(nested_str)

    body = "\n\n".join(body_parts)

    return f"""using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace {namespace}
{{
    public class {class_name}
    {{
{body}
    }}
}}
"""


def _generate_marshaller(namespace):
    """Generate the Marshaller static helper class."""
    return f"""using System.IO;
using System.Text.Json;

namespace {namespace}
{{
    public static class Marshaller
    {{
        public static AWSEvent<T> UnmarshalEvent<T>(Stream input)
        {{
            return JsonSerializer.Deserialize<AWSEvent<T>>(input);
        }}

        public static T Unmarshal<T>(Stream input)
        {{
            return JsonSerializer.Deserialize<T>(input);
        }}

        public static void Marshal<T>(Stream output, T value)
        {{
            JsonSerializer.Serialize(output, value);
        }}

        public static string Marshal<T>(T value)
        {{
            return JsonSerializer.Serialize(value);
        }}
    }}
}}
"""


def _write_zip(download_location, namespace_dir, schema_root_name, aws_event_cs, detail_cs, marshaller_cs):
    """Write the generated C# files as a ZIP archive."""
    with zipfile.ZipFile(download_location, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(os.path.join(namespace_dir, "AWSEvent.cs"), aws_event_cs)
        zf.writestr(os.path.join(namespace_dir, f"{schema_root_name}.cs"), detail_cs)
        zf.writestr(os.path.join(namespace_dir, "Marshaller.cs"), marshaller_cs)
