"""Isolates code download and merge logic for dynamic Schemas template"""

import json
import os

import click
from botocore.exceptions import ClientError

from samcli.lib.schemas.cli_dotnet_codegen import generate_dotnet_code_binding
from samcli.local.common.runtime_template import SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING
from samcli.local.lambdafn.zip import unzip

DOTNET_RUNTIMES = {"dotnet8", "dotnet10"}


def do_download_source_code_binding(runtime, schema_template_details, schemas_api_caller, download_location):
    """
    Downloads source code binding for given registry and schema version,
    generating the code bindings if they haven't been generated first.
    For dotnet runtimes, generates C# code locally since the Schemas API
    does not support C# as a code binding language.
    :param runtime: Lambda runtime
    :param schema_template_details: e.g: registry_name, schema_name, schema_version
    :param schemas_api_caller: the schemas api caller object
    :param download_location: the download location
    :return: directory location where code is downloaded
    """
    registry_name = schema_template_details["registry_name"]
    schema_name = schema_template_details["schema_full_name"]
    schema_version = schema_template_details["schema_version"]

    click.echo("Event code binding Registry: %s and Schema: %s" % (registry_name, schema_name))
    click.echo("Generating code bindings...")

    if runtime in DOTNET_RUNTIMES:
        return _do_dotnet_codegen(registry_name, schema_name, schemas_api_caller, download_location)

    schemas_runtime = SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING.get(runtime)
    try:
        # Optimistically try to get the code bindings first...
        return schemas_api_caller.download_source_code_binding(
            schemas_runtime, registry_name, schema_name, schema_version, download_location
        )
    except ClientError as e:
        # If the code bindings are not available, the API throws a NotFoundException, so we need to generate them
        if e.response["Error"]["Code"] == "NotFoundException":
            # At this point, any exceptions should percolate out upwards, and be wrapped as generic SchemasApiException
            # put code binding (to trigger the code generation)
            schemas_api_caller.put_code_binding(schemas_runtime, registry_name, schema_name, schema_version)
            # wait till binding is generated
            schemas_api_caller.poll_for_code_binding_status(schemas_runtime, registry_name, schema_name, schema_version)
            # Try download code binding again
            return schemas_api_caller.download_source_code_binding(
                schemas_runtime, registry_name, schema_name, schema_version, download_location
            )
        raise e


def _do_dotnet_codegen(registry_name, schema_name, schemas_api_caller, download_location):
    """
    Fetch the raw JSON Schema via DescribeSchema and generate C# code bindings locally.
    Writes a ZIP archive to download_location, compatible with do_extract_and_merge_schemas_code.
    """
    describe_response = schemas_api_caller._schemas_client.describe_schema(
        RegistryName=registry_name, SchemaName=schema_name
    )
    schema_content = describe_response["Content"]
    generate_dotnet_code_binding(schema_content, schema_name, download_location)


def do_extract_and_merge_schemas_code(download_location, output_dir, project_name, template_location):
    """
    Unzips schemas generated code and merge it with cookiecutter genertaed source.
    :param download_location:
    :param output_dir:
    :param project_name:
    :param template_location:
    """
    click.echo("Merging code bindings...")
    cookiecutter_json_path = os.path.join(template_location, "cookiecutter.json")
    with open(cookiecutter_json_path, "r") as cookiecutter_file:
        cookiecutter_json_data = cookiecutter_file.read()
        cookiecutter_json = json.loads(cookiecutter_json_data)
        function_name = cookiecutter_json["function_name"]
        copy_location = os.path.join(output_dir, project_name, function_name)
        unzip(download_location, copy_location)
