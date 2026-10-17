from app.classes.web.base_api_handler import BaseApiHandler


class Refused(Exception):
    """An error answer: the HTTP status, the error name and a message."""

    def __init__(self, status: int, error: str, message: str):
        super().__init__(message)
        self.status = status
        self.error = error

    def send(self, handler: BaseApiHandler) -> None:
        handler.finish_json(
            self.status,
            {"status": "error", "error": self.error, "error_data": str(self)},
        )
