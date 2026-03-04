from pydantic import BaseModel


class ValidationRequest(BaseModel):
    base_url: str = "http://localhost:8000"
    csv_path: str | None = None
    sample_size: int = 0


class TypeScoreResponse(BaseModel):
    count: int
    correctness: float
    relevance: float
    completeness: float
    average: float


class OverallScoreResponse(BaseModel):
    correctness: float
    relevance: float
    completeness: float
    average: float


class ValidationSummaryResponse(BaseModel):
    total: int
    valid: int
    overall: OverallScoreResponse | None = None
    by_type: dict[str, TypeScoreResponse]
    results_csv_path: str | None = None
