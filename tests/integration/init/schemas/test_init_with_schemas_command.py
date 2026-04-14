import tempfile
from pathlib import Path
from unittest import skipIf

import pytest
from boto3.session import Session
from click.testing import CliRunner

from samcli.commands.init import cli as init_cmd
from samcli.commands.init.init_templates import InitTemplates
from tests.integration.init.schemas.schemas_test_data_setup import SchemaTestDataSetup
from tests.testing_utils import RUN_BY_CANARY, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI

# Schemas tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SCHEMA_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


def _dotnet_eventbridge_templates_available():
    """Check if dotnet EventBridge templates are available in the manifest."""
    try:
        templates = InitTemplates()
        manifest = templates.get_preprocessed_manifest("dotnet8", None, None, None)
        return "Infrastructure event management" in manifest and "dotnet8" in manifest.get(
            "Infrastructure event management", {}
        )
    except Exception:
        return False


SKIP_DOTNET_EB_TESTS = not _dotnet_eventbridge_templates_available()


def _get_registry_position(registry_name):
    """Query EventBridge Schema registries and return the 1-based menu position for the given registry name.

    The sam init interactive prompt lists registries in alphabetical order.
    This avoids hardcoding positions that break when new registries are added to the account.
    """
    session = Session()
    client = session.client("schemas", region_name=session.region_name)
    paginator = client.get_paginator("list_registries")
    registries = []
    for page in paginator.paginate():
        registries.extend(r["RegistryName"] for r in page["Registries"])
    registries.sort()
    for i, name in enumerate(registries, 1):
        if name == registry_name:
            return i
    raise ValueError(f"Registry '{registry_name}' not found. Available: {registries}")


