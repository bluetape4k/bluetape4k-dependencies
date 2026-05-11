# bluetape4k 버전 관리 절차

이 문서는 bluetape4k 조직의 여러 독립 레포지토리에서 공통 버전과 BOM을 관리하는 운영 절차입니다.

## 핵심 모델

`bluetape4k-dependencies`는 두 가지 역할을 합니다.

| 역할 | 대상 | 결과물 |
|---|---|---|
| BOM | bluetape4k artifact dependency resolution | `io.github.bluetape4k:bluetape4k-dependencies` |
| Version catalog | Gradle plugin/library alias와 bluetape4k artifact alias | `io.github.bluetape4k:bluetape4k-version-catalog` |

중요한 점은 shared version alias가 동적으로 참조되는 구조가 아니라는 것입니다.

```text
bluetape4k-dependencies/gradle/libs.versions.toml
        |
        | scripts/sync-shared-versions.py --write
        v
각 대상 repo의 gradle/libs.versions.toml
```

즉, `bluetape4k-dependencies`가 source of truth이고, 대상 레포지토리들의 `libs.versions.toml`은 sync script로 갱신되는 materialized copy입니다.

## 관리 대상

`scripts/sync-shared-versions.py`의 기본 대상은 다음 레포지토리입니다.

| 레포지토리 | 비고 |
|---|---|
| `bluetape4k-projects` | 핵심 라이브러리 기준 repo |
| `bluetape4k-aws` | AWS 통합 |
| `bluetape4k-experimental` | 실험 repo, sync 대상에는 포함 |
| `bluetape4k-exposed` | Exposed 통합 |
| `bluetape4k-graph` | Graph 통합 |
| `bluetape4k-image` | Image 통합 |
| `bluetape4k-javers` | Javers 통합 |
| `bluetape4k-leader` | Leader election 통합 |
| `bluetape4k-text` | Text/tokenizer 통합 |
| `bluetape4k-workshop` | workshop 중 sync 대상 |

`ocean-workshop`과 `kotlin-dev-agent`는 기본 sync 대상에서 제외합니다.

## 버전 변경 절차

공통 dependency/plugin 버전을 바꿀 때는 아래 순서를 지킵니다.

1. `bluetape4k-dependencies`에서 새 브랜치를 만듭니다.
2. `gradle/libs.versions.toml`의 source-of-truth block을 수정합니다.
3. 대상 레포지토리 catalog를 갱신합니다.

```bash
scripts/sync-shared-versions.py --workspace .. --write --check --summary
```

4. 변경된 downstream repo마다 PR을 만들고 CI를 확인합니다.
5. downstream PR을 먼저 모두 머지합니다.
6. `bluetape4k-dependencies`에서 다시 drift check를 실행합니다.

```bash
scripts/sync-shared-versions.py --workspace .. --check --summary
```

7. `bluetape4k-dependencies` PR을 마지막에 만들고 머지합니다.

이 순서가 중요한 이유는 `bluetape4k-dependencies` CI가 downstream `develop` branch를 다시 clone해서 drift를 검사하기 때문입니다. downstream PR이 먼저 머지되지 않으면 central PR은 실패하는 것이 정상입니다.

## 검증 명령

스크립트는 반복 운영 도구이므로, 변경 시 다음 검증을 기본으로 수행합니다.

```bash
python3 -m py_compile scripts/sync-managed-catalog.py scripts/sync-shared-versions.py tests/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
scripts/sync-managed-catalog.py --check --summary
scripts/sync-shared-versions.py --workspace .. --check --summary
./gradlew build publishToMavenLocal --no-daemon
```

문서만 수정한 경우에도 최소한 아래는 확인합니다.

```bash
git diff --check
scripts/sync-managed-catalog.py --check --summary
scripts/sync-shared-versions.py --workspace .. --check --summary
```

## Compatibility-line alias 규칙

major line이 공존하는 dependency는 alias를 합치지 않습니다.

