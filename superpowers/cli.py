import click

from superpowers import __version__
from superpowers.cli_agent import agent_group
from superpowers.cli_audit import audit_group
from superpowers.cli_browse import browse_group
from superpowers.cli_cron import cron_group
from superpowers.cli_dag import dag_group
from superpowers.cli_dashboard import dashboard_cmd
from superpowers.cli_intake import intake_group
from superpowers.cli_jobs import jobs_group
from superpowers.cli_launchd import daemon
from superpowers.cli_memory import memory_group
from superpowers.cli_msg import msg_group
from superpowers.cli_orchestrate import orchestrate_group
from superpowers.cli_pack import pack_group
from superpowers.cli_policy import policy_group
from superpowers.cli_report import report_group
from superpowers.cli_setup import setup_group
from superpowers.cli_skill import (
    skill_auto_install,
    skill_info,
    skill_link,
    skill_list,
    skill_run,
    skill_sync,
    skill_validate,
)
from superpowers.cli_skill_create import skill_create
from superpowers.cli_ssh import ssh_group
from superpowers.cli_status import status_dashboard
from superpowers.cli_template import template_group
from superpowers.cli_vault import vault_group
from superpowers.cli_watcher import watcher_group
from superpowers.cli_workflow import workflow_group


@click.group()
@click.version_option(version=__version__, prog_name="claw")
def main():
    """Claude Superpowers — autonomous skill execution and orchestration."""


main.add_command(agent_group)
main.add_command(audit_group)
main.add_command(browse_group)
main.add_command(cron_group)
main.add_command(dag_group)
main.add_command(dashboard_cmd)
main.add_command(intake_group)
main.add_command(jobs_group)
main.add_command(daemon)
main.add_command(memory_group)
main.add_command(msg_group)
main.add_command(orchestrate_group)
main.add_command(pack_group)
main.add_command(policy_group)
main.add_command(setup_group)
main.add_command(ssh_group)
main.add_command(template_group)
main.add_command(vault_group)
main.add_command(watcher_group)
main.add_command(workflow_group)
main.add_command(report_group)
main.add_command(status_dashboard)


@main.group(invoke_without_command=True)
@click.pass_context
def skill(ctx):
    """Manage and execute skills."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(skill_list)


skill.add_command(skill_auto_install)
skill.add_command(skill_create)
skill.add_command(skill_list)
skill.add_command(skill_info)
skill.add_command(skill_link)
skill.add_command(skill_run)
skill.add_command(skill_sync)
skill.add_command(skill_validate)
