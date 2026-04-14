import io
import json
import os
import zipfile
from unittest import TestCase

from samcli.lib.schemas.cli_dotnet_codegen import (
    _derive_namespace,
    _generate_aws_event,
    _generate_detail_class,
    _generate_marshaller,
    _map_csharp_type,
    _to_pascal_case,
    generate_dotnet_code_binding,
)

# Sample EC2 Instance State Change schema (typical AWS EventBridge schema)
EC2_SCHEMA_CONTENT = json.dumps(
    {
        "openapi": "3.0.0",
        "info": {"version": "1.0.0", "title": "EC2InstanceStateChangeNotification"},
        "components": {
            "schemas": {
                "AWSEvent": {
                    "type": "object",
                    "x-amazon-events-source": "aws.ec2",
                    "x-amazon-events-detail-type": "EC2 Instance State-change Notification",
                    "properties": {
                        "detail": {"$ref": "#/components/schemas/EC2InstanceStateChangeNotification"},
                        "detail-type": {"type": "string"},
                        "resources": {"type": "array", "items": {"type": "string"}},
                        "id": {"type": "string"},
                        "source": {"type": "string"},
                        "time": {"type": "string", "format": "date-time"},
                        "region": {"type": "string"},
                        "version": {"type": "string"},
                        "account": {"type": "string"},
                    },
                },
                "EC2InstanceStateChangeNotification": {
                    "type": "object",
                    "properties": {
                        "instance-id": {"type": "string"},
                        "state": {"type": "string"},
                    },
                },
            }
        },
    }
)

