"""Errors that the dashboard can show without hiding the cause."""


class BenchmarkError(Exception):
    """Base error for a failed benchmark step."""


class ModelLoadError(BenchmarkError):
    """The requested model could not be loaded. No other model is substituted."""


class UnsupportedLanguage(BenchmarkError):
    """The requested model does not support this language."""


class DatasetError(BenchmarkError):
    """A dataset could not be read. An empty list is not a successful load."""


class ValidationError(BenchmarkError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))
