# Snapshot metadata가 지정한 timestamped artifact의 실재를 확인한다

## Context

`--require-artifacts`를 사용하는 개발선 verifier가 version-level
`maven-metadata.xml`의 HTTP 성공만 확인하면, metadata는 있어도 실제 게시 파일이
빠진 상태를 통과시킬 수 있다. 이 경우 다음 소비자는 metadata가 가리키는 timestamped
POM, Gradle module metadata 또는 기본 artifact를 가져오지 못한다.

Artifact 존재 확인은 `.module`과 JAR에 HEAD를 사용한다. 저장소가 HEAD를 HTTP 405로
거부하면 GET으로 fallback하는데, 응답 상태만 필요한 경로에서 `response.read()`를
호출하면 timestamped JAR 본문 전체를 메모리에 읽게 된다.

## Decision or Finding

Metadata는 artifact 위치를 알려주는 인덱스이지 게시 완료의 증거가 아니다. Metadata에서
unclassified `pom`, `.module`, 그리고 packaging에 맞는 기본 artifact의 timestamped
버전을 읽은 뒤 각 파일 URL을 직접 확인한다. POM packaging BOM에는 JAR을 요구하지 않고,
JAR packaging에는 timestamped JAR을 요구한다. 오류에는 좌표, 확장자, HTTP 상태와 실제
요청 URL을 남긴다. Metadata와 POM을 읽는 일반 GET 경로는 응답 본문이 필요하다. 반면
HEAD 405 fallback은 존재 여부를 HTTP 상태로 판정하고 빈 본문을 반환한다. 이 경로에서는
응답 본문을 읽거나 보관하지 않는다.

## Outcome

Issue #294의 회귀 검증은 metadata만 200이고 timestamped POM 또는 `.module`이 404인
경우를 거부한다. POM packaging BOM은 JAR 없이 통과하며, JAR packaging artifact는
timestamped JAR이 없으면 실패한다. `--require-artifacts`를 사용하지 않는 preflight
경로의 계약은 유지한다. Issue [#300](https://github.com/bluetape4k/bluetape4k-dependencies/issues/300)의
회귀 테스트는 HEAD 405 후 GET 응답이 200이어도 `read()`를 호출하지 않고, 요청 순서와
존재 판정 결과가 유지되는지 확인한다.

## Verification

- `tests/test_post_publish_next_development_line.py`에 metadata-only, POM BOM, JAR
  packaging 세 경계의 회귀 검사를 둔다.
- HEAD 405 fallback 테스트에서 응답 `read_count == 0`과 `(True, "200", b"")`를 확인한다.
- PR #297의 통합 전 exact-head CI는 모든 required checks가 통과했으며, 현재 develop
  통합 후보에서도 exact-head CI를 다시 실행한다.

## Future Guidance

Snapshot 게시 성공을 판정할 때 version-level metadata 응답만 검사하지 않는다. Metadata가
가리키는 timestamped 파일을 직접 확인하고, artifact의 Maven packaging에 따라 필수 파일
집합을 정한다. POM BOM과 JAR packaging artifact를 같은 필수 파일 규칙으로 다루지 않는다.
HEAD를 지원하지 않아 GET으로 fallback하는 존재 확인은 응답 상태만 사용한다. 응답 본문을
소비하는 일반 GET 경로와 구분해 대용량 artifact를 불필요하게 다운로드하거나 메모리에
적재하지 않는다.
