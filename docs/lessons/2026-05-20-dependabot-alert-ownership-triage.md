# Dependabot 경고 소유권 분류

## 배경

취약한 의존성 버전을 `bluetape4k-dependencies`가 관리하더라도 다운스트림 저장소에
Dependabot 보안 경고가 표시된다. 다운스트림 Dependabot 변경을 직접 병합하면
카탈로그가 어긋나고 의존성 결정이 중복된다.

## 결정

버전을 변경하기 전에 의존성 소유권에 따라 경고를 분류한다.

- `central-catalog`: `bluetape4k-dependencies`를 먼저 업데이트한 다음 다운스트림을
  동기화한다.
- `central-bom-transitive`: 패치된 BOM이 있으면 소유 BOM 라인을 업데이트하고,
  패치된 BOM이 나올 때까지 중앙 재정의를 유지한다.
- `repo-tooling`: 패키지를 중앙 거버넌스 대상으로 승격하지 않는 한 저장소 설정이나
  플러그인 도구를 수정한다.
- `repo-local`: 매니페스트를 소유한 저장소에서 직접 수정한다.

## 결과

이제 `scripts/triage-dependabot-alerts.py`는 GitHub 취약점 경고를 읽고, 패키지를
중앙 카탈로그 및 ignore 목록과 대조한 뒤 Markdown 또는 JSON 소유권 보고서를
출력한다. BouncyCastle, ClassGraph, Tomcat 경고의 소유권은 중앙 카탈로그와 BOM
제약 조건에 명시되어 있다.

## 검증

- `python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py scripts/sync-dependabot-ignores.py scripts/triage-dependabot-alerts.py`
- `python3 -m unittest tests/test_sync_dependabot_ignores.py tests/test_sync_shared_versions.py tests/test_sync_managed_catalog.py tests/test_triage_dependabot_alerts.py`
- `scripts/sync-shared-versions.py --workspace .. --check --summary`
- `scripts/sync-dependabot-ignores.py --workspace .. --check --summary`
- `scripts/triage-dependabot-alerts.py --repo bluetape4k-exposed`
- `scripts/triage-dependabot-alerts.py --repo bluetape4k-projects`
- `./gradlew build`

## 향후 지침

패키지를 중앙에서 관리하는 경우 리프 카탈로그를 먼저 수정해 다운스트림 Dependabot
경고를 닫지 않는다. 중앙 라인을 추가하고 다운스트림 카탈로그와 ignore를 동기화한
다음 저장소별 잔여 항목을 처리한다.
