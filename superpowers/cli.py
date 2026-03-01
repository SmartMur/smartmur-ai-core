import click

from superpowers import __version__
from superpowers.cli_skill import skill_info, skill_list, skill_run, skill_sync, skill_validate
from superpowers.cli_skill_create import skill_create
from superpowers.cli_cron import cron_group
from superpowers.cli_launchd import daemon
from superpowers.cli_vault import vault_group


@click.group()
@click.version_option(version=__version__, prog_name="claw")
def main():
    """Claude Superpowers — autonomous skill execution and orchestration."""


main.add_command(cron_group)
main.add_command(daemon)
main.add_command(vault_group)


@main.group(invoke_without_command=True)
@click.pass_context
def skill(ctx):
    """Manage and execute skills."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(skill_list)


skill.add_command(skill_create)
skill.add_command(skill_list)
skill.add_command(skill_info)
skill.add_command(skill_run)
skill.add_command(skill_sync)
skill.add_command(skill_validate)


@main.command()
@click.argument("target", required=False)
def msg(target):
    """Send messages via Slack, Telegram, Discord, email."""
    click.echo(f"msg: {target or 'inbox'}")


@main.command()
@click.argument("name", required=False)
def workflow(name):
    """Run multi-step workflows."""
    click.echo(f"workflow: {name or 'list all'}")


@main.command()
@click.argument("target", required=False)
def ssh(target):
    """Execute commands on remote hosts."""
    click.echo(f"ssh: {target or 'list hosts'}")


@main.command()
def status():
    """Show system status across all subsystems."""
    click.echo("claude-superpowers status: all systems nominal")
