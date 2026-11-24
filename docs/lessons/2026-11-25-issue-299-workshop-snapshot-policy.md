# Workshop 개발선 전환 뒤 중앙 consumer verifier 정책을 갱신한다

## Context

Dependencies #291은 다음 개발선 `2.2.0-SNAPSHOT`을 열면서 Workshop과 예제 저장소가
공식 `2.1.0` BOM을 유지한다고 분류했다. 이후 bluetape4k-workshop #1068은 중앙 BOM을
`2.2.0-SNAPSHOT`으로 바꾸어 `develop`에 merge됐다. 중앙 CI는 검증 때마다 consumer의
최신 `develop`을 fresh clone하므로, 기존 manifest 분류가 실제 개발선과 어긋났다.

## Decision or Finding

현재 live `develop` 카탈로그를 직접 읽어 Workshop은 개발 SNAPSHOT consumer로, 나머지
네 example/application 저장소는 공식 release consumer로 분류한다. 이번 기준에서는
`bluetape4k-workshop`의 key가 `bluetape4k-dependencies-version`이며 기대 버전은
`2.2.0-SNAPSHOT`이다.

## Outcome

Issue #299를 등록하고 manifest에서 Workshop을 `development-snapshot-repositories`로
옮긴다. 테스트는 안정 consumer 네 곳과 Workshop 개발선 key를 고정해 확인한다. 이
정책은 Exposed DAO alias Issue #293과 별개지만, #293 PR CI가 최신 consumer와 함께
통과하는 데 필요한 사전 수정이다.

## Verification

- Dependencies PR #298 run #45480299032에서 기존 오류를 재현했다.
- GitHub API의 현재 `develop` catalog에서 Workshop `2.2.0-SNAPSHOT` 및 나머지 네
  저장소의 `2.1.0`을 확인했다.
- 정책 변경 전 회귀 테스트는 Workshop이 공식 release 목록에 있다는 assertion에서
  실패했다.
- 정책 수정 뒤 `tests.test_post_publish_next_development_line` 22개가 통과했다.
- live `develop` catalog를 넣은 임시 consumer workspace에서 verifier가 통과했다:
  publisher 8, snapshot library 9, stable example 4, development-snapshot example 1.
- 기본 로컬 workspace verifier는 오래된 `timefold-workshop` checkout 때문에 실패했다.
  GitHub API에서 현재 `develop`이 공식 `2.1.0`을 사용함을 확인한 뒤 임시 workspace
  검증으로 교체했다.
- live workspace를 포함한 exact-head CI 재실행은 후속 확인 항목이다.

## Future Guidance

consumer의 BOM 경계가 stable과 development SNAPSHOT 사이에서 바뀌면 consumer PR과
같은 전달 순서에서 중앙 manifest, 회귀 테스트, 개발 기록을 함께 갱신한다. CI가
fresh remote clone을 쓸 때는 로컬 checkout 상태를 live remote 상태로 간주하지 않는다.
