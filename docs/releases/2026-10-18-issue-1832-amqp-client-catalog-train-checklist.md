# 2026-10-18 Issue #1832 RabbitMQ 카탈로그 train 체크리스트

상태: **PENDING / 카탈로그 감사, 소비자 해석·영향 테스트, 9개 downstream assemble, 9개 publisher POM/Maven model 통과; 전체 `build`, 전체 resolved graph, remote CI/alert 검증 대기**

## 고정 범위와 중단 조건

- 분류: Type P `catalog-train-snapshot`. Issue #1832의 Gradle Dependabot `dependency_not_found` 오류를 조사하고, 공식 수정 버전을 중앙 카탈로그에서 공급한다.
- 중앙 저장소: `bluetape4k/bluetape4k-dependencies`; 기준 `develop` / `775af2ecdf3658c332181bfd7865a55d04bf68f7`; 후보 `fix/issue-1832-amqp-client-5-37-0`.
- 소비자 범위: `bluetape4k-projects`의 Testcontainers 모듈에서 `bt4k.amqp.client`를 test dependency로 사용한다. 해당 저장소만 이 작업에서 새 불변 카탈로그 SHA로 고정한다. 다른 소비자 영향은 occurrence inventory와 workspace 검사로 확인한다.
- 대상 버전: `com.rabbitmq:amqp-client` `5.35.0` → `5.37.0`. Maven Central metadata audit는 2026-10-18T09:35:19Z에 `5.37.0`을 확인했으며 metadata SHA-256은 `4a8d176c0be3c69783badf2a253eda5b0ebbfc488ff815e77ba967d7dc2762af`다. 2026-10-18에 upstream advisory와 release 페이지를 다시 읽었다. [공식 보안 권고](https://github.com/rabbitmq/rabbitmq-java-client/security/advisories/GHSA-cqgh-8p3p-mx4m)는 `<=5.36.0` 영향, `5.37.0` 수정으로 표시하며, [5.37.0 릴리스](https://github.com/rabbitmq/rabbitmq-java-client/releases/tag/v5.37.0)는 해당 버전의 정식 Maven/Gradle 좌표를 공개한다. GitHub alert API의 `first_patched_version=5.36.1`은 advisory와 충돌하므로 이 값만으로 수정 버전을 선택하지 않는다.
- 대상 authority: `managed:managed-amqp-client-h639dbc3b57d0`; 생성 alias `amqp-client`. Maven BOM이나 발행 라이브러리의 production dependency는 변경하지 않는다.
- 릴리스 분류: Maven artifact/BOM release가 아니다. 중앙 catalog의 immutable ref만 병합 후 `catalog/2026-10-18-01`로 발행한다. tag 생성에는 병합 후 fresh approval이 필요하다.
- dispatch 순서: Dependencies PR은 아래 검증 후 생성한다. 병합은 정확한 head·CI·리뷰 상태를 보고한 뒤 새 승인을 받는다. 병합된 SHA에서 catalog ref `catalog/2026-10-18-01`을 만들고, 그 ref를 고정한 Projects PR을 생성한다. Projects 병합 후 Dependency Submission을 확인하고 alert #267의 `Try again`을 실제 실행한다. Maven Central publish와 GitHub Release는 이 train 범위가 아니다.

## 필수 게이트

- [x] **REL-01 — 대상과 authority 고정:** repository, base SHA, branch, 좌표/버전, authority, Projects 소비자 범위를 기록했다. 최신 upstream patch와 alert API의 불일치를 위 출처로 확인했다.
- [x] **REL-02 — live issue/PR 상태 재확인:** PR 생성 전 live GitHub를 확인했다. Projects Issue #1832는 OPEN, milestone `2.1.0`, labels `security`/`ci`, assignee `debop`이며, 두 저장소에서 `1832` 검색 결과 열린 중복 PR은 없었다. Dependencies에는 중복 open issue가 없었다.
- [x] **REL-03 — 동일 catalog 상태 검증:** Dependencies 후보 catalog 파일 SHA-256 `32887e9060e334600d3ff623ba60bd17fb732f45894d29e0f4a2f1b96924af8b`와 Projects `develop` SHA `d78baa47c6b60bd8e931d61539c2fe939f8cc3f5`에서 `:bluetape4k-testcontainers:dependencyInsight`를 실행했다. `testRuntimeClasspath`는 `com.rabbitmq:amqp-client:5.30.0 -> 5.37.0`을 출력했고 선택 근거는 `Selected by rule`, `By constraint`였다. 이어 `:bluetape4k-testcontainers:compileTestKotlin`이 통과했고 `RabbitMQServerTest` 3개가 통과했다. 첫 실행은 context-mode 자식 프로세스에 Docker 변수가 전달되지 않아 Docker 탐색에서 실패했으며, 확인된 Colima socket을 해당 재실행 프로세스에 설정해 통과했다.
- [x] **REL-04 — 안정 배치:** Maven 안정판 artifact/BOM release가 아니므로 N/A. 이 train은 중앙 catalog와 소비자 pin만 다루며 downstream stable publication을 시작하지 않는다.
- [x] **REL-05 — 발행 POM 최종 게이트:** Projects 소비자는 `testing/testcontainers/build.gradle.kts:197`의 `testImplementation(bt4k.amqp.client)`다. exact candidate repository map으로 Dependencies + 8개 library publisher의 POM 192개와 Maven effective model 192개를 검증했다. 결과 `failures=0 repositories=9 files=192 dependencies=50543 maven_models=192`; map SHA-256 `2066bc8cfc9425a22f969853562802891dc34205576fb3c35b35dca638e29789`. 생성 POM에는 `com.rabbitmq`/`amqp-client`가 없어 공개 dependency 변경은 없다. Maven publication은 하지 않는다.
- [x] **REL-06 — downstream assemble:** 후보 catalog로 `bluetape4k-projects`, `bluetape4k-aws`, `bluetape4k-experimental`, `bluetape4k-exposed`, `bluetape4k-graph`, `bluetape4k-image`, `bluetape4k-javers`, `bluetape4k-leader`, `bluetape4k-text`의 `./gradlew assemble --no-parallel --max-workers=1`이 각각 성공했다. `full-builds`와 테스트 suite 상태는 이 assemble 결과만으로 통과 처리하지 않는다.
- [ ] **REL-07 — 전체 build / 테스트 완료:** Projects 후보 전체 `build --continue --no-parallel --max-workers=1`은 Context Mode 호출의 300초 제한으로 터미널 결과를 받지 못했다. 별도 재실행에서는 `:bluetape4k-cache-lettuce:test`의 407개 중 43개 실패가 관찰됐지만 기준 코드에서 해당 모듈 `--rerun-tasks`를 worker 1과 4로 각각 실행해 464/464 통과하여 실패는 재현되지 않았다. 기준 코드 `:bluetape4k-lettuce:detektTest`는 변경하지 않은 테스트 파일에서 69건으로 실패했다. 원인은 확정하지 않으며, 이 항목은 미완료 상태로 유지한다.
- [ ] **REL-08 — 전체 resolved graph / remote CI:** Projects `testRuntimeClasspath`의 대상 `dependencyInsight`는 `5.30.0 -> 5.37.0` 및 `Selected by rule`, `By constraint`를 확인했지만, 전체 candidate resolved-graph receipt와 원격 immutable ref/PR/CI는 아직 없다.
- [ ] **Live update 검증:** 병합 후 Dependency Submission을 확인하고, alert #267 페이지에서 실제 Dependabot 재시도를 실행한다. `dependency_not_found`가 계속되면 이를 오류 미해소로 기록하고 Issue #1832를 열린 상태로 유지한다.

## 진행 증거

- Issue #1832: https://github.com/bluetape4k/bluetape4k-projects/issues/1832
- Dependabot alert #267: https://github.com/bluetape4k/bluetape4k-projects/security/dependabot/267
- Live issue/PR lookup: `gh issue view 1832 --json number,title,state,milestone,labels,assignees,url` confirmed OPEN / `2.1.0` / `security`,`ci` / `debop`; `gh pr list --state open --search '1832'` returned no PR in Dependencies or Projects, and Dependencies `gh issue list --state open --search '1832'` returned none.
- Projects consumer proof: `./gradlew :bluetape4k-testcontainers:dependencyInsight --dependency com.rabbitmq:amqp-client --configuration testRuntimeClasspath -Pbluetape4kDependenciesCatalogPath=/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/fix/issue-1832-amqp-client-5-37-0/gradle/libs.versions.toml`; resolved `5.30.0 -> 5.37.0` at Projects SHA `d78baa47c6b60bd8e931d61539c2fe939f8cc3f5`.
- Published-POM proof: `:bluetape4k-testcontainers:generatePomFileForBluetape4kPublication` succeeded with the candidate catalog; generated `testing/testcontainers/build/publications/Bluetape4k/pom-default.xml` contains neither `com.rabbitmq` nor `amqp-client`.
- Full POM/model proof: `scripts/verify-publication-poms.py --repository-map build/issue-1832/repository-map.json --summary` reported `failures=0 repositories=9 files=192 dependencies=50543 maven_models=192` on catalog SHA-256 `32887e9060e334600d3ff623ba60bd17fb732f45894d29e0f4a2f1b96924af8b`; repository-map SHA-256 `2066bc8cfc9425a22f969853562802891dc34205576fb3c35b35dca638e29789`. `sync-shared-versions.py --repository-map build/issue-1832/repository-map.json --check --summary` also passed.
- Affected verification: candidate catalog으로 `:bluetape4k-testcontainers:compileTestKotlin`이 통과했다. `DOCKER_HOST=unix:///Users/debop/.colima/default/docker.sock`와 `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`를 확인된 Colima에 한해 테스트 자식 프로세스에 전달한 뒤 `:bluetape4k-testcontainers:test --tests io.bluetape4k.testcontainers.mq.RabbitMQServerTest`가 3개 테스트를 통과했다. Gradle은 기존 Jib `Task.project` configuration-cache 직렬화 경고 12건(고유 4건)을 보고하고 캐시 항목을 폐기했지만 테스트는 성공했다.
- Downstream assemble proof: the candidate catalog was passed via `-Pbluetape4kDependenciesCatalogPath=...`; `assemble --no-parallel --max-workers=1` succeeded in all 9 downstream consumers. The affected Projects assemble completed 247 actionable tasks; AWS 43; Experimental 16; Exposed 118; Graph 80; Image 107; JaVers 29; Leader 150; Text 40. These are assemble results, not full `build` or full test results.
- Full-build disposition: candidate `:bluetape4k-cache-lettuce:test` once reported 43 failures among 407 tests. Baseline `--rerun-tasks --no-parallel` reruns passed 464/464 at both worker 1 and worker 4, so the failure was not reproduced and its cause is unknown. Baseline `:bluetape4k-lettuce:detektTest` reported 69 findings in unchanged test sources. The later candidate root `build --continue --no-parallel --max-workers=1` call timed out at the 300-second tool limit without a final Gradle result. Do not claim the whole Projects build passed.
- Dependencies governance: latest-stable audit/check, central catalog adoption check, managed catalog alias check, and `python3.13 -m unittest tests/test_catalog_checksum.py tests/test_latest_stable_version_deltas.py tests/test_audit_latest_stable.py tests/test_central_catalog_version_deltas.py tests/test_ci_catalog_governance.py` (78 tests) passed; `git diff --check` passed.
- Lesson gate: 새 규칙을 만들지 않았다. 기존 `docs/lessons/2026-10-09-gradle-dependabot-central-catalog.md`가 중앙 catalog 수정, consumer 고정 참조, 실제 alert 확인을 이미 다루므로 별도 lesson은 N/A다.
- Dependencies PR: pending
- Full candidate build and exhaustive resolved-graph receipt: pending
- Catalog tag: pending; merge readiness 승인 전에는 생성하지 않는다.
- Projects PR: pending
- CI / Dependency Submission / 실제 alert 재시도: pending
