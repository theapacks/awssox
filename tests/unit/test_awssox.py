# ./tests/unit/test_awssox.py  # noqa: D100

import subprocess
from unittest.mock import patch

import pytest
import typer

import awssox.awssox as awssox_module
from awssox.awssox import read_aws_profiles


@pytest.fixture
def mock_profiles():
    """Sample dictionary of AWS profiles for testing."""
    return {
        "dev-1": {
            "sso_start_url": "https://aws.apps.com/start",
            "sso_region": "us-west-2",
            "sso_account_id": "123456789012",
            "sso_role_name": "devOpsRole",
            "region": "us-west-2",
            "output": "json",
        },
        "dev-1-admin-role": {
            "role_arn": "arn:aws:iam::123456789012:role/dev-1-admin-role",
            "source_profile": "dev-1",
        },
        "dev-2-admin-role": {
            "role_arn": "arn:aws:iam::123456789012:role/dev-2-admin-role",
            "source_profile": "dev-2",
        },
        "some-other-profile": {
            "region": "us-east-1",
            "output": "text",
        },
    }


###############################################################################
# find_role_profiles
###############################################################################


def test_find_role_profiles_no_match(mock_profiles):
    """No roles match if source_profile doesn't match the base."""
    roles = awssox_module.find_role_profiles(mock_profiles, "non-existent")
    if roles != []:
        raise AssertionError(
            "Expected roles to be an empty list, but got: {}".format(roles)
        )


def test_find_role_profiles_match_single(mock_profiles):
    """Returns matching role profile(s) for dev-1 -> dev-1-admin-role."""
    roles = awssox_module.find_role_profiles(mock_profiles, "dev-1")
    assert roles == ["dev-1-admin-role"]


def test_read_aws_profiles_full_coverage():
    """Ensure we call parser.optionxform, parser.read, and parse multiple sections.

    This ensures lines 55-65 are fully covered.
    """
    with (
        patch("configparser.ConfigParser.read") as mock_read,
        patch("configparser.ConfigParser.sections") as mock_sections,
        patch("configparser.ConfigParser.__getitem__") as mock_getitem,
    ):

        mock_sections.return_value = ["profile dev-1", "profile dev-2"]
        mock_getitem.side_effect = lambda section: {
            "region": "us-west-2",
            "output": "json",
        }

        result = read_aws_profiles()
        mock_read.assert_called_once()
        mock_sections.assert_called_once()

        assert "dev-1" in result
        assert "dev-2" in result
        assert result["dev-1"]["region"] == "us-west-2"
        assert result["dev-2"]["output"] == "json"


###############################################################################
# pick_base_profile
###############################################################################
@pytest.mark.parametrize(
    "profile_names, selected, should_raise, expected",
    [
        (["one"], [], True, None),  # user selected nothing => raise typer.Exit
        (["one"], ["one", "two"], True, None),  # multiple => raise
        (["one", "two"], ["one"], False, "one"),  # single => ok
    ],
)
@patch("questionary.checkbox")
def test_pick_base_profile(
    mock_checkbox, profile_names, selected, should_raise, expected
):
    """Check pick_base_profile logic with different user selections."""
    mock_checkbox.return_value.ask.return_value = selected

    # minimal dict with just the keys
    mock_profiles_dict = {name: {} for name in profile_names}

    if should_raise:
        with pytest.raises(typer.Exit):
            awssox_module.pick_base_profile(mock_profiles_dict)
    else:
        chosen = awssox_module.pick_base_profile(mock_profiles_dict)
        assert chosen == expected


###############################################################################
# perform_sso_login
###############################################################################
@patch("subprocess.run")
def test_perform_sso_login_success(mock_run):
    """Ensure perform_sso_login doesn't raise on successful subprocess call."""
    mock_run.return_value.returncode = 0
    awssox_module.perform_sso_login("dev-1")

    mock_run.assert_called_once()
    (args, kwargs) = mock_run.call_args
    assert args[0][1:] == ["sso", "login", "--profile", "dev-1"]
    assert "aws" in args[0][0]  # or a regex check
    assert kwargs["check"] is True


@patch(
    "subprocess.run",
    side_effect=subprocess.CalledProcessError(returncode=1, cmd="aws sso login"),
)
def test_perform_sso_login_failure(mock_run):
    """perform_sso_login should raise typer.Exit on CalledProcessError."""
    with pytest.raises(typer.Exit):
        awssox_module.perform_sso_login("dev-1")


###############################################################################
# pick_role_profile
###############################################################################
@pytest.mark.parametrize(
    "input_selection, expected_role",
    [
        ([], "Skip role assumption"),  # pressed Enter => skip
        (["some-role", "another-role"], "Skip role assumption"),  # multiple => skip
        (["some-role"], "some-role"),  # single => chosen
    ],
)
@patch("questionary.checkbox")
def test_pick_role_profile(mock_checkbox, input_selection, expected_role):
    """Check picking a single role or skipping based on user selection."""
    mock_checkbox.return_value.ask.return_value = input_selection

    roles = ["some-role"]
    result = awssox_module.pick_role_profile(roles)
    assert result == expected_role


###############################################################################
# show_export_instructions
###############################################################################
@patch("typer.echo")
@patch("platform.system", return_value="Windows")
def test_show_export_instructions_windows(mock_platform, mock_echo):
    """Verify Windows instructions are printed."""
    awssox_module.show_export_instructions("dev-1-admin-role")

    all_calls = [str(call) for call in mock_echo.call_args_list]
    assert "For PowerShell" in "".join(all_calls)
    assert "set AWS_PROFILE=dev-1-admin-role" in "".join(all_calls)