@skipIf(SKIP_SCHEMA_TESTS, "Skip schema test")
@pytest.mark.xdist_group(name="sam_init")
class TestBasicInitWithEventBridgeCommand(SchemaTestDataSetup):
    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 4: Java Runtime
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # 1: select schema from cli_paginator
        # {aws_registry_pos}: select aws.events as registries (dynamic position)
        # 9: select schema AWSAPICallViaCloudTrail
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
1
{aws_registry_pos}
9
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp, "--debug"], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_partner_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 4: Java Runtime
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {partner_registry_pos}: partner registry (dynamic position)
        # 1: select aws schema
        partner_registry_pos = _get_registry_position("partner-registry")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{partner_registry_pos}
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )
            self.assertTrue(
                Path(
                    expected_output_folder,
                    "HelloWorldFunction",
                    "src",
                    "main",
                    "java",
                    "schema",
                    "schema_test_0",
                    "TicketCreated.java",
                ).is_file()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_pagination(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 4: Java Runtime
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {pagination_registry_pos}: select pagination-registry (dynamic position)
        # N: Go to next page
        # P: Go to previous page
        # 2: select 2nd schema
        pagination_registry_pos = _get_registry_position("test-pagination")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{pagination_registry_pos}
N
P
2
        """

        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_customer_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 4: Java Runtime
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {other_schema_pos}: select other-schema registry (dynamic position)
        # 1: select 1st schema
        other_schema_pos = _get_registry_position("other-schema")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{other_schema_pos}
1
                """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )
            self.assertTrue(
                Path(
                    expected_output_folder,
                    "HelloWorldFunction",
                    "src",
                    "main",
                    "java",
                    "schema",
                    "schema_test_0",
                    "Some_Awesome_Schema.java",
                ).is_file()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_schemas_python(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 8: Python 3.9
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python39: response to name
        # Y: Use default aws configuration
        # 1: select schema from cli_paginator
        # {aws_registry_pos}: select aws.events as registries (dynamic position)
        # 1: select aws schema
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
8
8
2
N
N
N
eb-app-python39
Y
1
{aws_registry_pos}
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-python39")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_schemas_go(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 1: Go 1.x
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-go: response to name
        # Y: Use default aws configuration
        # 4: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
1
2
N
N
N
eb-app-go
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-go")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "HelloWorld", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_non_default_profile_selection(self):
        self._init_custom_config("mynewprofile", "us-west-2")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 8: Python 3.9
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python38: response to name
        # N: Use default profile
        # 2: uses second profile from displayed one (myprofile)
        # schemas aws region us-east-1
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
8
2
N
N
N
eb-app-python39
3
N
2
us-east-1
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-python39")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_non_supported_schemas_region(self):
        self._init_custom_config("default", "cn-north-1")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 7: Python 3.9
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python39: response to name
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
8
2
N
N
N
eb-app-python39
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)
            self.assertTrue(result.exception)


@skipIf(
    SKIP_SCHEMA_TESTS or SKIP_DOTNET_EB_TESTS, "Skip dotnet EventBridge tests (templates not available or no creds)"
)
@pytest.mark.xdist_group(name="sam_init")
class TestDotnetEventBridgeInit(SchemaTestDataSetup):
    @pytest.mark.timeout(300)
    def test_init_interactive_with_dotnet8_event_bridge_hello_world(self):
        """
        Integration test for dotnet8 EventBridge Hello World template.
        Requires dotnet EventBridge templates to be available in the manifest.
        The menu positions for use case and runtime are dynamically determined
        based on the current manifest.
        """
        templates = InitTemplates()
        manifest = templates.get_preprocessed_manifest(None, None, None, None)

        # Find the position of "Infrastructure event management" use case
        use_cases = list(manifest.keys())
        use_case_pos = use_cases.index("Infrastructure event management") + 1

        # Find the position of dotnet8 among runtimes for this use case
        runtimes = list(manifest["Infrastructure event management"].keys())
        from samcli.commands.init.interactive_init_flow import get_sorted_runtimes

        sorted_runtimes = get_sorted_runtimes(runtimes)
        runtime_pos = sorted_runtimes.index("dotnet8") + 1

        # dotnet has only cli-package dep manager (auto-selected)
        # Find position of hello-world template
        zip_templates = manifest["Infrastructure event management"]["dotnet8"]["Zip"]
        hello_templates = [t for t in zip_templates if t.get("dependencyManager") == "cli-package"]
        hello_world_templates = [t for t in hello_templates if t.get("appTemplate") == "eventBridge-hello-world"]
        if not hello_world_templates:
            self.skipTest("eventBridge-hello-world template not found for dotnet8")

        # If there are multiple templates with cli-package dep manager, find hello-world position
        template_pos = next(
            i + 1 for i, t in enumerate(hello_templates) if t.get("appTemplate") == "eventBridge-hello-world"
        )

        user_input = f"""
1
{use_case_pos}
{runtime_pos}
{template_pos}
N
N
N
eb-dotnet-hello
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception, msg=f"Exception: {result.output}")
            expected_output_folder = Path(temp, "eb-dotnet-hello")
            self.assertTrue(expected_output_folder.exists())
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "template.yaml").is_file())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_dotnet8_event_bridge_schema_app(self):
        """
        Integration test for dotnet8 EventBridge Schema App template with custom C# codegen.
        Requires dotnet EventBridge templates and AWS credentials.
        """
        templates = InitTemplates()
        manifest = templates.get_preprocessed_manifest(None, None, None, None)

        use_cases = list(manifest.keys())
        use_case_pos = use_cases.index("Infrastructure event management") + 1

        runtimes = list(manifest["Infrastructure event management"].keys())
        from samcli.commands.init.interactive_init_flow import get_sorted_runtimes

        sorted_runtimes = get_sorted_runtimes(runtimes)
        runtime_pos = sorted_runtimes.index("dotnet8") + 1

        zip_templates = manifest["Infrastructure event management"]["dotnet8"]["Zip"]
        cli_package_templates = [t for t in zip_templates if t.get("dependencyManager") == "cli-package"]
        schema_app_templates = [t for t in cli_package_templates if t.get("appTemplate") == "eventBridge-schema-app"]
        if not schema_app_templates:
            self.skipTest("eventBridge-schema-app template not found for dotnet8")

        template_pos = next(
            i + 1 for i, t in enumerate(cli_package_templates) if t.get("appTemplate") == "eventBridge-schema-app"
        )

        aws_registry_pos = _get_registry_position("aws.events")

        user_input = f"""
1
{use_case_pos}
{runtime_pos}
{template_pos}
N
N
N
eb-dotnet-schema
Y
1
{aws_registry_pos}
9
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp, "--debug"], input=user_input)

            self.assertFalse(result.exception, msg=f"Exception: {result.output}")
            expected_output_folder = Path(temp, "eb-dotnet-schema")
            self.assertTrue(expected_output_folder.exists())
            self.assertTrue(expected_output_folder.is_dir())

    @pytest.mark.timeout(300)
    def test_init_non_interactive_with_dotnet8_event_bridge_hello_world(self):
        """
        Integration test for non-interactive dotnet8 EventBridge Hello World.
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(
                init_cmd,
                [
                    "--no-interactive",
                    "--runtime",
                    "dotnet8",
                    "--dependency-manager",
                    "cli-package",
                    "--app-template",
                    "eventBridge-hello-world",
                    "--name",
                    "eb-dotnet-ni",
                    "--output-dir",
                    temp,
                ],
            )

            self.assertFalse(result.exception, msg=f"Exception: {result.output}")
            expected_output_folder = Path(temp, "eb-dotnet-ni")
            self.assertTrue(expected_output_folder.exists())
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "template.yaml").is_file())
