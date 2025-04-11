"""awssox.py: A CLI tool to simplify AWS SSO logins.

This tool provides an interactive interface to select profiles, perform SSO logins,
and manage role assumptions.
"""

import configparser
import os
import platform
import re
import shutil
import subprocess
import sys

import questionary
import typer
from questionary import Style

###############################################################################
# App Setup
###############################################################################

app = typer.Typer(help="A CLI tool to simplify AWS SSO logins.")

# A custom style for questionary prompts
custom_style_fancy = Style(
    [
        ("qmark", "fg:#E91E63 bold"),  # question mark
        ("question", "bold"),  # question text
        ("answer", "fg:#2196f3 bold"),  # user answer
        ("pointer", "fg:#673ab7 bold"),  # pointer used in select boxes
        ("highlighted", "fg:#03A9F4 bold"),
        ("selected", "fg:#673ab7 bold"),  # style for a selected item
        ("separator", "fg:#cc5454"),
        ("instruction", ""),
        ("text", ""),
        ("disabled", "fg:#858585 italic"),
    ]
)

###############################################################################
# Helper Functions
###############################################################################


def read_aws_profiles(config_file: str = None) -> dict:
    """Read AWS profiles from a config file path.

    Defaulting to ~/.aws/config if none is provided. Return a dict of profiles.
    """
    if not config_file:
        config_file = os.path.expanduser("~/.aws/config")

    parser = configparser.ConfigParser()
    parser.optionxform = str  # Keep case sensitivity of keys
    parser.read(config_file)

    profiles = {}
    for section in parser.sections():
        raw_profile_name = section.replace("profile ", "")
        profiles[raw_profile_name] = dict(parser[section])

    return profiles


def pick_base_profile(profiles: dict) -> str:
    """Prompt the user to select exactly one base (SSO) profile.

    Return the chosen profile name, or raise typer.Exit if none or multiple selected.
    """
    profile_names = sorted(profiles.keys())
    selected = questionary.checkbox(
        "Select an AWS profile\n (use ↑/↓ to move, SPACE to check, ENTER to confirm)",
        choices=profile_names,
        style=custom_style_fancy,
        instruction="",
    ).ask()

    if not selected:
        typer.echo(typer.style("No profile selected. Exiting.", fg=typer.colors.YELLOW))
        raise typer.Exit()
    if len(selected) > 1:
        typer.echo(
            typer.style(
                "Multiple profiles selected. Please select only one.",
                fg=typer.colors.RED,
            )
        )
        raise typer.Exit()

    return selected[0]


def perform_sso_login(profile: str):
    """Run 'aws sso login --profile <profile>', raising typer.Exit on failure."""
    if not re.match(r"^[A-Za-z0-9._\-\+]+$", profile):
        typer.echo(typer.style("Invalid profile name!", fg=typer.colors.RED))
        raise typer.Exit(code=1)
    try:
        aws_executable = shutil.which("aws")
        if not aws_executable:
            typer.echo(typer.style("AWS CLI not found in PATH.", fg=typer.colors.RED))
            raise typer.Exit(code=1)

        subprocess.run(  # noqa: S603
            [aws_executable, "sso", "login", "--profile", profile], check=True
        )
    except subprocess.CalledProcessError as exc:
        typer.echo(typer.style("Login failed! See error above.", fg=typer.colors.RED))
        raise typer.Exit(code=exc.returncode) from exc


def find_role_profiles(profiles: dict, base_profile: str) -> list:
    """Return a list of role profiles that reference `base_profile`.

    Each role profile must have 'role_arn' and 'source_profile = base_profile'.
    """
    role_profile_names = []
    for name, data in profiles.items():
        if data.get("source_profile") == base_profile and "role_arn" in data:
            role_profile_names.append(name)
    return role_profile_names


def pick_role_profile(role_profile_names: list) -> str:
    """Prompt the user to pick exactly one role profile (or skip).

    Return the chosen role profile name, or the string 'Skip role assumption'.
    """
    role_profile_names.append("Skip role assumption")

    selected = questionary.checkbox(
        "Role(s) found referencing this profile.\n"
        "Pick one to assume or skip:\n"
        "(use ↑/↓ to move, SPACE to check, ENTER to confirm)",
        choices=role_profile_names,
        style=custom_style_fancy,
        instruction="",
    ).ask()

    if not selected:
        # If user hits enter without selecting anything
        return "Skip role assumption"
    if len(selected) > 1:
        typer.echo(
            typer.style(
                "Multiple roles selected. Please select only one or skip.",
                fg=typer.colors.RED,
            )
        )
        return "Skip role assumption"

    return selected[0]


