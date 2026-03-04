from pydantic import BaseModel


class TestRequest(BaseModel):
    base_url: str = "http://localhost:8000"


class TestResultResponse(BaseModel):
    name: str
    passed: bool
    latency_s: float | None = None
    detail: dict | None = None
    error: str | None = None


class TestSuiteResponse(BaseModel):
    base_url: str
    model: str | None = None
    total: int
    passed: int
    failed: int
    results: list[TestResultResponse]
