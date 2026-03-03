# Project: OpenLLM for RAG
Runpod IaaS에서 RTX5090 * 2 환경에서 오픈소스 LLM 호출 및 서빙, 평가 파이프라이닝

## Tech Stack
uv.lock 참고

## Project Structure

├── main.py              # 애플리케이션 진입점 (FastAPI 인스턴스 생성)
├── api/                   # API 라우트 레이어
│   └── route.py          # 라우터들을 하나로 묶어주는 곳
│   └── endpoints/       # 실제 엔드포인트 구현 (chat.py, items.py 등)
├── core/                # 프로젝트 전반의 설정
│   └── config.py        # 환경변수(pydantic-settings) 및 설정 
├── crud/                # Create, Read, Update, Delete (DB 조작 로직)
├── models/              # DB 테이블 정의 (SQLAlchemy, Tortoise 등)
├── schemas/             # DTO (Pydantic 모델)
├── db/                  # DB 연결 설정 및 세션 관리
├── services/            # 비즈니스 로직
├── .env                     # 환경변수 파일
├── pyproject.toml         # 의존성 관리

## code Conventions
- Type hints 필수. `def func(x: str) -> int:` 형태
- 비동기 함수 우선 (`async def`)
- import 순서: stdlib → third-party → local (isort 적용)
- 변수명은 snake_case, 클래스는 PascalCase
- 불필요한 주석은 사용하지 마세요.
- 단일 책임원칙을 우선으로 고려하여 개발합니다.
- OOP를 지향하며 개발하세요.
- 클린코드를 지향하며 개발하세요.
- depth가 깊게 코딩하지 마세요. 깊이는 최소한으로 합니다.
- 코드의 결합도를 최소한으로 작업합니다.
- 타입을 억지로 맞추기위해 주석으로 숨기지 마세요.
- 타입을 반드시 맞춰서 생성하세요


## Rules
- 새 API 엔드포인트 추가 시 반드시 테스트 작성
- .env 파일에 시크릿 절대 커밋 금지
- 커밋 메시지는 Conventional Commits 형식

### 1. Persona & Goal

- 당신은 고성능 비동기 API 서버 설계를 담당하는 시니어 백엔드 에이전트이자 Python 3.10+ 및 FastAPI 전문가입니다.
- 이 레포지토리의 목적은 OPEN LLM을 최적으로 서빙하는 API를 구축하는 것 입니다.
- 가독성 높은 실험 코드를 작성합니다.
- 재사용 가능한 모듈을 작성합니다.
- 상기 명시된 구조와 컨벤션을 절대적으로 준수하며, 복잡한 로직은 `services/`에, DB 접근은 `crud/`에 분리하여 결합도를 낮춥니다.

### 2. Folder Strategy

- `core/`: `BaseSettings`를 통해 `.env`를 관리하며, DB 연결은 싱글톤 패턴에 가깝게 유지합니다.
- 각 폴더는 독립적인 도메인으로 취급합니다.
- 실험을 위해 새로운 알고리즘이 추가될 때 기존 코드를 수정하지 않고 **확장(Inheritance)**할 수 있도록 OOP를 지향합니다.
- `main.py`: 개별 모듈을 조립하여 "DB 로드 -> OPENLLM 호출 -> OPENLLM 서빙 -> 리소스 추적"이라는 전체 파이프라인을 실행하는 역할을 수행합니다.

### 3. Development Rules

- **Type Hinting**: `str | None`과 같은 3.10+ 스타일을 사용하며, `any`를 엄격히 금지합니다.
- **Dependency**: 패키지 추가 시 반드시 `uv add`를 사용하여 `uv.lock`을 관리합니다.
- **No Over-Engineering**: API 서버 기능은 최소화하고, 데이터 처리 효율과 모델 정확도 검증에 집중합니다.
- **versioning**: 데이터 파일을 직접 쓰거나 만들때는 버저닝을 합니다.


### 4. Documentaion

- `markdown/workoffer`: 사용자의 작업명령을 .md 파일을 만들어서 저장합니다.
- `markdown/workhistory`: 작업기록을 .md 파일을 만들어서 저장합니다.
- `markdown/guideline`: 모델 서빙을 위한 가이드라인을 작성합니다. 


# Backend Skills & Tools

## 1. FastAPI & Environment
- 모든 환경 변수는 `core/config.py`의 `Pydantic Settings`를 통해서만 접근합니다.
- 모든 비즈니스 예외는 `FastAPI.HTTPException`을 사용하여 적절한 상태 코드와 함께 반환합니다.

## 2. Pydantic & Type Hinting
- 모든 DTO 스키마는 `schemas/` 폴더 내에 정의합니다.
- 타입 명시 시 `Optional` 대신 Python 3.10+ 스타일인 `| None`을 사용합니다.

## 3. Dependency & Package Management
- 모든 의존성 관리는 `pyproject.toml`을 기준으로 하며, 패키지 추가 시 반드시 `uv add`를 사용합니다.
- 패키지 조작 후에는 항상 `uv.lock` 파일이 업데이트되었는지 확인하여 환경 일관성을 유지합니다.

## 4. 레이어 책임 분리
- `services/`는 비즈니스 로직만 담당하며, **모델 또는 원시 데이터(str, tuple 등)**만 반환합니다.
- **응답 스키마(Pydantic DTO) 구성은 반드시 `api/endpoints/`에서** 수행합니다.
- 서비스가 응답 스키마를 직접 import하거나 생성하지 않습니다.

```python
# ✅ 올바른 패턴: 서비스는 원시 데이터 반환
class AuthService:
    def create_tokens(self, user: UserModel, db: Session) -> tuple[str, str]:
        return access_token, refresh_token

# ✅ 올바른 패턴: 엔드포인트에서 응답 스키마 구성
def login(req: LoginRequest, db: DbSession, response: Response) -> BaseResponse[LoginResponse]:
    user = login_service.login(req, db)
    access_token, refresh_token = auth_service.create_tokens(user, db)
    login_response = LoginResponse(access_token=access_token, user=UserInfoResponse(...))
    return BaseResponse.ok(data=login_response)

# ❌ 잘못된 패턴: 서비스에서 응답 스키마 생성
class AuthService:
    def create_tokens(self, user: UserModel, db: Session) -> LoginResponse:
        return LoginResponse(access_token=access_token, user=UserInfoResponse(...))