from fastapi import FastAPI, Depends
from pydantic import BaseModel
from core.database import get_db, init_db
from core.config import settings  # 설정 객체 임포트

app = FastAPI(
    title=settings.PROJECT_NAME,  # BaseSettings에서 가져온 프로젝트명
    debug=settings.DEBUG,
)


# --- Pydantic Schemas ---
class ProcessRequest(BaseModel):
    content_id: int
    raw_text: str


# --- API Endpoints ---
@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/config-check")
def get_config():
    # 설정이 잘 로드되었는지 확인하는 용도 (보안상 주의)
    return {"project_name": settings.PROJECT_NAME, "db_url": "configured!"}


@app.post("/process")
def process_task(payload: ProcessRequest, db=Depends(get_db)):
    return {"status": "success", "content_id": payload.content_id}
