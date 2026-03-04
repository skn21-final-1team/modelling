from pydantic import BaseModel


class ModelPullRequest(BaseModel):
    model_id: str
    revision: str = "main"


class ModelPullResponse(BaseModel):
    model_id: str
    revision: str
    local_path: str
    status: str


class CachedModelResponse(BaseModel):
    model_id: str
    size_gb: float
    path: str
