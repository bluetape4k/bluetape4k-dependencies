# Snapshot consumer commit 집합을 CI artifact로 고정한다

## 상황

`CI`가 `develop`의 consumer를 검증한 뒤 `Publish Snapshot`이 각 저장소의
최신 `develop`을 다시 clone하고 있었다. 두 workflow 사이에 consumer가
전진하면 동일한 중앙 commit에서 검증하지 않은 상태를 Snapshot preflight가
읽는다. `34244837500`은 이 경계에서 `bluetape4k-projects`의 catalog ref가
CI에서 검증한 값과 달라져 publication 전에 실패했다.

## 잘못된 가정과 결정

- 잘못된 가정: `workflow_run`의 중앙 `head_sha`만 고정하면 downstream
  checkout도 CI와 같다고 볼 수 있다.
- 결정: CI의 검증 workspace에서 모든 required consumer의 clean HEAD와
  검증 대상 catalog ref를 `snapshot-consumer-inputs.json`에 기록한다.
  artifact에는 중앙 source commit, CI run ID, run attempt도 함께 저장한다.
- Snapshot은 triggering CI run의 artifact를 `actions: read` 권한으로
  다운로드하고, source commit과 run ID를 검증한 뒤 모든 consumer를
  manifest의 exact SHA에 detached checkout한다. candidate branch나
  `develop` fallback은 사용하지 않는다.

## 검증과 운영 경계

manifest가 없거나 inventory, source commit, run ID, SHA, settings/CI catalog
ref 일치 조건을 만족하지 않으면 Snapshot은 publication 전에 종료한다.
수동 dispatch는 임의 SHA를 받지 않고 재사용할 성공한 CI `ci_run_id`만 받는다.
merge, workflow dispatch, Maven Central publication은 이 repair의 검증과
분리된 후속 gate다.

## 재발 방지 규칙

`workflow_run` 기반 publication은 중앙 commit만이 아니라 선행 CI가 실제로
검증한 모든 외부 checkout의 immutable input을 artifact로 전달해야 한다.
다음 변경에서 consumer clone 로직을 수정할 때는 exact manifest 검증과
`git rev-parse HEAD` read-back을 함께 유지하고, artifact가 없으면
`develop`으로 조용히 대체하지 않는다.

## Publish job의 catalog history 경계

Publish job은 manifest의 중앙 source commit을 detached checkout한 뒤
preflight를 실행하므로, 중앙 저장소의 branch history에 포함되지 않은 pinned
catalog SHA를 자동으로 보유하지 않는다. CI와 Publish 양쪽에서
`GITHUB_SERVER_URL/GITHUB_REPOSITORY`를 직접 지정해 policy의 모든 catalog
ref를 fetch하고 `git rev-parse --verify`로 확인해야 한다. 이 fetch가 없으면
CI는 통과해도 Publish preflight가 `pinned snapshot catalog ref ... is missing`
으로 publication 전에 중단된다.

## DoD

- source commit과 CI run ID가 manifest에 포함된다.
- required consumer inventory가 manifest와 일치한다.
- Snapshot checkout은 manifest SHA만 사용하며 fallback branch가 없다.
- Python 회귀 테스트, shell checkout 테스트, workflow contract 테스트가
  이 경계를 고정한다.