| Alias | 의미 |
|---|---|
| `kafka3` | Kafka 3.x 계열 |
| `kafka4` | Kafka 4.x 계열 |
| `jackson2` | Jackson 2.x 계열 |
| `jackson3` | Jackson 3.x 계열 |
| `spring-boot3` | Spring Boot 3.x 계열 |
| `spring-boot4` | Spring Boot 4.x 계열 |
| `spring-kafka` | Spring Kafka 3.x 계열 |
| `spring-kafka4` | Spring Kafka 4.x 계열 |
| `ignite` | Apache Ignite 2.x 계열 |
| `ignite3` | Apache Ignite 3.x 계열 |

Dependabot PR이 `kafka3`를 4.x로 올리거나, `spring-kafka`를 4.x로 올리면 그대로 머지하지 않습니다. 필요한 경우 `kafka4`, `spring-kafka4` 같은 별도 alias를 갱신합니다.

## BOM managed module 갱신

Sibling repo의 module include가 바뀌면 BOM과 version catalog alias도 갱신해야 합니다.

```bash
scripts/sync-managed-catalog.py --write --check --summary
```

이 스크립트는 sibling repo의 `settings.gradle.kts`를 읽어서 다음을 갱신합니다.

| 파일 | 갱신 내용 |
|---|---|
| `gradle/libs.versions.toml` | bluetape4k artifact catalog alias |
| `build.gradle.kts` | java-platform `api(...)` constraints |

`README.md`와 `README.ko.md`의 managed module 표도 generated catalog와 맞춰 갱신합니다.

## Dependabot PR 처리

Dependabot PR은 자동으로 맞다고 가정하지 않습니다.

1. compatibility-line alias가 깨졌는지 먼저 확인합니다.
2. 같은 alias가 여러 repo에 있으면 `bluetape4k-dependencies` source-of-truth에서 먼저 결정합니다.
3. source-of-truth 변경 후 sync script로 downstream repo PR을 일괄 생성합니다.
4. PR별 CI를 확인합니다.
5. downstream이 모두 green이면 central PR을 마지막에 머지합니다.

특정 repo 하나에만 Dependabot PR이 생기고 `bluetape4k-projects` 또는 source-of-truth에는 없으면, 그 PR만 단독 머지하지 말고 shared alias인지 먼저 확인합니다.

## Snapshot 배포와 공식 릴리즈

`bluetape4k-dependencies`의 catalog version은 `gradle.properties`의 `baseVersion + snapshotVersion`과 맞아야 합니다. `scripts/sync-shared-versions.py`는 source-of-truth block의 `bluetape4k-dependencies` 버전과 `gradle.properties`가 다르면 실패합니다.

### Snapshot 배포

Snapshot 배포는 개발 중인 최신 상태를 검증하거나 다른 repo에서 미리 참조하기 위한 배포입니다.

Snapshot 배포 시에는 다음 값을 유지합니다.

| 위치 | 예시 |
|---|---|
| upstream repo `gradle.properties` | `baseVersion=0.1.0`, `snapshotVersion=-SNAPSHOT` |
| `bluetape4k-dependencies/gradle/libs.versions.toml` upstream ref | `bluetape4k-leader = "0.1.0-SNAPSHOT"` |
| `bluetape4k-dependencies/gradle.properties` | `baseVersion=1.0.0`, `snapshotVersion=-SNAPSHOT` |
| source-of-truth block | `bluetape4k-dependencies = "1.0.0-SNAPSHOT"` |

Snapshot 배포에서는 upstream artifact와 BOM/catalog가 모두 snapshot repository를 가리켜도 됩니다.

### 공식 릴리즈 원칙

공식 릴리즈 BOM은 snapshot artifact를 가리키면 안 됩니다. `bluetape4k-dependencies`를 release로 배포할 때는 BOM이 관리하는 `bluetape4k-*` upstream version ref에서 `-SNAPSHOT`을 제거해야 합니다.

단, `-SNAPSHOT` 제거는 해당 upstream release artifact가 Central에 존재할 때만 해야 합니다. 예를 들어 `bluetape4k-leader = "0.1.0"`으로 바꾸는 것은 “BOM이 `io.github.bluetape4k.leader:*:0.1.0` release artifact를 관리한다”는 뜻입니다. 이것은 `bluetape4k-leader` repo의 `gradle.properties`를 자동으로 바꾸지 않습니다.

### Pre-release 배포

