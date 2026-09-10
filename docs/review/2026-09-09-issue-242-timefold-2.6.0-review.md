# Issue #242 Timefold 2.6.0 7-Tier 코드리뷰

- 검토일: 2026-09-09
- 대상: 중앙 `bluetape4k-dependencies` candidate와 Exposed/Workshop/Clinic 소비자 경로
- 판정: **BLOCKED**
- 근거 receipt: `build/issues-242-243/issue-242-receipt.json` (mapping 교정 후 최신 receipt)
- 관련 차단 증거: [`2026-09-09-issue-242-timefold-2.6.0-blocked-evidence.md`](../releases/2026-09-09-issue-242-timefold-2.6.0-blocked-evidence.md)

## 요약

중앙 catalog와 candidate BOM 생성은 통과했으며, runner와 receipt는 실제
`dependencyInsight` 의미를 검사하고 실패를 보존한다. 그러나 baseline graph에서
필수 소비자 증거가 완성되지 않아 `2.6.0` adoption, candidate graph, 소비자 테스트,
publication POM 및 hosted CI로 진행하지 않았다.

## 7-Tier 결과

| Tier | 결과 | 근거와 남은 위험 |
| --- | --- | --- |
| 1. Source/Implementation | PASS | 중앙 `timefold-solver` ref와 checksum, candidate BOM POM/Module Metadata, graph semantic parser와 receipt CAS 경계를 검증했다. semantic 실패 cache 제거 회귀 테스트가 있다. |
| 2. Callers/Consumers | BLOCKED | Exposed persistence의 직접 graph는 core로 정정됐고 Workshop baseline의 core/Jackson/starter는 `2.2.0`으로 확인됐지만, Clinic benchmark는 verification 오류로 중단됐다. 소비자 graph 합집합의 네 좌표 coverage는 유지된다. |
| 3. Tests/Fixtures | BLOCKED | 중앙 runner/receipt Python 93개 targeted test는 통과했다. 필수 candidate graph와 Exposed/Workshop/Clinic consumer test는 baseline gate 실패로 실행하지 않았다. |
| 4. ABI/API/Compatibility | PASS (범위 한정) | Kotlin/Java public API를 직접 변경하지 않았고 기존 Timefold aliases와 persistence API를 재사용했다. 다만 dependency promotion 호환성은 consumer graph 미완료로 승인하지 않는다. |
| 5. Docs/KDoc/Contracts | PASS | 설계/실행 plan, 차단 증거, 본 7-Tier review를 한국어로 남겼다. 독립적인 KDoc API 변경은 없다. |
| 6. CI/Publication | BLOCKED | local candidate BOM은 생성됐지만 publication POM phase, consumer build, exact-head hosted CI, snapshot/publication dispatch는 baseline 실패 때문에 실행하지 않았다. `SKIPPED`를 PASS로 집계하지 않았다. |
| 7. Design/Reuse/Ops Risk | BLOCKED | 공통 catalog inventory, runner, receipt validator와 cache primitive을 재사용했고 실제 소비자별 좌표로 계약을 교정했지만 Clinic verification metadata의 재검토가 필요하다. |

## 검증된 증거

- 중앙 candidate BOM coordinate: `io.github.bluetape4k:bluetape4k-dependencies:2.1.0-issue-242.local`
- baseline phase: `timefold-graphs-baseline`, result `fail`
- Workshop: `core`, `jackson`, `spring-boot-starter` 모두 `2.2.0`; 각 output digest와 selection reason은 receipt에 기록됨
- Exposed: persistence runtime에서 직접 소비하는 `core`만 `2.4.0`으로 선택; benchmark/Jackson/starter는 이 모듈의 graph 계약에서 제외
- Clinic: `temporal-bom:1.38.0`의 `.module`/`.pom` verification 실패
- receipt state: `blocked`; pending graph marker는 미완료 증거를 보존하기 위해 허용되며 terminal 상태에서는 허용되지 않음
- local cleanup: candidate Maven repository와 실패 artifact를 정리하지 않음

## 재사용 및 Kotlin 패턴 점검

- 새 dependency나 별도 version source를 추가하지 않았다.
- 기존 central BOM import, versionless alias, catalog checksum, candidate init script,
  repository inventory와 receipt validator를 재사용했다.
- semantic 검증을 우회하는 blanket `exit code` 처리나 cache 재사용을 도입하지 않았다.
- Exposed에 사용하지 않는 Timefold runtime dependency를 억지로 추가하는 방식은
  선택하지 않았다. 실제 consumer mapping 또는 계약 범위 결정을 먼저 해야 한다.

## 판정과 다음 재검토

P0는 없다. P1 adoption blocker는 Clinic baseline verification metadata 한 가지다.

1. Exposed core, Workshop core/Jackson/starter, Clinic benchmark의 실제 consumer
   runtime 매핑과 합집합 네 좌표 coverage를 새 receipt에서 확인한다.
2. Clinic dependency verification metadata를 공식 artifact digest로 갱신한다.

두 조건을 해결한 새 clean baseline/candidate worktree와 receipt에서 baseline부터
재실행해야 한다. 그 전에는 central policy를 `defer-breaking-migration`과
`validation-pending`으로 유지한다.

**최종 상태: BLOCKED — Issue #242를 닫거나 2.6.0 adoption으로 전환하지 않음.**