# Partner schema (MongoDB trigger)
PARTNER_SCHEMA_CONTENT = json.dumps(
    {
        "openapi": "3.0.0",
        "info": {"version": "1.0.0", "title": "MongoDBTrigger"},
        "components": {
            "schemas": {
                "AWSEvent": {
                    "type": "object",
                    "x-amazon-events-source": "aws.partner.mongodb.com",
                    "x-amazon-events-detail-type": "MongoDB Trigger",
                    "properties": {
                        "detail": {"$ref": "#/components/schemas/MongoDBTrigger"},
                        "detail-type": {"type": "string"},
                        "resources": {"type": "array", "items": {"type": "string"}},
                        "id": {"type": "string"},
                        "source": {"type": "string"},
                        "time": {"type": "string", "format": "date-time"},
                        "region": {"type": "string"},
                        "version": {"type": "string"},
                        "account": {"type": "string"},
                    },
                },
                "MongoDBTrigger": {
                    "type": "object",
                    "properties": {
                        "collection": {"type": "string"},
                        "database": {"type": "string"},
                        "event-count": {"type": "integer"},
                        "is-full-document": {"type": "boolean"},
                        "score": {"type": "number"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            }
        },
    }
)


class TestAWSEventGeneration(TestCase):
    def test_aws_event_cs_contains_generic_class(self):
        result = _generate_aws_event("Model.Aws.Ec2")
        self.assertIn("public class AWSEvent<T>", result)

    def test_aws_event_cs_has_correct_namespace(self):
        result = _generate_aws_event("Model.Aws.Ec2")
        self.assertIn("namespace Model.Aws.Ec2", result)

    def test_aws_event_cs_has_all_properties(self):
        result = _generate_aws_event("Model.Aws.Ec2")
        expected_properties = [
            "public T Detail { get; set; }",
            "public string DetailType { get; set; }",
            "public List<string> Resources { get; set; }",
            "public string Id { get; set; }",
            "public string Source { get; set; }",
            "public DateTime Time { get; set; }",
            "public string Region { get; set; }",
            "public string Version { get; set; }",
            "public string Account { get; set; }",
        ]
        for prop in expected_properties:
            self.assertIn(prop, result)

    def test_aws_event_cs_has_json_property_name_attributes(self):
        result = _generate_aws_event("Model.Aws.Ec2")
        self.assertIn('[JsonPropertyName("detail")]', result)
        self.assertIn('[JsonPropertyName("detail-type")]', result)
        self.assertIn('[JsonPropertyName("resources")]', result)
        self.assertIn('[JsonPropertyName("id")]', result)
        self.assertIn('[JsonPropertyName("source")]', result)
        self.assertIn('[JsonPropertyName("time")]', result)
        self.assertIn('[JsonPropertyName("region")]', result)
        self.assertIn('[JsonPropertyName("version")]', result)
        self.assertIn('[JsonPropertyName("account")]', result)

    def test_aws_event_cs_uses_system_text_json(self):
        result = _generate_aws_event("Model.Aws.Ec2")
        self.assertIn("using System.Text.Json.Serialization;", result)


class TestDetailClassGeneration(TestCase):
    def test_flat_schema_generates_correct_class_name(self):
        schema = json.loads(EC2_SCHEMA_CONTENT)
        schemas = schema["components"]["schemas"]
        detail_schema = schemas["EC2InstanceStateChangeNotification"]
        result = _generate_detail_class("Model.Aws.Ec2", "EC2InstanceStateChangeNotification", detail_schema, schemas)
        self.assertIn("public class EC2InstanceStateChangeNotification", result)

    def test_flat_schema_converts_property_names_to_pascal_case(self):
        schema = json.loads(EC2_SCHEMA_CONTENT)
        schemas = schema["components"]["schemas"]
        detail_schema = schemas["EC2InstanceStateChangeNotification"]
        result = _generate_detail_class("Model.Aws.Ec2", "EC2InstanceStateChangeNotification", detail_schema, schemas)
        self.assertIn("public string InstanceId { get; set; }", result)
        self.assertIn("public string State { get; set; }", result)

    def test_flat_schema_adds_json_property_name_for_non_pascal_names(self):
        schema = json.loads(EC2_SCHEMA_CONTENT)
        schemas = schema["components"]["schemas"]
        detail_schema = schemas["EC2InstanceStateChangeNotification"]
        result = _generate_detail_class("Model.Aws.Ec2", "EC2InstanceStateChangeNotification", detail_schema, schemas)
        self.assertIn('[JsonPropertyName("instance-id")]', result)

    def test_flat_schema_no_json_property_name_when_already_pascal(self):
        """'state' -> 'State' — different case, so attribute should be present."""
        schema = json.loads(EC2_SCHEMA_CONTENT)
        schemas = schema["components"]["schemas"]
        detail_schema = schemas["EC2InstanceStateChangeNotification"]
        result = _generate_detail_class("Model.Aws.Ec2", "EC2InstanceStateChangeNotification", detail_schema, schemas)
        # "state" != "State", so JsonPropertyName should be there
        self.assertIn('[JsonPropertyName("state")]', result)

    def test_partner_schema_generates_correct_types(self):
        schema = json.loads(PARTNER_SCHEMA_CONTENT)
        schemas = schema["components"]["schemas"]
        detail_schema = schemas["MongoDBTrigger"]
        result = _generate_detail_class("Model.Aws.Partner.Mongodb.Com", "MongoDBTrigger", detail_schema, schemas)
        self.assertIn("public string Collection { get; set; }", result)
        self.assertIn("public string Database { get; set; }", result)
        self.assertIn("public int EventCount { get; set; }", result)
        self.assertIn("public bool IsFullDocument { get; set; }", result)
        self.assertIn("public double Score { get; set; }", result)
        self.assertIn("public List<string> Tags { get; set; }", result)


class TestJsonSchemaTypeMapping(TestCase):
    def test_string_maps_to_string(self):
        self.assertEqual(_map_csharp_type("string"), "string")

    def test_integer_maps_to_int(self):
        self.assertEqual(_map_csharp_type("integer"), "int")

    def test_number_maps_to_double(self):
        self.assertEqual(_map_csharp_type("number"), "double")

    def test_boolean_maps_to_bool(self):
        self.assertEqual(_map_csharp_type("boolean"), "bool")

    def test_array_of_string_maps_to_list_string(self):
        result = _map_csharp_type("array", items={"type": "string"})
        self.assertEqual(result, "List<string>")

    def test_array_of_int_maps_to_list_int(self):
        result = _map_csharp_type("array", items={"type": "integer"})
        self.assertEqual(result, "List<int>")

    def test_array_with_ref_maps_to_list_of_ref(self):
        result = _map_csharp_type("array", items={"$ref": "#/components/schemas/Item"})
        self.assertEqual(result, "List<Item>")

    def test_object_with_property_name_maps_to_pascal_case(self):
        result = _map_csharp_type("object", property_name="nested-detail")
        self.assertEqual(result, "NestedDetail")

    def test_object_without_property_name_maps_to_object(self):
        result = _map_csharp_type("object")
        self.assertEqual(result, "object")

    def test_unknown_type_maps_to_object(self):
        result = _map_csharp_type("unknown_type")
        self.assertEqual(result, "object")


class TestMarshallerGeneration(TestCase):
    def test_marshaller_has_correct_namespace(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("namespace Model.Aws.Ec2", result)

    def test_marshaller_is_static_class(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("public static class Marshaller", result)

    def test_marshaller_has_unmarshal_event_method(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("public static AWSEvent<T> UnmarshalEvent<T>(Stream input)", result)

    def test_marshaller_has_unmarshal_method(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("public static T Unmarshal<T>(Stream input)", result)

    def test_marshaller_has_marshal_stream_method(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("public static void Marshal<T>(Stream output, T value)", result)

    def test_marshaller_has_marshal_string_method(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("public static string Marshal<T>(T value)", result)

    def test_marshaller_uses_system_text_json(self):
        result = _generate_marshaller("Model.Aws.Ec2")
        self.assertIn("using System.Text.Json;", result)
        self.assertIn("JsonSerializer.Deserialize", result)
        self.assertIn("JsonSerializer.Serialize", result)


class TestNamespaceDerivation(TestCase):
    def test_aws_ec2_schema(self):
        namespace, directory = _derive_namespace("aws.ec2@EC2InstanceStateChangeNotification")
        self.assertEqual(namespace, "Model.Aws.Ec2")
        self.assertEqual(directory, os.path.join("Model", "Aws", "Ec2"))

    def test_aws_s3_schema(self):
        namespace, directory = _derive_namespace("aws.s3@S3ObjectCreated")
        self.assertEqual(namespace, "Model.Aws.S3")
        self.assertEqual(directory, os.path.join("Model", "Aws", "S3"))

    def test_partner_mongodb_schema(self):
        namespace, directory = _derive_namespace("aws.partner.mongodb.com@MongoDBTrigger")
        self.assertEqual(namespace, "Model.Aws.Partner.Mongodb.Com")
        self.assertEqual(directory, os.path.join("Model", "Aws", "Partner", "Mongodb", "Com"))

    def test_single_segment_schema(self):
        namespace, directory = _derive_namespace("MyCustomEvent")
        self.assertEqual(namespace, "Model.Mycustomevent")
        self.assertEqual(directory, os.path.join("Model", "Mycustomevent"))


class TestPascalCaseConversion(TestCase):
    def test_hyphenated_name(self):
        self.assertEqual(_to_pascal_case("instance-id"), "InstanceId")

    def test_already_pascal(self):
        self.assertEqual(_to_pascal_case("State"), "State")

    def test_lowercase(self):
        self.assertEqual(_to_pascal_case("region"), "Region")

    def test_underscore_separated(self):
        self.assertEqual(_to_pascal_case("event_count"), "EventCount")


class TestEndToEndCodeGeneration(TestCase):
    def test_ec2_schema_generates_zip_with_three_files(self):
        output = io.BytesIO()
        generate_dotnet_code_binding(EC2_SCHEMA_CONTENT, "aws.ec2@EC2InstanceStateChangeNotification", output)
        output.seek(0)
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            self.assertEqual(len(names), 3)
            # Check files exist in the correct directory
            for name in names:
                self.assertTrue(
                    name.startswith(os.path.join("Model", "Aws", "Ec2") + os.sep) or name.startswith("Model/Aws/Ec2/")
                )

    def test_ec2_schema_zip_contains_expected_files(self):
        output = io.BytesIO()
        generate_dotnet_code_binding(EC2_SCHEMA_CONTENT, "aws.ec2@EC2InstanceStateChangeNotification", output)
        output.seek(0)
        with zipfile.ZipFile(output, "r") as zf:
            names = [os.path.basename(n) for n in zf.namelist()]
            self.assertIn("AWSEvent.cs", names)
            self.assertIn("EC2InstanceStateChangeNotification.cs", names)
            self.assertIn("Marshaller.cs", names)

    def test_partner_schema_generates_correct_namespace_dir(self):
        output = io.BytesIO()
        generate_dotnet_code_binding(PARTNER_SCHEMA_CONTENT, "aws.partner.mongodb.com@MongoDBTrigger", output)
        output.seek(0)
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            self.assertEqual(len(names), 3)
            basenames = [os.path.basename(n) for n in names]
            self.assertIn("AWSEvent.cs", basenames)
            self.assertIn("MongoDBTrigger.cs", basenames)
            self.assertIn("Marshaller.cs", basenames)