정식 버전으로 확정하기 전에도 `1.0.0-Beta1`, `1.0.0-RC1` 같은 pre-release version을 Central Portal에 배포할 수 있습니다. Maven Central은 version 문자열을 기준으로 release artifact를 저장하므로, 이런 버전도 snapshot이 아닌 immutable release artifact입니다.

Pre-release는 다음 상황에 사용합니다.

- [ ] 여러 repo를 실제 Central artifact 기준으로 검증해야 합니다.
- [ ] 정식 `1.0.0`으로 고정하기 전에 downstream 사용성을 먼저 확인해야 합니다.
- [ ] snapshot repository가 아니라 Maven Central 경로에서 소비되는지 확인해야 합니다.

Pre-release를 배포할 때도 아래 원칙은 동일합니다.

- [ ] 같은 pre-release version은 다시 배포할 수 없습니다. `1.0.0-Beta1`을 수정해야 하면 `1.0.0-Beta2`를 새로 배포합니다.
- [ ] `bluetape4k-dependencies` release BOM이 `1.0.0-Beta1` upstream artifact를 참조한다면, 해당 upstream artifact가 Central에 먼저 존재해야 합니다.
- [ ] 정식 release BOM은 최종적으로 정식 upstream version을 참조해야 합니다. 예: `1.0.0-Beta1` -> `1.0.0`.
- [ ] pre-release와 정식 release는 서로 다른 version matrix로 기록합니다.

예시:

```toml
bluetape4k-dependencies = "1.1.0-Beta1"
bluetape4k-core         = "1.8.0-Beta1"
bluetape4k-aws          = "1.8.0-Beta1"
bluetape4k-leader       = "0.1.0-Beta1"
```

이 경우 `bluetape4k-dependencies:1.1.0-Beta1`은 정식 `1.1.0`이 아니지만 Central에 배포된 release artifact입니다. 정식 `1.1.0` 배포 시에는 upstream ref를 다시 정식 version matrix로 바꾸고 동일한 missing-only 절차를 반복합니다.

공식 릴리즈는 아래 체크리스트 순서로 진행합니다. 실행자는 체크리스트를 채우고, 검증자는 release matrix, Central 존재 여부, CI/release workflow 결과를 확인합니다.

#### 1. 릴리즈 요청 정리

- [ ] `bluetape4k-dependencies` release version을 기록합니다.
- [ ] BOM이 참조할 모든 upstream alias와 version을 release matrix로 정규화합니다.
- [ ] 요청에 중복 alias가 있으면 하나로 정리합니다.
- [ ] BOM 대상인데 요청에서 빠진 alias가 있는지 확인합니다. 예: `bluetape4k-text`.
- [ ] 빠진 alias는 release matrix에 추가하거나, 이번 release BOM에서 제외할 별도 결정을 기록합니다.

#### 2. Central 존재 여부 확인

- [ ] Maven Central 또는 Central Portal에서 각 upstream group/artifact/version을 조회합니다.
- [ ] 이미 존재하는 version은 `exists`로 표시하고 release action 대상에서 제외합니다.
- [ ] 존재하지 않는 version만 `missing`으로 표시합니다.
- [ ] 같은 version을 다시 배포하지 않는다는 점을 확인합니다. Maven Central release artifact는 같은 version으로 재배포할 수 없습니다.

#### 3. Missing upstream release

- [ ] `missing` repo에 release tag가 있는지 확인합니다.
- [ ] tag의 `gradle.properties`가 `baseVersion=<releaseVersion>`, `snapshotVersion=`인지 확인합니다.
- [ ] `missing` repo/version만 GitHub Actions `Publish Release` workflow를 실행합니다.
- [ ] 실행한 release workflow가 모두 green인지 확인합니다.
- [ ] `missing` artifact가 모두 Central에서 조회되는지 다시 확인합니다.

#### 4. `bluetape4k-dependencies` release 반영

- [ ] `gradle/libs.versions.toml`에서 release BOM이 참조할 upstream ref의 `-SNAPSHOT`을 제거합니다.
- [ ] source-of-truth block의 `bluetape4k-dependencies` 값을 release version으로 변경합니다.
- [ ] `gradle.properties`를 release version으로 맞춥니다. 예: `baseVersion=1.1.0`, `snapshotVersion=`.
- [ ] `scripts/sync-managed-catalog.py --check --summary`를 실행합니다.
- [ ] `scripts/sync-shared-versions.py --workspace .. --check --summary`를 실행합니다.
- [ ] `./gradlew build publishToMavenLocal --no-daemon`로 로컬 release BOM/catalog를 검증합니다.

