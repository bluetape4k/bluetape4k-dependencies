# 카탈로그 후보와 서명 검증 이력의 ref 분리

## 문제와 놓친 가정

Kotlin 2.4.20 전환 후보는 로컬에서 185개 alias와 189개 publication POM을
검증했다. 그러나 [PR #249의 첫 CI](https://github.com/bluetape4k/bluetape4k-dependencies/actions/runs/34237564193)는
과거 서명 검증용 Exposed `d742a129`를 checkout해 184개 alias와 188개 POM을
검사했다. Python 회귀 검사가 통과해도 카탈로그 생성 검사는 실패했다.

로컬 후보의 POM 검증 성공이 hosted CI에서도 같은 모듈 집합을 검증한다는 가정이
잘못됐다. 두 실행의 publisher 이름만 비교하고 commit과 모듈 목록을 비교하지 않은
검토 누락이었다. POM 작업의 성공도 이전 188개 모델에 대한 결과였으므로 최신
189개 모델의 검증으로 인정할 수 없다.

## 결정과 적용 범위

- `config/publishing-signing-repository-refs.json`과 기존 서명 검증 checkout은
  과거 서명 증거를 재현하는 용도로 유지한다.
- `config/catalog-publisher-repository-refs.json`은 카탈로그 생성과 POM 검증의
  publisher commit을 고정한다. 같은 `checkout-catalog-publishers.sh`를 두 CI 작업이
  사용하며, checkout 위치는 `$RUNNER_TEMP/catalog-workspace`로 분리한다.
- 기존 checkout을 전환하거나 덮어쓰지 않는다. 입력 목록과 SHA를 먼저 검증하고,
  각 checkout의 commit 및 clean 상태를 확인한 후 검증을 시작한다.
- 카탈로그에서 최신 모듈을 제거해 과거 서명 목록에 맞추거나, 과거 서명 receipt를
  최신 모듈 검증 증거로 다시 쓰는 방법은 채택하지 않는다.
- 기존 #242/#243 계획의 publication job용 서명 ref 재사용 설명은 이 변경으로
  대체한다. 서명 source·receipt 계약 자체는 변경하지 않는다.

## 검증과 재발 방지

`tests/test_catalog_publisher_checkout.py`는 실제 Git fixture로 다른 commit의 서명
checkout과 사용자 파일 보존, 불변 SHA 선택, 잘못된 목록·ref 거부, 기존 목적지
보존을 검사한다. `tests/test_ci_catalog_governance.py`는 카탈로그와 POM 작업이
동일한 checkout 도구와 디렉터리를 사용하고 서명 ref를 다시 참조하지 않는지 검사한다.

다음 카탈로그 전환에서는 버전·checksum과 함께 publisher commit 목록을 갱신한다.
로컬과 hosted 실행의 commit, alias 수, POM 수, Maven 모델 수를 각각 대조한다.
서명 이력 검증 성공, 카탈로그 생성 성공, POM 검증 성공은 별도 증거로 기록한다.
현재 후보 전달이 전체 소비자 CI·배포·Dependabot 재수집 완료를 뜻하지는 않는다.
