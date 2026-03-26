---
title: README Design Spec
date: 2026-03-26
status: approved
---

# README Design Spec

## Overview
modelling 프로젝트의 README.md를 GitHub Flavored Markdown(GFM) 문법으로 작성한다.

## Approach
사용자 중심 README — Quick Start 우선, 기능별 사용법 중심 구성.

## Sections

1. **헤더** — 프로젝트명, 한줄 설명, tech stack 뱃지
2. **기능 개요** — 4대 기능 테이블 (Model Pulling, Testing, Validation, Monitoring)
3. **프로젝트 구조** — 디렉토리 트리 (핵심만)
4. **Quick Start** — env.sh, .env, 서버 실행
5. **CLI 사용법** — 4개 CLI 명령어 + 옵션 테이블
6. **API Endpoints** — 엔드포인트 테이블 + 요청/응답 예시
7. **Docker** — 3종 Pod 테이블 + 빌드 명령어
8. **환경 변수** — 주요 변수 테이블
9. **Dependencies** — 핵심 의존성 목록
10. **문서** — markdown/ 하위 문서 링크

## Constraints
- GFM 문법 전체 활용 (테이블, 체크박스, 코드 블록, 뱃지)
- 한국어 작성
- 실행 가능한 명령어 예시 포함
