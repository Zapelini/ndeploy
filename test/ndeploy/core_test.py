import json
import os
import unittest

import ndeploy.environment_repository
from ndeploy import environment_repository, core
from ndeploy.model import Environment


class EnvironmentTest(unittest.TestCase):
    """
    Test ndeploy functions.
    """

    def test_add_enviroments(self):

        environment_repository.DIR_ENVS = os.environ['HOME'] + "/.ndeploy-tmp"
        environment_repository.FILE_ENVS = ndeploy.environment_repository.DIR_ENVS + "/environments.json"

        if os.path.isdir(environment_repository.DIR_ENVS):
            os.removedirs(ndeploy.environment_repository.DIR_ENVS)

        core.add_environment(type="dokku",
            name="integrated-dev",
            host="integrated-dev.nexxera.com",
            conf_app_file="git@gitlab.nexxera.com:group/my-app.git")

        file = os.path.join(os.path.dirname(__file__), '../resources', 'model_environments.json')
        json_data_expected = open(file).read()
        data_expected = json.loads(json_data_expected)

        json_data = open(ndeploy.environment_repository.FILE_ENVS).read()
        data = json.loads(json_data)

        os.remove(ndeploy.environment_repository.FILE_ENVS)

        self.assertEqual(data, data_expected)


    def test_remove_enviroments(self):

        environment_repository.DIR_ENVS = os.path.join(os.path.dirname(__file__), '../resources')
        environment_repository.FILE_ENVS = ndeploy.environment_repository.DIR_ENVS + "/environments.json"

        environments = core.list_environments()

        self.assertEqual(len(environments), 2)


    def test_remove_enviroments(self):
        environment_repository.DIR_ENVS = os.environ['HOME'] + "/.ndeploy-tmp"
        environment_repository.FILE_ENVS = ndeploy.environment_repository.DIR_ENVS + "/environments.json"

        if os.path.isdir(environment_repository.DIR_ENVS):
            os.removedirs(ndeploy.environment_repository.DIR_ENVS)

        core.add_environment(type="dokku",
            name="integrated-dev",
            host="integrated-dev.nexxera.com",
            conf_app_file="git@gitlab.nexxera.com:group/my-app.git")

        core.add_environment(type="openshift",
            name="qa",
            host="qa.nexxera.com",
            conf_app_file="git@gitlab.nexxera.com:group/my-app.git")

        core.remove_environment("qa")

        environments = core.list_environments()

        os.remove(ndeploy.environment_repository.FILE_ENVS)
        self.assertEqual(len(environments), 1)