#### 5. PR, CI, 배포

- [ ] `bluetape4k-dependencies` release PR을 만들고 `debop`에게 할당합니다.
- [ ] PR CI가 green인지 확인합니다.
- [ ] PR을 merge하고 로컬 `develop`을 동기화합니다.
- [ ] `bluetape4k-dependencies` GitHub Actions `Publish Release` workflow를 실행합니다.
- [ ] release workflow가 green인지 확인합니다.
- [ ] release BOM과 version catalog가 Central에서 조회되는지 확인합니다.

#### 6. 다음 개발 사이클 준비

- [ ] 필요한 upstream repo를 다음 snapshot version으로 올립니다.
- [ ] `bluetape4k-dependencies` upstream refs를 다음 snapshot으로 갱신합니다.
- [ ] `bluetape4k-dependencies` 자체 version도 다음 snapshot으로 올립니다.
- [ ] drift check, CI, snapshot publish 결과를 확인합니다.

### 실제 배포 예시: `bluetape4k-dependencies` 1.1.0

요청 예시:

```text
이번에 dependencies 1.1.0을 릴리즈하자.
bluetape4k-core = 1.8.0
aws = 1.8.0
exposed = 1.8.0
image = 1.8.0
graph = 0.3.0
javers = 1.8.0
leader = 0.1.0
```

운영자는 먼저 이 요청을 release matrix로 정규화합니다.

| Source alias | Group | Version |
|---|---|---|
| `bluetape4k-core` | `io.github.bluetape4k` | `1.8.0` |
| `bluetape4k-aws` | `io.github.bluetape4k.aws` | `1.8.0` |
| `bluetape4k-exposed` | `io.github.bluetape4k.exposed` | `1.8.0` |
| `bluetape4k-image` | `io.github.bluetape4k.image` | `1.8.0` |
| `bluetape4k-graph` | `io.github.bluetape4k.graph` | `0.3.0` |
| `bluetape4k-javers` | `io.github.bluetape4k.javers` | `1.8.0` |
| `bluetape4k-leader` | `io.github.bluetape4k.leader` | `0.1.0` |

`bluetape4k-text`도 BOM 대상입니다. 요청에 빠져 있으면 release BOM에서 어떤 version을 가리킬지 확인해야 합니다. release BOM이 snapshot을 가리키면 안 되므로, `bluetape4k-text`를 release matrix에 추가하거나 해당 alias를 BOM에서 의도적으로 제외하는 별도 결정을 해야 합니다.

다음 체크리스트를 그대로 채워서 진행합니다.

#### 1. 요청 정규화

- [ ] `bluetape4k-dependencies = 1.1.0`을 release target으로 기록합니다.
- [ ] `exposed`처럼 요청에 중복된 alias가 있으면 하나로 정리합니다.
- [ ] 요청에 없는 `bluetape4k-text` version을 확인합니다.
- [ ] 최종 release matrix를 확정합니다.

#### 2. Central 확인

| Alias | Version | Central | Action |
|---|---:|---|---|
| `bluetape4k-core` | `1.8.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-aws` | `1.8.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-exposed` | `1.8.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-image` | `1.8.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-graph` | `0.3.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-javers` | `1.8.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-leader` | `0.1.0` | `exists` 또는 `missing` | `exists`면 제외, `missing`이면 release |
| `bluetape4k-text` | `확인 필요` | `exists` 또는 `missing` | version 결정 후 판정 |

예를 들어 `bluetape4k-core:1.8.0`, `bluetape4k-aws:1.8.0`, `bluetape4k-image:1.8.0`은 이미 있고, `bluetape4k-graph:0.3.0`, `bluetape4k-leader:0.1.0`만 없다면 `bluetape4k-graph`와 `bluetape4k-leader`만 release합니다.

#### 3. Missing-only upstream release

