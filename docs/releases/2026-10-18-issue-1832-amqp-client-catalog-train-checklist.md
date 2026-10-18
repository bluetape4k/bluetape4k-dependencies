# 2026-10-18 Issue #1832 RabbitMQ 카탈로그 train 체크리스트

상태: **PENDING / 카탈로그 감사, 소비자 해석, 영향 모듈 compile/test 통과; 9개 publisher exact-candidate POM gate 대기**

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
- [ ] **REL-02 — live issue/PR 상태 재확인:** Issue #1832와 두 대상 branch의 PR/issue 중복, milestone, labels, assignee를 PR 생성 직전에 다시 읽는다.
- [x] **REL-03 — 동일 catalog 상태 검증:** Dependencies 후보 catalog 파일 SHA-256 `32887e9060e334600d3ff623ba60bd17fb732f45894d29e0f4a2f1b96924af8b`와 Projects `develop` SHA `d78baa47c6b60bd8e931d61539c2fe939f8cc3f5`에서 `:bluetape4k-testcontainers:dependencyInsight`를 실행했다. `testRuntimeClasspath`는 `com.rabbitmq:amqp-client:5.30.0 -> 5.37.0`을 출력했고 선택 근거는 `Selected by rule`, `By constraint`였다. 이어 `:bluetape4k-testcontainers:compileTestKotlin`이 통과했고 `RabbitMQServerTest` 3개가 통과했다. 첫 실행은 context-mode 자식 프로세스에 Docker 변수가 전달되지 않아 Docker 탐색에서 실패했으며, 확인된 Colima socket을 해당 재실행 프로세스에 설정해 통과했다.
- [x] **REL-04 — 안정 배치:** Maven 안정판 artifact/BOM release가 아니므로 N/A. 이 train은 중앙 catalog와 소비자 pin만 다루며 downstream stable publication을 시작하지 않는다.
- [ ] **REL-05 — 발행 최종 게이트:** Projects 소비자는 `testing/testcontainers/build.gradle.kts:197`의 `testImplementation(bt4k.amqp.client)`다. 후보 catalog로 해당 모듈 POM을 생성한 결과 `com.rabbitmq`/`amqp-client`는 없어 대표 POM에서 공개 dependency 변경이 없음을 확인했다. 다만 catalog train에는 전체 9개 publisher의 exact-candidate POM/Maven model 검증이 필요하므로 이 결과만으로 gate를 통과시키지 않는다. 전체 gate 대기 중이며 Maven publication은 하지 않는다.
- [ ] **Live update 검증:** 병합 후 Dependency Submission을 확인하고, alert #267 페이지에서 실제 Dependabot 재시도를 실행한다. `dependency_not_found`가 계속되면 이를 오류 미해소로 기록하고 Issue #1832를 열린 상태로 유지한다.

## 진행 증거

- Issue #1832: https://github.com/bluetape4k/bluetape4k-projects/issues/1832
- Dependabot alert #267: https://github.com/bluetape4k/bluetape4k-projects/security/dependabot/267
- Projects consumer proof: `./gradlew :bluetape4k-testcontainers:dependencyInsight --dependency com.rabbitmq:amqp-client --configuration testRuntimeClasspath -Pbluetape4kDependenciesCatalogPath=/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/fix/issue-1832-amqp-client-5-37-0/gradle/libs.versions.toml`; resolved `5.30.0 -> 5.37.0` at Projects SHA `d78baa47c6b60bd8e931d61539c2fe939f8cc3f5`.
- Published-POM proof: `:bluetape4k-testcontainers:generatePomFileForBluetape4kPublication` succeeded with the candidate catalog; generated `testing/testcontainers/build/publications/Bluetape4k/pom-default.xml` contains neither `com.rabbitmq` nor `amqp-client`.
- Affected verification: candidate catalog으로 `:bluetape4k-testcontainers:compileTestKotlin`이 통과했다. `DOCKER_HOST=unix:///Users/debop/.colima/default/docker.sock`와 `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`를 확인된 Colima에 한해 테스트 자식 프로세스에 전달한 뒤 `:bluetape4k-testcontainers:test --tests io.bluetape4k.testcontainers.mq.RabbitMQServerTest`가 3개 테스트를 통과했다. Gradle은 기존 Jib `Task.project` configuration-cache 직렬화 경고 12건(고유 4건)을 보고하고 캐시 항목을 폐기했지만 테스트는 성공했다.
- Dependencies governance: latest-stable audit/check, central catalog adoption check, managed catalog alias check, and the targeted Python governance suite (78 tests) passed; `git diff --check` passed.
- Lesson gate: 새 규칙을 만들지 않았다. 기존 `docs/lessons/2026-10-09-gradle-dependabot-central-catalog.md`가 중앙 catalog 수정, consumer 고정 참조, 실제 alert 확인을 이미 다루므로 별도 lesson은 N/A다.
- Dependencies PR: pending
- Catalog tag: pending; merge readiness 승인 전에는 생성하지 않는다.
- Projects PR: pending
- CI / Dependency Submission / 실제 alert 재시도: pending
