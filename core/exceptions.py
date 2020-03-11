class APIException(Exception):
    def __init__(self, reason):
        super().__init__(reason)


class APICallFailedException(APIException):
    pass


class LoginFailException(APIException):
    pass
