class IncompleteCopy(Exception):
    def __init__(self, message: str, source, destination):
        super().__init__(message)
        self.source = source
        self.destination = destination
        failures: dict[str, Exception] = {}
