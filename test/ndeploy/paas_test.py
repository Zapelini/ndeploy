import json
import os
import unittest

from ndeploy.model import App, Environment
from ndeploy.paas import AbstractPaas, service


class MockPaas(AbstractPaas):

    def __init__(self):
        self.result = {}

    def deploy_by_image(self, app):
        self.result['deploy_method'] = 'by_image'
        self.result['app'] = app

    def deploy_by_git_push(self, app):
        self.result['deploy_method'] = 'by_git_push'
        self.result['app'] = app

    def load_app(self, name):
        return "http://%s.com" % (name)

    @service("postgres")
    def load_postgres(self, resource):
        return "postgres://user:senha@localhost:5432/%s" % (resource)


class AssembleModelTest(unittest.TestCase):
    """
    Test assemble models.
    """

    def test_deploy_app(self):

        os.environ['BLA'] = 'teste'

        file = os.path.join(os.path.dirname(__file__), '../resources', 'deployed_app.json')
        json_data = open(file).read()

        data = json.loads(json_data)
        app = App(**data)

        mock_paas = MockPaas()
        mock_paas.deploy(app, Environment(name='dev', host='localhost', type='mock'))

        env_vars = dict(
            APP_ENV="Development",
            TESTE="Oi teste",
            APP_NOTIFICATION_URL="http://notification.com",
            DATABASE_URL="postgres://user:senha@localhost:5432/teste",
            URL_OPEN_ID="http://www.teste.com")

        self.assertEqual(app.env_vars, env_vars)
