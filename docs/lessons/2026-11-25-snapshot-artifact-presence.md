# Snapshot metadata가 지정한 timestamped artifact의 실재를 확인한다

## Context

`--require-artifacts`를 사용하는 개발선 verifier가 version-level
`maven-metadata.xml`의 HTTP 성공만 확인하면, metadata는 있어도 실제 게시 파일이
빠진 상태를 통과시킬 수 있다. 이 경우 다음 소비자는 metadata가 가리키는 timestamped
POM, Gradle module metadata 또는 기본 artifact를 가져오지 못한다.

## Decision or Finding

Metadata는 artifact 위치를 알려주는 인덱스이지 게시 완료의 증거가 아니다. Metadata에서
unclassified `pom`, `.module`, 그리고 packaging에 맞는 기본 artifact의 timestamped
버전을 읽은 뒤 각 파일 URL을 직접 확인한다. POM packaging BOM에는 JAR을 요구하지 않고,
JAR packaging에는 timestamped JAR을 요구한다. 오류에는 좌표, 확장자, HTTP 상태와 실제
요청 URL을 남긴다.

## Outcome

Issue #294의 회귀 검증은 metadata만 200이고 timestamped POM 또는 `.module`이 404인
경우를 거부한다. POM packaging BOM은 JAR 없이 통과하며, JAR packaging artifact는
timestamped JAR이 없으면 실패한다. `--require-artifacts`를 사용하지 않는 preflight
경로의 계약은 유지한다.

## Verification

- `tests/test_post_publish_next_development_line.py`에 metadata-only, POM BOM, JAR
  packaging 세 경계의 회귀 검사를 둔다.
- PR #297의 통합 전 exact-head CI는 모든 required checks가 통과했으며, 현재 develop
  통합 후보에서도 exact-head CI를 다시 실행한다.

## Future Guidance

Snapshot 게시 성공을 판정할 때 version-level metadata 응답만 검사하지 않는다. Metadata가
가리키는 timestamped 파일을 직접 읽거나 요청하고, artifact의 Maven packaging에 따라
필수 파일 집합을 정한다. POM BOM과 JAR packaging artifact를 같은 필수 파일 규칙으로
다루지 않는다.
