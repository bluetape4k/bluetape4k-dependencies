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

## 릴리즈와 Snapshot

`bluetape4k-dependencies`의 catalog version은 `gradle.properties`의 `baseVersion + snapshotVersion`과 맞아야 합니다. `scripts/sync-shared-versions.py`는 source-of-truth block의 `bluetape4k-dependencies` 버전과 `gradle.properties`가 다르면 실패합니다.

릴리즈 준비 시 확인할 항목:

| 항목 | 확인 |
|---|---|
| Downstream sync | `scripts/sync-shared-versions.py --workspace .. --check --summary` |
| Managed module sync | `scripts/sync-managed-catalog.py --check --summary` |
| Local publish | `./gradlew build publishToMavenLocal --no-daemon` |
| Snapshot publish | GitHub Actions `Publish Snapshot` 성공 |

## 장애 대응

| 증상 | 대응 |
|---|---|
| central PR CI에서 shared-version drift 실패 | downstream PR이 먼저 머지되었는지 확인 |
| 특정 repo만 drift가 남음 | 해당 repo가 sync 대상인지, alias 이름이 같은지 확인 |
| Dependabot이 compatibility alias를 잘못 올림 | PR을 닫고 올바른 major-line alias를 갱신 |
| generated module이 README에 없음 | `gradle/libs.versions.toml` generated section과 README 표를 비교 |
| `--write --check`가 실패 | sync script regression 가능성이 있으므로 unittest fixture 추가 후 수정 |
