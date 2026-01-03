
from meta_classes.singleton_meta import SingletonMeta

import os
from dotenv import load_dotenv


class ServerConfig(metaclass = SingletonMeta):

    def __init__(self):
        if os.getenv('ENV') is None:  #only in local run the below
            load_dotenv()
        self.pat = os.getenv('GITLAB_ACCESS_TOKEN')
        self.project_list = os.getenv('GITLAB_PROJETCS').split(',')  #list of project ids

    def get_token(self):
        return self.pat
    
    def get_project_list(self):
        return self.project_list