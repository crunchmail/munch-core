from rest_framework.exceptions import APIException


class InvalidSubmitedData(ValueError, APIException):
    status_code = 500
    default_detail = 'Some data is invalid'

    @property
    def detail(self):
        return self.__str__()


class WrongHTML(InvalidSubmitedData):
    def __init__(self, parent_e):
        self._e = parent_e
        super().__init__()

    def __str__(self):
        return 'Le HTML soumis est invalide : "{}"'.format(str(self._e))
