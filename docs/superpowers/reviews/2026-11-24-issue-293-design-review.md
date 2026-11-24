# Issue #293 중앙 catalog alias 설계 리뷰

## 결과

- 대상 설계: `docs/superpowers/specs/2026-11-24-issue-293-exposed-dao-r2dbc-alias-design.md`
- 기준 설계 commit: `2cdfd0de1bddda088ca41736650ed2135240fc00`
- 리뷰 방식: inline fallback review. native `code-reviewer` 실행은 `/opt/homebrew/Caskroom/codex/0.171.0/bin/codex-code-mode-host` 부재로 문서 접근 전에 실패했다. 따라서 독립 reviewer attestation은 주장하지 않는다.
- 설계 결과: P0=0, P1=0. 수정한 P2 두 건을 다시 확인했다.

## 발견과 처리

| 등급 | 근거 | 발견 | 처리 |
|---|---|---|---|
| P2 | 설계 §4와 §7 | §4는 설계·계획·리뷰·lesson 기록도 작업 산출물에 포함했지만, §7은 최종 diff를 catalog·test·evidence만으로 제한해 서로 모순됐다. | §7에서 PR 변경 집합과 구현 소스 diff의 경계를 나눴다. 닫힘. |
| P2 | 설계 §7; `tests/test_kotlinx_serialization_catalog.py`; `.github/workflows/ci.yml:480` | 회귀 검사는 Python `unittest` 패턴인데 완료 기준은 Gradle build만 요구해 회귀 테스트 실행을 보장하지 않았다. CI의 발견 명령도 완료 기준에 없었다. | `python3 -m unittest discover -s tests -p 'test_*.py'`를 완료 기준에 추가하고 기존 CI 명령을 출처에 기록했다. 닫힘. |

## 7개 관점 확인

| 관점 | 검토 결과 |
|---|---|
| 성능 | catalog alias만 추가하므로 실행 시점 동작이나 성능 경로는 바뀌지 않는다. Maven Central 소비자 해석은 alias 사용성 검증에 적합하며 별도 성능 benchmark는 필요하지 않다. |
| 안정성 | 기존 `exposed` version ref, sidecar checksum, 명시적 alias 검사로 버전 드리프트와 catalog 변조를 검출한다. 실패 시 alias와 sidecar만 되돌릴 수 있다. |
| 보안 | 이번 변경은 catalog 노출만 포함하고 모듈 의존성 또는 게시 POM을 바꾸지 않는다. 향후 #942에서 실제 DAO 의존성을 사용하는 시점의 transitive graph와 API 검토는 별도 범위다. |
| 운영 | checksum 검사, catalog/ignore 검사, Python 테스트, Gradle build 및 exact-head PR 확인이 완료 기준에 연결됐다. 게시·tag·merge 경계도 보존됐다. |
| 개발자/API | alias 좌표와 기존 버전 키가 명확하며 `libs.exposed.dao.r2dbc` 소비 예제가 포함됐다. 테스트는 module, version ref, 실제 선택 버전을 확인하도록 정의됐다. |
| 사용자/소비자 | 소비자는 `mavenCentral()`만으로 alias를 해석할 수 있고, #942는 #293 병합 뒤 고정 SHA를 사용하도록 계약이 구체적이다. 사용 설명은 구현 모듈이 제공된 뒤 #942에서 다룬다. |
| 통합 | #293의 중앙 catalog 변경과 #942의 별도 R2DBC DAO 모듈 사이 의존 관계가 분리돼 있다. version key, BOM, ignore 목록, 생성 catalog, publication POM 범위가 혼합되지 않는다. |

## 검증 경계

- 설계, 기존 catalog 회귀 테스트, CI의 Python test 명령, 변경 diff를 읽기 전용으로 확인했다.
- 이 단계에서는 구현 코드나 테스트를 추가·실행하지 않았다.
- `.bluetape` run `20261124T125346Z-df0e8e85`의 `spec_performance` native lane은 실제 실패 상태로 보존됐다. 이 문서는 inline fallback 판단이며 독립 리뷰 완료 기록이 아니다.

Inline verdict: PASS; P0=0, P1=0.

## Writer gate 기록

- SPW-01: PASS — 설계 파일, 승인된 결정, 이슈, catalog/test/CI 근거와 reviewer 실행 제한을 고정했다.
- SPW-02: PASS — 리뷰 범위, 심각도, 근거 위치, 수정 내용, 7개 관점, 검증 경계와 verdict를 기록했다.
- SPW-03: PASS — 한국어 기술 문체를 적용하고 기술 식별자와 명령을 보존했다. KO-01~KO-07을 확인했고 contextual terminology audit는 finding 0건이다.
- SPW-04: PASS — 각 발견을 설계 변경과 기존 catalog/test/CI 근거에 연결했으며 독립 reviewer 부재를 명시했다.
- SPW-05: PASS — 표, 섹션, 링크, 명령과 최종 verdict를 다시 읽었다.