@patch("typer.echo")
@patch("platform.system", return_value="Linux")
def test_show_export_instructions_unix(mock_platform, mock_echo):
    """Verify *nix export instructions are printed."""
    awssox_module.show_export_instructions("dev-1-admin-role")

    all_calls = [str(call) for call in mock_echo.call_args_list]
    assert "export AWS_PROFILE=dev-1-admin-role" in "".join(all_calls)


###############################################################################
# list_profiles
###############################################################################
@patch("awssox.awssox.read_aws_profiles")
def test_list_profiles_no_profiles(mock_read, capsys):
    """list_profiles should raise an Exit if no profiles found."""
    mock_read.return_value = {}
    with pytest.raises(typer.Exit):
        awssox_module.list_profiles()

    captured = capsys.readouterr()
    assert "No profiles found" in captured.out


@patch("awssox.awssox.read_aws_profiles")
def test_list_profiles_some_profiles(mock_read, capsys):
    """list_profiles prints out the found profiles.

    Does NOT raise Exit if profiles exist.
    """
    mock_read.return_value = {"dev-1": {}, "dev-2": {}}
    awssox_module.list_profiles()

    captured = capsys.readouterr()
    assert "Available AWS Profiles:" in captured.out
    assert "- dev-1" in captured.out
    assert "- dev-2" in captured.out


@pytest.mark.usefixtures("mock_profiles")
def test_list_profiles_print_output(capsys, mock_profiles):
    """Example test for list_profiles when profiles exist."""
    with patch.object(awssox_module, "read_aws_profiles", return_value=mock_profiles):
        awssox_module.list_profiles()
    captured = capsys.readouterr()
    assert "Available AWS Profiles:" in captured.out
    assert "- dev-1" in captured.out
    assert "- dev-1-admin-role" in captured.out


@patch("sys.argv", ["awssox", "list-profiles"])
@patch.object(awssox_module, "read_aws_profiles", return_value={"dev-1": {}})
def test_cli_list_profiles(mock_read, capsys):
    """Invoke the CLI directly with 'list-profiles' to ensure lines in cli().

    This ensures lines in cli() are covered.
    """
    with pytest.raises(SystemExit):
        awssox_module.cli()

    captured = capsys.readouterr()
    assert "Available AWS Profiles:" in captured.out
    assert "- dev-1" in captured.out


###############################################################################
# login (Full Command)
###############################################################################
@patch.object(awssox_module, "read_aws_profiles")
@patch.object(awssox_module, "pick_base_profile")
@patch.object(awssox_module, "perform_sso_login")
@patch.object(awssox_module, "find_role_profiles")
@patch.object(awssox_module, "pick_role_profile")
@patch.object(awssox_module, "show_export_instructions")
def test_login_full_flow(
    mock_show_export,
    mock_pick_role,
    mock_find_roles,
    mock_login,
    mock_pick_base,
    mock_read,
    capsys,
):
    """Test the login command from start to finish, ensuring each piece is called."""
    mock_read.return_value = {"dev-1": {}}
    mock_pick_base.return_value = "dev-1"
    mock_find_roles.return_value = ["dev-1-admin-role"]
    mock_pick_role.return_value = "dev-1-admin-role"

    # login calls sys.exit(0), so we expect SystemExit
    with pytest.raises(SystemExit):
        awssox_module.login()

    # Verify each helper function was called in sequence
    mock_read.assert_called_once()
    mock_pick_base.assert_called_once()
    mock_login.assert_called_once_with("dev-1")
    mock_find_roles.assert_called_once_with({"dev-1": {}}, "dev-1")
    mock_pick_role.assert_called_once_with(["dev-1-admin-role"])
    mock_show_export.assert_called_once_with("dev-1-admin-role")

    captured = capsys.readouterr()
    assert "Logging in with profile: dev-1" in captured.out
    assert "Login successful!" in captured.out


@patch.object(awssox_module, "read_aws_profiles")
def test_login_no_profiles(mock_read, capsys):
    """If read_aws_profiles returns {}, login should raise Exit.

    A "No profiles found" message should be displayed.
    """
    mock_read.return_value = {}
    with pytest.raises(typer.Exit):
        awssox_module.login()

    captured = capsys.readouterr()
    assert "No profiles found" in captured.out


@patch.object(awssox_module, "read_aws_profiles", return_value={"dev-1": {}})
@patch.object(awssox_module, "pick_base_profile", return_value="dev-1")
@patch.object(awssox_module, "perform_sso_login")
@patch.object(awssox_module, "find_role_profiles", return_value=[])
def test_login_no_role_profiles(mock_find, mock_login_fn, mock_pick, mock_read, capsys):
    """If there are no associated role profiles, code prints a message.

    The function then returns early.
    """
    awssox_module.login()

    captured = capsys.readouterr()
    assert "No associated role profile found. Exiting..." in captured.out


@patch.object(awssox_module, "read_aws_profiles", return_value={"dev-1": {}})
@patch.object(awssox_module, "pick_base_profile", return_value="dev-1")
@patch.object(awssox_module, "perform_sso_login")
@patch.object(awssox_module, "find_role_profiles", return_value=["dev-1-admin-role"])
@patch.object(awssox_module, "pick_role_profile", return_value="Skip role assumption")
def test_login_skip_role(
    mock_pick_role, mock_find, mock_login_fn, mock_pick, mock_read, capsys
):
    """If user chooses to skip role assumption, we exit."""
    awssox_module.login()

    captured = capsys.readouterr()
    assert "Skipping role assumption. Goodbye!" in captured.out