- [ ] Central 값이 `missing`인 repo만 release action을 실행합니다.
- [ ] release action이 green인지 확인합니다.
- [ ] release한 artifact가 Central에서 조회되는지 확인합니다.
- [ ] Central 값이 `exists`였던 repo는 다시 release하지 않았는지 확인합니다.

#### 4. Dependencies release 변경

missing upstream release가 끝나면 `bluetape4k-dependencies`를 다음처럼 변경합니다.

```toml
bluetape4k-dependencies = "1.1.0"
bluetape4k-core         = "1.8.0"
bluetape4k-aws          = "1.8.0"
bluetape4k-exposed      = "1.8.0"
bluetape4k-image        = "1.8.0"
bluetape4k-graph        = "0.3.0"
bluetape4k-javers       = "1.8.0"
bluetape4k-leader       = "0.1.0"
```

그리고 `gradle.properties`도 release version으로 맞춥니다.

```properties
baseVersion=1.1.0
snapshotVersion=
```

그 뒤 아래 순서로 `bluetape4k-dependencies`를 마지막에 배포합니다.

- [ ] `scripts/sync-managed-catalog.py --check --summary`
- [ ] `scripts/sync-shared-versions.py --workspace .. --check --summary`
- [ ] `./gradlew build publishToMavenLocal --no-daemon`
- [ ] release PR 생성 및 `debop` 할당
- [ ] PR CI green 확인
- [ ] PR merge 및 로컬 `develop` 동기화
- [ ] `Publish Release` workflow 실행
- [ ] release workflow green 확인
- [ ] `bluetape4k-dependencies:1.1.0`과 `bluetape4k-version-catalog:1.1.0` Central 조회 확인

### 공식 릴리즈 체크리스트

- [ ] 모든 `bluetape4k-*` version ref가 실제 release artifact로 존재합니다.
- [ ] Central에 없는 upstream version만 release action을 실행했습니다.
- [ ] release BOM의 managed `bluetape4k-*` ref에 `-SNAPSHOT`이 없습니다.
- [ ] `gradle.properties`와 source-of-truth block의 `bluetape4k-dependencies` 값이 일치합니다.
- [ ] `scripts/sync-shared-versions.py --workspace .. --check --summary`가 통과합니다.
- [ ] `scripts/sync-managed-catalog.py --check --summary`가 통과합니다.
- [ ] `./gradlew build publishToMavenLocal --no-daemon`가 통과합니다.
- [ ] GitHub Actions `Publish Release`가 성공했습니다.

### 릴리즈 후 다음 개발 사이클

공식 릴리즈가 끝나면 다음 개발 cycle을 시작하기 위해 version을 다시 snapshot으로 올립니다.

1. upstream repo들의 다음 개발 버전을 설정합니다.
   - 예: `baseVersion=0.1.1`, `snapshotVersion=-SNAPSHOT`
2. `bluetape4k-dependencies/gradle/libs.versions.toml`의 upstream refs를 다음 snapshot으로 갱신합니다.
   - 예: `bluetape4k-leader = "0.1.1-SNAPSHOT"`
3. `bluetape4k-dependencies` 자체도 다음 snapshot으로 갱신합니다.
   - 예: `baseVersion=1.0.1`, `snapshotVersion=-SNAPSHOT`
   - source-of-truth block: `bluetape4k-dependencies = "1.0.1-SNAPSHOT"`
4. drift check와 CI를 통과시킨 뒤 snapshot publish를 확인합니다.

## 장애 대응

| 증상 | 대응 |
|---|---|
| central PR CI에서 shared-version drift 실패 | downstream PR이 먼저 머지되었는지 확인 |
| 특정 repo만 drift가 남음 | 해당 repo가 sync 대상인지, alias 이름이 같은지 확인 |
| Dependabot이 compatibility alias를 잘못 올림 | PR을 닫고 올바른 major-line alias를 갱신 |
| generated module이 README에 없음 | `gradle/libs.versions.toml` generated section과 README 표를 비교 |
| `--write --check`가 실패 | sync script regression 가능성이 있으므로 unittest fixture 추가 후 수정 |
| release BOM이 snapshot artifact를 참조 | upstream release 완료 여부 확인 후 `libs.versions.toml` ref에서 `-SNAPSHOT` 제거 |
