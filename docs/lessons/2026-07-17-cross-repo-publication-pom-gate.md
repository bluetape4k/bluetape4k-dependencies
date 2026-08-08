# repository 간 publication POM gate

## 배경

중앙 catalog 도입 train은 catalog 소유권, downstream Gradle 구성, build,
resolve된 graph를 검증했다. 중앙 dependency 관리가 버전을 공급하는 경우에는
repository-local alias를 의도적으로 versionless 상태로 둘 수 있게 했다.

이 규칙은 Gradle 작성에는 유효하지만, 해당 train은 library publisher가 생성한
Maven POM을 검사하지 않았다. 따라서 downstream build는 올바르게 resolve되면서도
게시된 dependency-management 항목에는 버전이 빠질 수 있었다. 그 결과 Maven
소비자가 effective model을 만들 때 실패했다.

## 결정 또는 발견

Catalog 권한과 publication metadata는 서로 다른 계약이다. library publisher에
영향을 줄 수 있는 모든 catalog train은 다음 두 가지를 모두 입증해야 한다.

- Gradle이 후보 catalog와 dependency graph를 resolve한다.
- 생성된 모든 POM이 구조적으로 유효하고 Maven이 effective model을 만들 수 있다.

BOM import를 포함한 모든 dependency-management 항목에는 버전이 필요하다.
일반 dependency는 같은 POM의 버전 지정 항목이나 버전이 지정된 imported BOM이
해당 버전을 관리하는 경우에만 버전을 생략할 수 있다. Maven은 imported BOM이
실제로 해당 dependency coordinate를 관리하는지도 검증한다.

## 결과

`scripts/verify-publication-poms.py`는 9개 library publisher를 후보 중앙
catalog 기준으로 구성하고 publication POM 생성 task를 실행한 뒤, 생성된 모든
POM을 감사하고 하나의 임시 Maven reactor에서 모든 effective model을 검증한다.
`bluetape4k-experimental`은 catalog 도입 감사에는 남아 있지만 publisher가
아니므로 이 gate에서는 제외한다.

Gradle version-catalog publication은 Maven이 lifecycle로 인식하지 않는 `toml`
packaging을 사용한다. 원본 POM은 변경하지 않고 감사하며, dependency model
검증을 진행할 수 있도록 임시 Maven-reactor 복사본에서만 `toml`을 `pom`으로
정규화한다.

이 gate는 재생성 전에 기존 `build/publications/*/pom-default.xml` 파일만
제거하고, 구성된 publisher를 managed registry 및 live snapshot-publish
workflow와 비교하며, publication POM profile을 거부한다. 비활성 Maven profile은
그렇지 않으면 기본 effective-model reactor를 빠져나갈 수 있으므로 profile은
fail-closed로 처리한다.

repository map이 ancestor `.worktrees` directory 아래의 후보 root를 선택하면
POM discovery는 선택한 root를 기준으로 제외 대상을 평가한다. 따라서 후보의
publication output은 포함하면서 그 아래에 중첩된 `.worktrees` checkout은 계속
제외한다.

## 검증

- `python3 -m unittest tests/test_verify_publication_poms.py tests/test_ci_catalog_governance.py`
- `scripts/verify-publication-poms.py --workspace .. --summary`
- 9 publisher repositories, 175 freshly regenerated POM files, 46,009 dependency entries, and 175
  Maven effective models passed.

## 향후 지침

“이 train은 게시하지 않는다”를 “Maven validation은 N/A”로 해석하지 않는다.
후보 catalog가 downstream publisher에 영향을 줄 수 있다면 생성된 publication
metadata는 train의 Definition of Done에 포함된다. worktree나 후보 branch가
관련된 경우 `--repository-map`과 함께 exact-candidate gate를 실행하고,
worktree 제외 범위는 절대 filesystem path가 아니라 각 mapping repository root를
기준으로 유지한다.
