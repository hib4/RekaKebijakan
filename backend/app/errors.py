class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class ResourceNotFound(ApiError):
    def __init__(self):
        super().__init__(404, "not_found", "Sumber daya tidak ditemukan")


class StageConflict(ApiError):
    def __init__(self, message: str):
        super().__init__(409, "stage_locked", message)


class InvalidControl(ApiError):
    def __init__(self, message: str):
        super().__init__(409, "invalid_control", message)


class UnsupportedDocument(ApiError):
    def __init__(self, message: str):
        super().__init__(422, "unsupported_document", message)


class AuthenticationRequired(ApiError):
    def __init__(self, message: str = "Autentikasi diperlukan"):
        super().__init__(401, "unauthorized", message)


class EmailConflict(ApiError):
    def __init__(self):
        super().__init__(409, "email_conflict", "Alamat email sudah terdaftar")
