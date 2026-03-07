class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "BAD_REQUEST") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ExternalDataError(AppError):
    def __init__(self, message: str = "外部基金数据获取失败") -> None:
        super().__init__(message=message, status_code=502, code="EXTERNAL_DATA_ERROR")


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message=message, status_code=404, code="NOT_FOUND")
