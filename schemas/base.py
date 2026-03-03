from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: T | None = None
    message: str = ""

    @classmethod
    def ok(cls, data: T, message: str = "") -> "BaseResponse[T]":
        return cls(status="success", data=data, message=message)

    @classmethod
    def error(cls, message: str) -> "BaseResponse[None]":
        return BaseResponse(status="error", data=None, message=message)
