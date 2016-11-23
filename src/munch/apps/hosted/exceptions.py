from munch.apps.campaigns.exceptions import InvalidSubmitedData


class TooBigMedia(InvalidSubmitedData):
    def __init__(self, name, max_size):
        self.name = name
        self.max_size = max_size
        super().__init__()

    def __str__(self):
        return 'Le fichier "{}" est trop gros (> {:.2}Mio)'.format(
            self.name, self.max_size / 1024 / 1024)


class InvalidMimeType(InvalidSubmitedData):
    def __init__(self, mime_type):
        self.mimetype = mime_type
        super().__init__()

    def __str__(self):
        return '"{}" n\'est pas un type mime supporté'.format(self.mimetype)
