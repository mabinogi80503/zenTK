from abc import ABCMeta, abstractmethod


class BasicAuthenticator(object, metaclass=ABCMeta):
    @abstractmethod
    def login(self):
        raise NotImplementedError
