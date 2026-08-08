# 의존성 미해결 이슈

## 배경

`bluetape4k-dependencies` issue #39에서는 이 저장소에서
`scripts/sync-dependabot-ignores.py`를 실행할 때 워크스페이스 루트의 상위
디렉터리를 기본값으로 사용한다는 사실이 드러났다. Issues #34와 #35에서는
다운스트림 저장소에 영향을 주는 두 공유 의존성인 MyBatis Dynamic SQL 2.x와
Timefold Solver 2.x도 승격했다. 열린 Dependabot PR은 AWS SDK Java, AWS SDK
Kotlin, ClassGraph, Apache Fory의 공유 패치/마이너 업데이트도 제안했다.

## 결정

`gradle/libs.versions.toml`을 기준 데이터 원본으로 유지하고, 기본 워크스페이스
리졸버가 `bluetape4k-dependencies` 체크아웃에서 탐색을 멈추도록 수정하며, 조정된
PR을 통해 2.x 버전을 다운스트림 저장소에 반영한다.

## 결과

- MyBatis Dynamic SQL을 `2.0.0`으로 승격했다.
- Timefold Solver를 `2.1.0`으로 승격했다.
- AWS SDK Java를 `2.44.9`로 승격했다.
- AWS SDK Kotlin을 `1.6.77`로 승격했다.
- ClassGraph를 `4.8.184`로 승격했다.
- Apache Fory core와 Kotlin을 `0.17.0`으로 승격했다.
- Dependabot ignore 동기화의 기본값이 이제 bluetape4k 워크스페이스 루트다.
- 대상 Dependabot 파일을 찾지 못하면 `--check`가 실패하므로 조용한 오탐을
  방지한다.

## 검증

- `python3 -m unittest tests/test_sync_dependabot_ignores.py tests/test_sync_shared_versions.py tests/test_sync_managed_catalog.py tests/test_triage_dependabot_alerts.py`
- `./gradlew build --no-daemon`
- `scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --check --summary`
- `scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --check --summary`

두 동기화 검사는 다운스트림 업데이트가 feature worktree에 있고, 이전에 생성한
Dependabot-ignore PR 두 개가 아직 기준 워크스페이스에 병합되지 않았기 때문에
예상된 불일치를 보고했다.
