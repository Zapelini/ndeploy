import click
import os

from ndeploy import core
from ndeploy import environment_repository
from ndeploy import deployer
from ndeploy import provider
from ndeploy.shell_exec import ShellExec
from ndeploy.exception import NDeployError

# dependencies resolution
NDEPLOY_HOME = os.path.expanduser('~')+"/.ndeploy"
env_repository = environment_repository.EnvironmentRepository(NDEPLOY_HOME, ShellExec())
provider_repository = provider.ProviderRepository()
deployer = deployer.Deployer(provider_repository, env_repository)
ndeploy_core = core.NDeployCore(env_repository, deployer)


@click.group()
def ndeploy():
    pass


@click.option('-f', '--file_url', prompt='App deployment file URL',
              help="App deployment file URL, ex.: git@myhost.com:myconfs/{group} master {name}.json.")
@click.option('-h', '--deploy_host', prompt='Deploy deploy_host', help="Deploy deploy_host.")
@click.option('-n', '--name', prompt='Environment name', help='Environment name.')
@click.option('-t', '--type', prompt='Provider type', help="Provider type.",
              type=click.Choice(provider_repository.get_available_providers().keys()))
@ndeploy.command()
def addenv(**kwargs):
    ndeploy_core.add_environment(name=kwargs['name'],
                                 type=kwargs['type'],
                                 deploy_host=kwargs['deploy_host'],
                                 app_deployment_file_url=kwargs['file_url'])
    print("Environment added.")


@ndeploy.command()
@click.option('-n', '--name', prompt='Environment name', help="Environment name.")
def delenv(**kwargs):
    ndeploy_core.remove_environment(kwargs['name'])
    print("Environment deleted.")


@click.option('-f', '--file_url', prompt='App deployment file URL',
              help="App deployment file URL, ex.: git@myhost.com:myconfs/{group} master {name}.json.")
@click.option('-h', '--deploy_host', prompt='Deploy deploy_host', help="Deploy deploy_host.")
@click.option('-t', '--type', prompt='Provider type', help="Provider type.",
              type=click.Choice(provider_repository.get_available_providers().keys()))
@click.option('-n', '--name', prompt='Environment name', help='Environment name.')
@ndeploy.command()
def updatenv(**kwargs):
    ndeploy_core.update_environment(name=kwargs['name'],
                                    type=kwargs['type'],
                                    deploy_host=kwargs['deploy_host'],
                                    app_deployment_file_url=kwargs['file_url'])
    print("Environment updated.")


@ndeploy.command()
def listenv(**kwargs):
    print(ndeploy_core.list_environments_as_str())


@ndeploy.command()
@click.option('-n', '--name', prompt='Environment name', help="Environment name.")
def keyenv(**kwargs):
    print(ndeploy_core.get_environment_key(kwargs['name']))


@ndeploy.command()
@click.option('-f', '--file', help="App deployment file")
@click.option('-g', '--group', help="Group name of project")
@click.option('-n', '--name', help="Project name")
@click.option('-e', '--environment', help="Environment name")
def deploy(**kwargs):
    try:
        ndeploy_core.deploy(**kwargs)
    except NDeployError as e:
        print(e)
        raise click.Abort()
    except Exception as e:
        print(e)
        raise click.Abort()


@ndeploy.command()
@click.option('-f', '--file', help="App deployment file")
@click.option('-g', '--group', help="Group name of project.", prompt="App group")
@click.option('-n', '--name', help="Name project.", prompt="App name")
@click.option('-e', '--environment', help="Environment configured.", prompt="Environment name")
def undeploy(**kwargs):
    ndeploy_core.undeploy(**kwargs)


if __name__ == '__main__':
    ndeploy()
