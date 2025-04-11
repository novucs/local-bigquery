class NotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"NotFoundError: {self.message}"


class AlreadyExistsError(Exception):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"AlreadyExistsError: {self.message}"
