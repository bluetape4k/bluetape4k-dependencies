# latest-stable 후보 catalog의 과거 입력 검증

## 배경

Issue #272에서 latest-stable 검증기는 `candidate.catalog-sha256`을 현재
`gradle/libs.versions.toml`의 바이트 해시와 직접 비교하고 있었다. 버전 변경 기록의 후보
catalog는 `2026-10-18-issue-1832-amqp-client-candidate-receipt.json`이 가리키는
`content-commit` `bd3c06ec52e2a075a54ce62ff7790956477c5863`에서 복원할 수 있지만,
현재 catalog는 이후 변경되어 두 해시가 다른 상태였다.

당시 후보 catalog의 SHA-256은
`32887e9060e334600d3ff623ba60bd17fb732f45894d29e0f4a2f1b96924af8b`이고, 현재
catalog의 SHA-256은
`11255a5e195a2e66574559fff4568e4551f5b58ab89c68fabeffa2197e331f30`이다.
`candidate-validation-evidence.sha256`의
`86b72e90a8c64df73b3584be1ed40086e496f7fcc2d47e865af856b66a63bbff`는 검증 기록 파일을
확인하는 별도 해시다.

## 결정 또는 발견

- 현재 catalog sidecar는 현재 파일 바이트의 무결성을 검증한다.
- `candidate.catalog-sha256`은 과거 후보 catalog 바이트를 식별한다.
- `candidate-validation-evidence`는 검증 기록 파일을 식별하고, 그 안의
  `catalog.content-commit`은 후보 catalog를 복원할 변경할 수 없는 Git commit을 지정한다.
- 검증 기록 SHA와 내부 catalog SHA를 확인한 뒤, 해당 commit에서
  `gradle/libs.versions.toml`을 읽어 후보 해시를 다시 계산해야 한다.
- 버전 변경 기록의 `delta[].after`는 현재 작업 트리가 아니라 복원한 후보 catalog에서
  비교해야 한다.

두 해시를 같게 강제하면 후보를 만든 뒤 catalog를 변경한 정상 이력이 깨진다.
반대로 검증 기록의 commit 포인터만 믿으면 다른 catalog를 가리키는 오류를 놓칠 수
있으므로 복원한 파일 바이트까지 해시로 확인한다.

## 결과

`verify-latest-stable-resolved-graphs.py`는 현재 catalog를 sidecar와 비교하고,
후보 catalog는 검증 기록이 가리키는 전체 commit SHA에서 복원하도록 분리했다. 해당
값이 실제 commit 객체인지 확인한 뒤 파일 바이트를 다시 해시한다. 회귀 테스트는
현재 해시와 후보 해시가 다른 경우 통과하고, sidecar 불일치와 잘못된 과거 commit
포인터를 실패시킨다.

## 검증

- `python3 -m unittest tests/test_verify_latest_stable_resolved_graphs.py`
- `python3 -m py_compile scripts/verify-latest-stable-resolved-graphs.py tests/test_verify_latest_stable_resolved_graphs.py`
- 실제 변경 기록과 검증 기록을 대상으로 후보 commit 복원 및 현재 sidecar 검증을 수행했다.

## 향후 지침

과거 후보 증거와 현재 작업 트리 무결성 증거는 서로 다른 시점을 나타낸다. 한 시점의
해시를 다른 시점의 파일에 대입하지 말고, 검증 기록이 지정한 변경 불가 commit에서
원본 바이트를 복원해 검증한다. 후보 검증 기록을 교체하거나 다시 만들 때는 변경 기록이
보관한 검증 기록 SHA와 `catalog.content-commit`을 함께 갱신하고, 회귀 테스트에서 두
시점의 catalog 해시가 실제로 다른 사례를 유지한다.
