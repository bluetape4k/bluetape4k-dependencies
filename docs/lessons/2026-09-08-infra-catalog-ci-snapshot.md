# 신규 인프라 모듈의 카탈로그와 CI 검사 기준

projects #1715–#1717의 SDK와 신규 모듈 alias를 중앙에 등록했다. 로컬의 최신 모듈 디렉터리만으로 카탈로그를 생성하면 CI가 고정한 publisher SHA와 목록이 달라질 수 있다.

## 결정과 재발 방지

- SDK는 OpenFGA 0.10.0, Qdrant 1.19.0, Temporal 1.38.0을 사용한다. OpenFGA·Qdrant는 BOM constraint, Temporal은 공식 BOM import로 관리한다.
- `config/publishing-signing-repository-refs.json`의 projects SHA를 원격에서 확인한 `f78ce75cc763747448a75700fab005644415d755`로 갱신했다. 다른 publisher SHA와 canonical signing source는 유지했다.
- 생성기는 이 manifest의 8개 정확한 Git tree를 입력으로 실행했다. 기존 로컬 exposed checkout에서 우연히 포함된 tenant-jdbc alias를 제거하고, 이번 신규 3개 모듈을 포함한 187개 alias를 확인했다.
- 향후 새 모듈을 등록할 때는 먼저 구현 커밋을 push하고, CI가 검사할 SHA와 생성기의 입력을 맞춘다. 생성 영역 수동 편집이나 CI 검증 생략으로 불일치를 숨기지 않는다.
- 소비자의 기본 catalog ref는 원격에서 조회할 수 있는 중앙 commit으로 고정한다. 카탈로그 파일을 읽는 것과 Maven에 BOM을 발행하는 것은 별도 작업이다.

## 검증 및 전달 조건

- 관련 Python 테스트 74개 통과: checksum, managed catalog, Dependabot ignore, CI governance, signing support.
- 중앙 `./gradlew build generatePomFileForBluetapeDependenciesPublication --no-daemon --no-configuration-cache --max-workers=1` 통과.
- 생성기 `--write --check --summary`: 187 aliases, 8 sub-BOM, projects 82 aliases.
- 기존 publish 플러그인 deprecation 경고는 남아 있다. 이 작업은 publication plugin을 변경하지 않는다.
- 원격 CI의 전체 publisher POM 및 signing 검증은 PR에서 확인한다. 이를 통과하기 전에는 cross-repository 전달 완료로 보고하지 않는다.
- 병합·tag·Maven 발행은 수행하지 않았다. 사용자에게 최신 head와 CI를 보고한 뒤 병합 승인을 받는다.

문서 검토 SPW-01–05: 대상은 저장소 유지보수자이며, manifest·생성 결과·테스트 출력과 대조했다. 한국어 설명과 정확한 SHA·명령을 유지했고, 미수행 원격 검증을 명시했다.

## SDK alias 추가 시 감사 기록 보존

- CI에서 관련 테스트 74개만으로 감사 계약도 통과할 것으로 판단했지만, 전체 suite는 신규 SDK alias 6개가 빠진 `515` authority 기대치를 발견했다. 신규 외부 alias 추가 시 inventory, audit, delta-ledger 테스트를 함께 확인하고 전체 Python suite를 실행한다.
- 단순 전체 재감사는 기존 upstream 변경 33개와 `adopt-latest` 23건까지 포함했다. 이 작업은 기존 버전 업그레이드를 포함하지 않으므로 기존 515개 감사 기록과 실제 조회 시각을 그대로 보존하고, 공식 Maven Central에서 조회한 신규 6개 기록만 추가했다.
- 증분 감사의 최상위 `retrieved-at`은 기록을 모은 스냅샷의 조회 시각 상한이다. 각 기록의 `retrieved-at`은 해당 metadata의 실제 조회 시각이며 최상위 시각보다 늦을 수 없다. 기존 기록이 이 시각에 새로 검증되었다는 의미가 아니다.
- 검증기는 기존 inventory·policy hash, 좌표·버전·요약 검사에 더해 UTC 시각 형식, 존재하지 않는 날짜, 누락, 미래 조회 시각을 거부한다. 과거 시각 보존 테스트는 변경 전 실패하고 변경 후 통과했다.
- 재현 시 기존 커밋의 audit를 authority-key로 읽고 신규 조회 결과와 병합한다. 보존할 기록의 좌표·버전·policy가 변했다면 보존하지 말고 다시 조회한다. 이 변경에서는 기존 inventory 515개와 audit-policy가 모두 동일함을 대조했다.
- 수정 후 Python 3.14 전체 suite는 443개 실행, 실패 0, skip 2였다. skip은 worktree에서 고정된 sibling 경로를 찾지 못한 기존 workspace 검사이며, 실제 publisher 계약은 원격 CI에서 별도로 확인한다. 감사 대상 521개 중 metadata 조회 실패는 0이다.

## 병합과 발행 단계의 검증 기준

- SNAPSHOT workflow의 입력만 확인하면 feature 브랜치에서도 발행할 수 있다고 잘못 판단할 수 있다. 실제 `maven-central-release` 환경은 `develop`과 버전 태그만 허용했다. 다음 발행에서는 workflow와 환경 branch policy를 함께 조회하고, 정책을 완화하지 않고 병합 후 정확한 develop SHA로 발행한다.
- Projects 병합 커밋 `d6e4a8be88813632992fbd78e4e41066006d8260`의 발행 run `34244599690`은 성공했으며 82개 모듈·822개 공개 파일을 확인했다. workflow 성공과 공개 아티팩트 존재를 별도 검증한다.
- 중앙 develop 병합 시 감사 JSON을 한쪽으로 덮어쓰면 새 SDK나 기존 감사 결과를 잃는다. upstream 515개 record의 완전 동일성과 신규 SDK 6개 보존을 비교하고, inventory·checksum·입력 hash를 갱신한 뒤 감사 검사를 실행한다.
- macOS 기본 `python3`는 Apple Python 3.9를 선택해 `tomllib`과 sandbox 라이브러리 로딩 검사를 실패시켰다. 전체 검사 전 interpreter 버전을 확인하고 설치된 Python 3.14로 실행한다.
- 카탈로그 참조를 갱신한 publisher는 중앙 `post-publish-next-development-line.json`의 해당 repository override도 함께 갱신한다. CI가 실제 Projects 참조 `f16b29a0da64481c19443f76476e8166dbc57618`과 이전 정책 참조 불일치를 검출했다. 다른 repository override와 strict equality 검증은 유지한다.