def show_export_instructions(role_choice: str):
    """Print instructions on how to export AWS_PROFILE for Unix/Windows.

    Confirm caller identity with 'aws sts get-caller-identity'.
    """
    system_os = platform.system().lower()

    typer.echo(
        typer.style(
            f"Selected role profile: {role_choice}",
            fg=typer.colors.CYAN,
            bold=True,
        )
    )
    typer.echo(
        typer.style(
            "Run the following in your shell or use eval to persist it:",
            fg=typer.colors.MAGENTA,
        )
    )

    if "windows" in system_os:
        # For PowerShell or CMD
        typer.echo(
            typer.style(
                f'\n# For PowerShell:\n$Env:AWS_PROFILE = "{role_choice}"\n'
                f"# For CMD:\nset AWS_PROFILE={role_choice}\n"
                "# Then run:\naws sts get-caller-identity\n",
                fg=typer.colors.YELLOW,
            )
        )
    else:
        # For bash, zsh, etc.
        typer.echo(
            typer.style(
                f"\nexport AWS_PROFILE={role_choice}\n"
                "# Then run:\naws sts get-caller-identity\n",
                fg=typer.colors.YELLOW,
            )
        )


###############################################################################
# Typer Commands
###############################################################################


@app.command()
def list_profiles(
    config_file: str = typer.Option(
        None,
        "--config-file",
        "-c",
        help="Path to AWS config file (defaults to ~/.aws/config).",
    )
):
    """List all AWS profiles found in the specified config file."""
    profiles = read_aws_profiles(config_file)
    if not profiles:
        typer.echo("No profiles found.")
        raise typer.Exit()

    typer.echo("Available AWS Profiles:")
    for profile_name in sorted(profiles.keys()):
        typer.echo(f" - {profile_name}")


@app.command()
def login(
    config_file: str = typer.Option(
        None,
        "--config-file",
        "-c",
        help="Path to AWS config file (defaults to ~/.aws/config).",
    )
):
    """Prompt user to pick one AWS profile from the specified config file.

    Then run 'aws sso login', optionally pick a role referencing that profile,
    and display how to export AWS_PROFILE for the selected role.
    """
    profiles = read_aws_profiles(config_file)
    if not profiles:
        typer.echo(
            typer.style("No profiles found in ~/.aws/config.", fg=typer.colors.RED)
        )
        raise typer.Exit()

    # Step 1: Pick base profile

    chosen_profile = pick_base_profile(profiles)

    typer.echo(
        typer.style(
            f"\nLogging in with profile: {chosen_profile}",
            fg=typer.colors.CYAN,
            bold=True,
        )
    )

    # Step 2: Perform SSO login
    perform_sso_login(chosen_profile)
    typer.echo(
        typer.style("Login successful for profile: ", fg=typer.colors.GREEN, bold=True)
        + typer.style(chosen_profile, fg=typer.colors.MAGENTA, bold=True)
        + typer.style(" ✅", fg=typer.colors.GREEN, bold=True)
    )

    # Step 3: Find any role profiles referencing the chosen base
    role_profile_names = find_role_profiles(profiles, chosen_profile)
    if not role_profile_names:
        typer.echo(
            typer.style(
                "No associated role profile found. Exiting...",
                fg=typer.colors.YELLOW,
            )
        )
        return

    # Step 4: Prompt user to pick one role (or skip)
    role_choice = pick_role_profile(role_profile_names)
    if role_choice == "Skip role assumption":
        typer.echo(
            typer.style("Skipping role assumption. Goodbye!", fg=typer.colors.YELLOW)
        )
        return

    # Step 5: Show instructions for exporting AWS_PROFILE
    show_export_instructions(role_choice)

    sys.exit(0)


def cli():
    """Entry point when installed via Poetry.

    This function serves as the main entry point for the CLI application.
    """
    app()
