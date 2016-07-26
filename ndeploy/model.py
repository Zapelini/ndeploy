"""
Models usados no processo de deploy.
"""

class Environment:
    """
    Model para os dados de Environment.
    """

    def __init__(self, type, name, host, conf_app_file=None):
        """
        Construtor
        Args:
            type: Tipo de ambiente, relacionado a ferramenta Paas a qual os dados do ambiente se refere, ex.: dokku, openshift, heroku, etc.
            name: Nome do Environment, ex.: dev, qa, stage, production, etc.
            host: Host de acesso a ferramenta Paas onde é realizado o deploy.
            conf_app_file: Template usado para baixar arquivo de configuração da aplicação a ser deployada.
        """
        self.type = type
        self.name = name
        self.host = host
        self.conf_app_file = conf_app_file


class App:
    """
    Model para os dados de um aplicação a ser deployada.
    """

    def __init__(self, name, deploy_name=None, repository=None, image=None, env_vars=None):
        """
        Construtor
        Args:
            name: Nome da aplicação.
            deploy_name: Nome de deploy da aplicação, quando informado a aplicação será deployada com esse nome, caso contrário será usado o "name"
            repository: Repositório git onde estão os fontes da aplicação. Se não informado será considerado que o repositório git é o repositório de execução.
            image: Imagem docker usada para deploy. Quando informada o deploy ocorre preferencialmente via imagem docker. Se não informado será considerado o "repository"
            env_vars: Variáveis de ambiente que devem ser aplicada no ambiente de deploy.
                É composta por um dicionário de dados no formato chave/valor, onde a chave é o nome da variável e valor o valor que deve estár aplicado na variável.
                O valor pode ser informado de alguma maneiras:
                - Valor explicito: String com valor fixo a ser aplicado na variável.
                - Composição com variável ambientes: No meio da String pode usar chaves referentes a outras variáveis de ambiente,
                    ex.: http://{EMAIL_USER}:{EMAIL_PASS}@host.com. Os valores EMAIL_USER e EMAIL_PASS serão substítuidos pelo valor real da variável de ambiente.
                - Uso de serviços: Pode-se informar no valor a necessidade do uso de um serviço especifíco, ex.: service:postgres ou service:postgres:mydb,
                    onde service indica que um serviço deve ser usado, postgres é o nome do serviço e mydb é o nome do resource a ser usado.
                - Uso de outras apps: Pode-se informar no valor a necessidade do uso de um link com outra aplicação, ex.: app:other-app,
                    onde app indica que um link com outra app deve ser usado, other-app é o nome da app que deve ser verificado a url para composição do link.
        """
        self.name = name
        self.deploy_name = deploy_name
        self.repository = repository
        self.image = image
        self.env_vars = env_vars