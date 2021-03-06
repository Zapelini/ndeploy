import hashlib
import json

from ndeploy.provider import AbstractProvider
import socket
from ndeploy.exception import NDeployError
import timeout_decorator


class OpenShiftNotLoggedError(NDeployError):
    def __str__(self):
        return "Could not continue deploying because openshift command line is not logged. " \
               "You have to execute 'oc login' before executing ndeploy."


class OpenShiftNameTooLongError(NDeployError):
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return "The app deploy name {} is too long for openshift to handle.\n" \
               "Use a name shorter than 24 characteres in App deploy_name field."\
            .format(self.name)


class OpenshiftProvider(AbstractProvider):
    """
    Openshift deployment implementation
    """

    __type__ = 'openshift'

    def __init__(self):
        super().__init__()
        self.app = None
        self.env = None

    def deploy_by_image(self, app, env):
        """
        Deploys the app passing an image. The app should have an image field.

        Args:
            app (App): the app to deploy.
            env (Environment): the environment to deploy.

        """
        assert app.image != ""

        self.app = app
        self.env = env

        self.openshift_deploy(self.create_app_by_image)

    def deploy_by_git_push(self, app, env):
        """
        Deploys the app by source. The app should have a repository field

        Args:
            app: the App to deploy
            env: the Environment to deploy
        """
        assert app.repository != ""

        self.app = app
        self.env = env

        self.openshift_deploy(self.create_app_by_source)

    def undeploy(self, app, env):
        """
        Undeploys the app in the environment.

        Args:
            app (App): app object
            env (Environment): environment object

        """
        self.app = app
        self.env = env

        print("Undeploying app {app_name} from environment {env_name}"
              .format(app_name=self.app.deploy_name, env_name=self.env.name))
        self.openshift_exec("delete all -l app={app_name}"
                            .format(app_name=app.deploy_name))
        print("Undeploy done.")

    def openshift_deploy(self, create_app_callback):
        """
        Do all the flow needed to deploy an app on openshift.
        The real deploy should be made by the 'create_app_callback' function

        Args:
            create_app_callback: function that makes the deploy
                            signature: fn()
        """
        self.validate_deploy_name()
        self.handle_login()
        self.configure_project()
        create_app_callback()
        self.expose_service()

    def create_app_by_image(self):
        """
        Creates the app in the environment by image

        """
        print("...Deploying app {app_name} by image\n...Image url: {image}"
              .format(app_name=self.app.deploy_name, image=self.app.image))

        self.create_app_if_does_not_exist(True)

        current_revision = self.get_app_deploy_revision()

        # those commands may trigger another deployment if some var or image has changed
        self.import_image()
        self.update_env_vars()

        # last chance to trigger a new deployment..
        # if new-app and env dc didn't triggered we need to force a new
        # deploy
        if current_revision == self.get_app_deploy_revision():
            self.force_deploy()

    def import_image(self):
        """
        Imports the app image in openshift registry.
        Updates the openshift image stream for current app

        """
        image_stream_uri = "{app_name}:{image_tag}"\
            .format(app_name=self.app.deploy_name, image_tag=self.get_image_tag())
        print("...Importing image {}".format(image_stream_uri))
        self.openshift_exec("import-image {}".format(image_stream_uri))

    def force_deploy(self):
        """
        Forces a new deploy on openshift

        """
        print("...Nothing changes, forcing a new deploy")
        self.openshift_exec("deploy {app_name} --latest"
                            .format(app_name=self.app.deploy_name))

    def update_env_vars(self):
        """
        Updates the environments variables for the app in the project

        """
        print("...Configuring environment variables")
        env_vars = self.prepare_env_vars(self.app.env_vars)
        self.openshift_exec("env dc/{app_name} {env_vars}"
                            .format(app_name=self.app.deploy_name,
                                    env_vars=env_vars))

    def create_app_by_source(self):
        """
        Creates the app in the environment by source

        """
        print("...Deploying app {app_name} by source\nRepository: {repo}"
              .format(app_name=self.app.deploy_name, repo=self.app.repository))

        self.create_app_if_does_not_exist(False)

        project = self.get_openshift_area_name()
        self.shell_exec.execute_system(
            "oc patch bc %s -p "
            "'{\"spec\":{\"source\":{\"sourceSecret\":{\"name\":\"scmsecret\"}}}}'"
            " -n %s" % (self.app.deploy_name, project))

        self.openshift_exec("start-build {app_name} --follow"
                            .format(app_name=self.app.deploy_name))
        self.openshift_exec("env dc/{app_name} {env_vars}"
                            .format(app_name=self.app.deploy_name,
                                    env_vars=self.prepare_env_vars(self.app.env_vars)))

    def load_service(self, name, resource):
        if name == 'postgres':
            return self._load_postgres(resource)

    def app_url(self, name):
        return "http://%s.com" % name

    def handle_login(self):
        """
        Verifies if the oc client is logged. Raise OpenShiftNotLoggedError
        if not logged
        """
        print("...Verifying if oc client is logged......", end="")
        if not self.is_logged():
            # raising exception for now. We need to think in a better solution for this
            raise OpenShiftNotLoggedError
            # self.login()
        print("...[Ok]")

    def expose_service(self):
        """
        Expose the openshift route if it doesn't exist.
        The created route will have the name of the app

        """
        default_domain = self.get_openshift_app_host()
        domains = [default_domain] + self.app.domains
        self._expose_service_domains(domains)
        print("[Ok]")

    def _expose_service_domains(self, domains):
        """
        Expose the openshift extra route if it doesn't exist.
        Args:
            domains: Domains exposed to app

        """
        for domain in domains:
            if not self.route_exist(domain):
                print("...Create route to domain: {}....".format(domain))
                hash_domain = self._generate_unique_id(domain)
                route_name = "{}-{}".format(self.app.deploy_name, hash_domain)
                self.create_route(route_name, domain)

    @staticmethod
    def _generate_unique_id(value):
        """
        Generate md5 sum from a value

        Args:
            value (str): string to generate md5 sum
        Returns:
            string with value md5 sum
        """
        return hashlib.md5(value.encode("utf-8")).hexdigest()[:6]

    def create_route(self, route_name, route):
        """
        Creates the route for the app.
        The route name will be the app deploy name.

        Args:
            route_name (str): the route name
            route (str): route to expose in openshift

        """
        cmd = "expose service/{app_name} --hostname={hostname} --name={name}".format(app_name=self.app.deploy_name,
                                                                                     hostname=route,
                                                                                     name=route_name)
        print("\t...Creating app route to {}: {}".format(self.app.deploy_name, cmd))
        self.openshift_exec(cmd)

        print("\t...Patching route to enable tls...", end="")
        patch_cmd = "patch route %s -p '{\"spec\": {\"tls\": {\"termination\": \"edge\", " \
                    "\"insecureEdgeTerminationPolicy\": \"Redirect\"}}}'" % route_name

        self.openshift_exec(patch_cmd)
        print("[Ok]")

    def get_openshift_app_host(self):
        """
        Returns the host where app will be deployed

        Returns:
            the host url of the app
        """
        return "%s-%s.%s" % (self.app.deploy_name, self.get_openshift_area_name(), self.env.deploy_host)

    def configure_project(self):
        """
        Configure the openshift project where the app will be deployed.
        Creates the project and the secret for the scm if they doesn't exist

        """
        self.create_project_if_does_not_exist()
        self.create_secret_if_does_not_exist()
        self.add_annotations_in_project()

    def create_project(self, project):
        """
        Creates a new project on openshift

        Args:
            project: the project name
        """
        self.openshift_exec("new-project " + project, False)

    def create_project_if_does_not_exist(self):
        """
        Verifies if the project exists and creates a new project if it doesn't exist

        """
        project = self.get_openshift_area_name()
        print("...Verifying if project {} exists........."
              .format(project), end="")
        if not self.project_exist(project):
            print("No, creating project.........", end="")
            self.create_project(project)
            print("[Ok]")
        else:
            print("[Ok]")

    def create_secret(self, secret):
        """
        Creates a new secret with the default ssh key of current user (located at
        $HOME/.ssh/id_rsa) to allow openshift to access the git repo.
        The secret will be create with 'scmsecret' as name

        Args:
            secret (str): secret name

        """
        project = self.get_openshift_area_name()
        # temos que executar com os.system por causa do parâmatro ssh-privatekey.
        # Por algum motivo não funciona com subprocess
        self.shell_exec.execute_system("oc secrets new {secret} "
                                       "ssh-privatekey=$HOME/.ssh/id_rsa -n {project}"
                                       .format(project=project, secret=secret))
        self.openshift_exec("secrets add serviceaccount/builder secrets/{secret}"
                            .format(secret=secret))

    def create_secret_if_does_not_exist(self):
        """
        Creates a secret if it doesn't exist.
        The secret will be named 'scmsecret'

        """
        print("...Verifying if secret scmsecret exists.........", end="")
        if not self.secret_exist("scmsecret"):
            print("No, will create........", end="")
            self.create_secret("scmsecret")
            print("[Ok]")
        else:
            print("[Ok]")

    def add_annotations_in_project(self):
        """
        Add openshift annotations in project

        """
        deployment_config = {
            "metadata": {"annotations": {"openshift.io/node-selector": "region={}".format(self.env.name)}}
        }
        self.openshift_exec("patch namespace {project_name} --patch '{dc_json}'".format(
            project_name=self.get_openshift_area_name(), dc_json=json.dumps(deployment_config)))

    def app_exist(self, app):
        """
        Verifies if app exist.
        We are verifying only if a deployment config exists.

        Args:
            app (App): the app object

        Returns:
            True if exists, False otherwise

        """
        return not self.oc_return_error("get dc/{app_name}"
                                        .format(app_name=app.deploy_name))

    def create_app(self, app, by_image):
        """
        Creates an app on openshift `project`

        Args:
            app (App): app object
            by_image (bool): True if the app will be created by image,
                False if by source

        """
        if by_image:
            env_vars = self.prepare_env_vars(self.app.env_vars)
            self.openshift_exec("new-app {image_url} --name {app_name} --env={env_vars}"
                                .format(image_url=app.image,
                                        app_name=app.deploy_name,
                                        env_vars=env_vars))
        else:
            self.openshift_exec("new-app {source_repo} --name {app_name}"
                                .format(source_repo=app.repository,
                                        app_name=app.deploy_name))

    def create_app_if_does_not_exist(self, by_image):
        """
        Creates an app on openshift if it does not exist
        Args:
            by_image (bool): True if needs to create by image,
                False if by source

        """
        print("...Verifying if app {} exists........."
              .format(self.app.deploy_name), end="")
        if not self.app_exist(self.app):
            print("No, will create..........", end="")
            self.create_app(self.app, by_image)
            print("[Ok]")
        else:
            print("[Ok]")

    def project_exist(self, project):
        """
        Verifies if the project exists

        Args:
            project: the project name

        Returns:
            True if exists, False otherwise
        """
        return not self.oc_return_error("get project {project}"
                                        .format(project=project), False)

    def secret_exist(self, secret):
        """
        Verifies if the secret exists

        Args:
            secret: the secret to verify

        Returns:
            True if exists, False otherwise
        """
        return not self.oc_return_error("get secret {secret_name}"
                                        .format(secret_name=secret))

    def route_exist(self, route):
        """
        Verifies if the route exists in the current project

        Args:
            route: the route to verify

        Returns:
            True if exists, False otherwise
        """
        err, out = self.openshift_exec("get routes", output="json")
        try:
            routes_in_os = json.loads(out)
            for route_os in routes_in_os["items"]:
                if route_os["spec"]["to"]["name"] == self.app.deploy_name and route_os["spec"]["host"] == route:
                    return True

            return False

        except json.decoder.JSONDecodeError as e:
            print("...{}".format(err))
            print("...Error checking route existing: {}".format(e))
            return False

    def openshift_exec(self, oc_cmd, append_project=True, output=''):
        """
        Exec a command with oc client.
        If append_project the command will have the project option at the end.
        Ex:
            openshift_exec('get routes', True)

            will execute > oc get routes -n project_name

            openshift_exec('get routes', False)

            will execute > oc get routes

        Args:
            oc_cmd: oc command to execute
            append_project: if True will append the -n 'project_name'
                at end of the command
            output: output formats at Openshift (json, yaml), by default bash table

        Returns:
            tuple (err, out) containing response from ShellExec.execute_program

        """
        project = self.get_openshift_area_name()
        return self.shell_exec.execute_program(
            "oc {cmd} {project} {output}"
            .format(cmd=oc_cmd, project="-n " + project if append_project != "" else "",
                    output="-o {}".format(output) if output else ""), True)

    def oc_return_error(self, cmd, append_project=True):
        """
        Executes a oc command and verifies if execution returned error
        Args:
            cmd: oc command
            append_project: if True will append -n [project_name] at the of the cmd

        Returns:
            err: err != None if returned error
        """
        err, out = self.openshift_exec(cmd, append_project)
        return err

    def is_logged(self):
        """
        Verifies if oc client is logged

        Returns:
            True if logged, False otherwise
        """
        cmd = "oc whoami"
        try:
            err, out = self.shell_exec.execute_program_with_timeout(cmd, True)
            if "system:anonymous" in err or "provide credentials" in err:
                return False
            else:
                return True
        except timeout_decorator.TimeoutError:
            return False

    def login(self):
        """
        Login at openshift host.

        """
        # login has to be by IP because of teh https/ssl signed certificate
        ip = socket.gethostbyname(self.env.deploy_host)
        self.shell_exec.execute_program("oc login https://%s:8443" % ip)

    @staticmethod
    def _load_postgres(self, resource):
        return "postgres://user:senha@localhost:5432/%s" % resource

    def get_openshift_area_name(self):
        """
        Returns the current openshift project name(it must be lowercase, because openshift cant handle upper
        case namespaces)
        By now the project name will be the env.name. In sgslebs/ndeploy the project
        name will be the name of the user executing ndeploy
        or 'area' option passed in command line.

        Returns:
            the current openshift project name
        """
        return str(self.app.group).lower()
        # sgslebs/ndeploy implementation
        # default = getpass.getuser()
        # return options.get("area", default).replace(".", "")

    def validate_deploy_name(self):
        """
        Verifies if app deploy name is shorter than 24 characteres
         (OpenShift limitation)

        Returns:
            bool: True if is valid, False otherwise

        """
        print("...Validating deploy name.........", end="")
        if len(self.app.deploy_name) > 24:
            raise OpenShiftNameTooLongError(self.app.deploy_name)
        print("[Ok]")

    def get_app_deploy_revision(self):
        """
        Returns the app deployment revision.

        Returns:
            int: revision number

        """
        err, out = self.openshift_exec("get dc/{app_name}".format(app_name=self.app.deploy_name),
                                       output="json")

        if err:
            return 0

        deployment_config = json.loads(out)
        revision = deployment_config["status"].get("latestVersion", 0)
        return revision
