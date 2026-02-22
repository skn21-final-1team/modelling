1. runpod 플랫폼에서 단일 pod으로 openllm을 서빙하고 테스트하기위한 이미지를 빌드할거야.
해당 이미지 경로 @docker/testing/Dockerfile
해당된 이미지에는 model pulling(huggingface, hf_transfer, env.sh), model inference(tranfromer, ...), model server(vllm), model testing(python script files; ex: model-testing.py) 등이 포함되어야해. 또한 모두 uv.lock, pyproject.toml를 통한 의존성 설치를 할거야.

2. openllm의 성능을 테스트할 가상데이터 혹은 합성데이터를 만들어줘. 필요한 데이터는 notebooklm 서비스에서의 웹소스추가처럼 url을 입력받으면 해당 url에 있는 정보들을 crawling해서 적재되었을때의 데이터야. 필요하다면 스크립트를 만들어서 직접 크롤링을 해도 돼. (절대 이미지에 셀레니움과 같은 크롤링 라이브러리를 포함시키지 마. 하지만 로컬에서의 크롤링은 가능해)

3. model