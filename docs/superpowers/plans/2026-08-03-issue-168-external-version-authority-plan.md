# Issue #168 외부 버전 권한 중앙화 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 9개 관리 library repository의 외부 dependency/plugin version 선언 864건을 중앙 catalog authority, 증명된 BOM 관리, 호환 라인 또는 구조적 예외 중 하나로 귀속하고, 동일 후보 catalog SHA에서 검증 가능한 `blocked-until-tag` handoff를 만든다.

**Architecture:** 중앙 Python 모델이 catalog·Gradle 선언을 deterministic inventory와 disposition으로 정규화한다. 별도 candidate 모델이 10개 worktree topology, catalog lock, cache manifest와 receipt chain을 고정하고, credential-free macOS sandbox runner가 G1–G8을 순서대로 실행한다. downstream 변환은 inventory/disposition이 확정된 뒤에만 수행하며 immutable catalog ref가 없으므로 이번 실행의 정상 정지점은 `blocked-until-tag`다.

**Tech Stack:** Python 3 표준 라이브러리, `unittest`, Gradle Kotlin DSL/version catalog, Maven effective model, macOS `sandbox-exec`, SHA-256, JSON/TOML, Git worktree.

---

## 실행 경계와 승인

- Work type: Type A — multi-repository catalog authority migration.
- Issue: `bluetape4k/bluetape4k-dependencies#168`, milestone `1.4.0`.
- 중앙 branch/worktree: `issue/168-central-catalog-authority` / `/Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority`.
- 중앙 base: `2d0b9185f4e8f4d1989fd934f40a96cccb8b4f62` (`develop`).
- 승인된 설계: `docs/superpowers/specs/2026-08-03-issue-168-external-version-authority-design.md`.
- 허용: local worktree 생성, local 파일 변경, test/build/analysis, Lore commit.
- 금지: push, PR, merge, tag, workflow dispatch, Maven publish, release, branch/worktree 삭제.
- 정상 정지점: path-mode G1/G3–G8 PASS와 G2 path/SHA PASS를 확보하고, immutable catalog tag가 필요한 declared-ref 항목만 `blocked-until-tag`로 남긴다.

## 파일 책임 지도

| 책임 | 파일 |
| --- | --- |
| stable identity, catalog/Gradle parsing, accessor collision | `scripts/catalog_authority.py` |
| existing adoption CLI and inventory/disposition integration | `scripts/sync-shared-versions.py` |
| candidate map, catalog/cache lock, atomic receipt ledger | `scripts/catalog_candidate.py` |
| G1–G8 manifest-only sandbox execution | `scripts/run-catalog-validation.py` |
| POM generation/effective-model candidate mode | `scripts/verify-publication-poms.py` |
| central aliases, version lines, compatibility families | `gradle/libs.versions.toml` |
| every authority disposition | `config/central-catalog-authority-dispositions.json` |
| intentional resolved-version changes | `config/central-catalog-version-deltas.json` |
| compatibility/structural exceptions | `config/central-catalog-exceptions.toml` |
| downstream Dependabot ownership | `scripts/sync-dependabot-ignores.py`, `.github/dependabot.yml` in each candidate repo |
| CI governance | `.github/workflows/ci.yml`, `tests/test_ci_catalog_governance.py` |
| operator contract and candidate receipt | `docs/version-management.ko.md`, `docs/releases/2026-08-03-issue-168-candidate-ledger.md` |
| unit/fixture proof | `tests/test_catalog_authority.py`, `tests/test_catalog_candidate.py`, `tests/test_run_catalog_validation.py`, existing affected test files |

## Spec 추적성

| 설계 요구 | 구현 task | 검증 |
| --- | --- | --- |
| 864 선언과 43 hard-coded 후보의 one-to-one disposition | 1–3, 8 | inventory count, orphan/duplicate disposition tests |
| stable `(authority-id, line-id)`와 representation lineage | 1 | model unit tests, before/after reconciliation fixture |
| accessor/synthetic namespace collision 차단 | 1 | parser fixtures, Gradle `help` |
| exact 9-repository topology와 catalog lock | 4 | candidate map/lock negative tests, G1/G2 receipt |
| credential-free runner와 forbidden task 차단 | 5 | sandbox/preflight negative tests |
| POM/effective-model 보장 | 6 | publication POM unit tests, G6 |
| central alias/version authority 및 호환 라인 | 7 | checksum, catalog parser, graph delta |
| downstream direct adoption/hard-coded 제거 | 8 | repository literal scan, G7/G8 |
| Dependabot/CI/runbook/rollback | 9–10 | generated ignore check, CI tests, ledger read-back |
| release 경계 | 11 | final `blocked-until-tag`, no remote side effect proof |

### Task 1: stable authority 모델과 accessor parser를 RED/GREEN으로 추가

**Complexity:** high
**Depends on:** approved spec
**Write scope:** central repository only

**Files:**

- Create: `scripts/catalog_authority.py`
- Create: `tests/test_catalog_authority.py`
- Create: `tests/fixtures/catalog-authority/central/gradle/libs.versions.toml`
- Create: `tests/fixtures/catalog-authority/bluetape4k-projects/gradle/libs.versions.toml`
- Create: `tests/fixtures/catalog-authority/bluetape4k-projects/build.gradle.kts`

- [ ] **Step 1: identity와 collision 실패 테스트 작성**

```python
def test_hard_coded_to_catalog_keeps_authority_identity(self) -> None:
    before = authority_id("bluetape4k-projects", "library", "org.example:demo")
    after = authority_id("bluetape4k-projects", "library", "org.example:demo")
    self.assertEqual(before, after)

def test_compatibility_lines_keep_distinct_line_identity(self) -> None:
    self.assertNotEqual(
        authority_key("same-authority", "spring-boot-3"),
        authority_key("same-authority", "spring-boot-4"),
    )

def test_synthetic_and_normalized_accessor_collisions_are_rejected(self) -> None:
    with self.assertRaisesRegex(ValueError, "reserved accessor namespace"):
        validate_accessor_aliases(["plugins-foo"])
    with self.assertRaisesRegex(ValueError, "accessor collision"):
        validate_accessor_aliases(["foo-bar", "foo.bar"])
```

- [ ] **Step 2: RED 확인**

Run: `python3 -m unittest tests/test_catalog_authority.py -v`
Expected: import failure for missing `scripts/catalog_authority.py`.

- [ ] **Step 3: immutable subject identity와 parser 최소 구현**

```python
@dataclasses.dataclass(frozen=True)
class AuthorityRecord:
    authority_id: str
    line_id: str
    occurrence_id: str
    repository: str
    subject_kind: str
    declaration_form: str
    coordinate_or_plugin_id: str
    alias: str
    source_path: str
    source_line: int
    declared_version: str
    resolved_version: str

def authority_id(repository: str, subject_kind: str, coordinate: str) -> str:
    payload = "\0".join((repository, subject_kind, coordinate)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def authority_key(stable_authority_id: str, line_id: str) -> str:
    if not re.fullmatch(r"(?:default|[a-z][a-z0-9]*(?:-[a-z0-9]+)*)", line_id):
        raise ValueError("invalid canonical line-id")
    return f"{stable_authority_id}:{line_id}"
```

`validate_accessor_aliases()`는 lowercase/hyphen grammar, Kotlin reserved word, `plugins`/`versions`/`bundles`, library/plugin/bundle/version cross-tree collision을 모두 fail-closed로 검사한다. Catalog parser는 `tomllib`만 사용하고 dynamic/range version을 거부한다.

- [ ] **Step 4: GREEN과 회귀 확인**

Run: `python3 -m unittest tests/test_catalog_authority.py tests/test_sync_shared_versions.py -v`
Expected: all tests pass; existing compatibility/adoption tests remain green.

- [ ] **Step 5: Lore commit 후보 준비**

```text
Make catalog authority identity stable across declaration migrations

Constraint: Compatibility lines must remain distinct without binding identity to mutable aliases or versions
Confidence: high
Scope-risk: moderate
Tested: python3 -m unittest tests/test_catalog_authority.py tests/test_sync_shared_versions.py -v
Not-tested: downstream Gradle accessors before catalog migration
```

**Rollback/rerun:** parser fixture 실패 시 새 module과 test만 repair하고 Task 2를 시작하지 않는다.

### Task 2: deterministic inventory와 disposition contract 추가

**Complexity:** high
**Depends on:** Task 1
**Write scope:** central scripts/config/tests

**Files:**

- Modify: `scripts/sync-shared-versions.py`
- Modify: `tests/test_sync_shared_versions.py`
- Create: `config/central-catalog-authority-dispositions.json`
- Create: `tests/fixtures/catalog-authority/dispositions-valid.json`
- Create: `tests/fixtures/catalog-authority/dispositions-orphan.json`

- [ ] **Step 1: inventory/disposition RED tests 작성**

다음 exact CLI contract를 test한다.

```bash
scripts/sync-shared-versions.py \
  --workspace /Users/debop/work/bluetape4k \
  --inventory-out build/catalog-authority/baseline/inventory.json \
  --summary-out build/catalog-authority/baseline/summary.json \
  --dispositions config/central-catalog-authority-dispositions.json \
  --format json
```

Assertions: canonical key ordering, 864 catalog occurrences, 43 hard-coded candidate baseline, stable occurrence lineage, missing/orphan/duplicate pair rejection, invalid evidence/disposition combination rejection, `bom-managed-versionless` POM evidence requirement, `structural-repo-owned` same-repository issue/review date requirement.

- [ ] **Step 2: RED 확인**

Run: `python3 -m unittest tests/test_sync_shared_versions.py -v`
Expected: argparse rejects `--inventory-out`, `--summary-out`, `--dispositions`.

- [ ] **Step 3: report-only inventory 구현**

`sync-shared-versions.py`는 `catalog_authority.py`를 load해 workspace를 repository enum 순서로 scan하고, before/after record를 authority pair로 group한 뒤 disposition manifest와 exact set equality를 검사한다. Deterministic writer는 다음 구현을 사용한다.

```python
def canonical_json_bytes(value: object) -> bytes:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("utf-8")

def write_report(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
```

Inventory는 repository/path/line/alias 순서로 정렬한 뒤 writer에 전달하고 report-only semantics를 유지한다. `--write`는 계속 deprecated/no-op이다.

- [ ] **Step 4: 실제 baseline 생성과 count read-back**

Run: 위 exact CLI command.
Expected: inventory and summary created; summary reports the approved audit baseline. Count drift가 있으면 구현을 계속하지 않고 source path별 drift를 설계 감사치와 reconcile한다.

- [ ] **Step 5: baseline disposition manifest를 실제 pair로 채우고 strict validation 통과**

각 record는 `central-direct`, `central-version-local-alias`, `bom-managed-versionless`, `compatibility-line`, `structural-repo-owned` 중 하나와 owner/evidence를 가진다. `compatibility-line`은 repository, local key/alias, central key/alias, subject-kind, exact coordinate/plugin ID, expected declared/resolved version, canonical `line-id`, evidence SHA를 모두 요구하며 wildcard/dynamic/range selector와 누락 필드를 거부한다. 33개 conflict 각각이 정확히 하나의 compatibility/alignment record로 매핑되는 fixture와 count guard를 둔다. 미결 항목은 허위 disposition으로 채우지 않고 Task 7 전까지 guard를 실패 상태로 유지한다.

`baseline/` 출력은 pre-candidate audit evidence다. Candidate inventory는 manifest의 central raw catalog SHA에서 계산한 `build/catalog-authority/<catalog-sha256>/inventory.json`과 `summary.json`만 canonical하며, `--output-root build/catalog-authority/<catalog-sha256>`와 `--catalog-sha <64-lowercase-hex>`가 catalog bytes와 불일치하면 쓰기 전에 실패한다. G3와 pre-G8 receipt는 두 artifact SHA를 필수로 bind한다.

**Rollback/rerun:** count 또는 lineage drift가 생기면 inventory artifact를 삭제하지 않고 failure evidence로 보존하고 parser를 repair한 뒤 전체 inventory를 다시 생성한다.

### Task 3: 10개 candidate worktree와 repository map 준비

**Complexity:** medium
**Depends on:** Task 2 baseline
**Write scope:** 각 repository의 `.worktrees/issue-168-central-catalog-authority`

- [ ] **Step 1: default checkout 보호 확인**

각 repository에서 `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, `git rev-parse origin/develop`을 읽는다. dirty/ahead/detached/mismatch repository는 수정하지 않고 candidate map에서 `blocked`로 기록한다.

- [ ] **Step 2: clean repository만 isolated worktree 생성**

Branch는 모두 `issue/168-central-catalog-authority`, path는 각 repository의 `.worktrees/issue-168-central-catalog-authority`, base는 exact `origin/develop`이다. 기존 branch/worktree가 있으면 새로 덮어쓰지 않고 current state를 검증한다.

- [ ] **Step 3: repository map 작성**

Create: `build/catalog-authority/prepare/candidate-repositories.json`. Versioned schema는 top-level exact fields `schema_version: 1`, `central`, `repositories`만 허용한다. `repositories` map의 exact enum은 `projects`, `aws`, `experimental`, `exposed`, `graph`, `image`, `javers`, `leader`, `text`의 9개뿐이며, central worktree metadata는 별도 `central` object다. Central/downstream entry는 canonical root/catalog path, approved origin, branch, base SHA, expected HEAD, clean boolean을 가진다. Task 4의 단일 `load_repository_map_v1()`가 legacy flat map을 거부하고, `sync-shared-versions.py`와 `sync-managed-catalog.py`는 자체 loader 대신 이 adapter를 import한다.

- [ ] **Step 4: map artifact read-back**

Run: `python3 -m json.tool build/catalog-authority/prepare/candidate-repositories.json` followed by NUL-safe `git status --porcelain=v1 -z` and `git rev-parse` read-back for every entry.
Expected: valid JSON; exact 9 downstream entries plus one top-level central object; every declared branch/base/HEAD/path matches the observed worktree and no default checkout changed.

**Rollback/rerun:** worktree 생성 실패 시 생성된 clean worktree를 삭제하지 않고 map을 `partial`로 유지한다. default checkout과 branch는 변경하지 않는다.

### Task 4: candidate map, catalog lock, receipt chain 구현

**Complexity:** high
**Depends on:** Task 3
**Write scope:** central scripts/tests/build evidence

**Files:**

- Create: `scripts/catalog_candidate.py`
- Create: `tests/test_catalog_candidate.py`
- Create: `tests/fixtures/catalog-candidate/repository-map-valid.json`
- Create: `tests/fixtures/catalog-candidate/repository-map-traversal.json`
- Create: `docs/releases/2026-08-03-issue-168-candidate-ledger.md`
- Modify: `scripts/sync-managed-catalog.py`
- Modify: `tests/test_sync_managed_catalog.py`
- Modify: `scripts/sync-dependabot-ignores.py`
- Modify: `tests/test_sync_dependabot_ignores.py`

- [ ] **Step 1: G1/G2/ledger RED tests 작성**

Cover: versioned v1 envelope/exact enum, legacy flat-map rejection, shared loader behavior across `sync-shared-versions.py`, `sync-managed-catalog.py`, `sync-dependabot-ignores.py`, canonical regular non-symlink path, workspace containment, branch/base/HEAD/clean state, approved origin, raw catalog SHA, immutable 40/64-char ref peel, path/ref check separation, manifest no-follow owner/mode/path/bytes revalidation, cache-manifest binding, atomic receipt chain and interrupted-write rejection. 각 CLI/fixture는 동일 `load_repository_map_v1()`를 호출해 unknown field, exact 9-entry enum, canonical path, approved origin, base/expected HEAD와 clean state를 검증하며 default/broad sibling discovery를 금지한다. Non-absolute, symlinked, outside-workspace, unknown-field and post-create mutated manifest inputs fail before child launch. Ledger tests include initialization before any downstream mutation, monotonic sequence/parent hash, stale-writer fencing, crash/interleaving rejection, same-manifest resume, retry invalidation, and deterministic merge of immutable per-job receipts. G1/G2 provenance fixture requires a trusted-worktree review receipt and local CI-provenance artifact, both bound to the exact central commit/workflow SHA and reviewer/check command/output SHA; missing, stale or mismatched evidence produces zero-child `BLOCKED`.

- [ ] **Step 2: RED 확인**

Run: `python3 -m unittest tests/test_catalog_candidate.py -v`
Expected: missing `scripts/catalog_candidate.py` import failure.

- [ ] **Step 3: candidate primitives 구현**

모든 JSON input은 unknown field를 거부한다. `load_repository_map_v1()`은 `schema_version: 1`, top-level `central`과 exact 9-entry `repositories`만 허용하고 `CandidateRepository` tuple을 enum 순서로 반환한다. `sync-shared-versions.py`의 기존 flat-map loader는 제거하고 `sync-shared-versions.py`, `sync-managed-catalog.py`, `sync-dependabot-ignores.py` 세 CLI/fixture가 이 shared adapter와 같은 envelope/validation을 사용한다. `create_catalog_lock()`은 central/downstream raw catalog digest와 path/ref observation을 분리한다. `create_candidate_manifest()`는 repository/disposition/cache input SHA를 canonical JSON에 bind한다. Atomic writer는 다음 순서를 그대로 사용한다.

```python
def write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        if path.read_bytes() != payload:
            raise RuntimeError("atomic write read-back mismatch")
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
```

Coordinator만 aggregate ledger를 쓰는 single-writer다. G6–G8 worker는 candidate/stage/job identity와 immutable input SHA가 포함된 개별 receipt만 atomic write하고, coordinator가 canonical job order로 검증·merge한다. Aggregate record는 monotonic sequence, prior-record SHA, manifest/catalog/cache/disposition SHA와 fencing token을 포함한다. Interrupted same-stage resume는 PASS receipt의 input/output SHA를 다시 검증해 재사용하고, incomplete/FAILED/stale-fence artifact는 evidence로 보존하되 재사용하지 않는다.

- [ ] **Step 4: GREEN 확인**

Run: `python3 -m unittest tests/test_catalog_candidate.py tests/test_sync_managed_catalog.py tests/test_sync_shared_versions.py tests/test_sync_dependabot_ignores.py -v`
Expected: all pass.

- [ ] **Step 5: prepare ledger 초기화와 fixture read-back**

어떤 downstream 변환보다 먼저 durable `docs/releases/2026-08-03-issue-168-candidate-ledger.md`와 machine-readable chained record를 atomic 초기화한다. Candidate ID, central+9 downstream base/expected HEAD, repository별 last-known-good SHA, canonical source diff hash, repository map/manifest/catalog lock/disposition/cache SHA를 기록하고 즉시 read-back한다. Canonical diff hash는 NUL-safe tracked/untracked path 목록과 file bytes로 계산하며 `build/catalog-authority/**`와 candidate ledger 자체는 제외하고, 제외된 ledger는 prior/current receipt SHA로 별도 bind해 자기참조를 피한다. 이후 state transition과 local commit마다 coordinator가 새 chained record를 append-equivalent atomic replace하고 read-back한다. Unit test가 생성한 manifest/lock/ledger를 다시 열어 schema와 모든 bound SHA가 입력 bytes와 일치하는지 확인한다. Trusted-worktree review receipt와 `ci-provenance.json`은 exact central commit, `.github/workflows/ci.yml` SHA, executed check argv/output SHA, toolchain SHA와 independent reviewer identity를 bind하고 G1/G2 ledger entry에서 read-back한다. 실제 G1/G2 stage receipt 생성은 runner가 존재하는 Task 5에서만 수행한다.

- [ ] **Step 6: copy-paste 가능한 bootstrap CLI 고정**

```bash
python3 scripts/catalog_candidate.py prepare --workspace /Users/debop/work/bluetape4k --central /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority --repository-map /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-repositories.json --cache-manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/cache-manifest.json --manifest-out /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --ledger /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/docs/releases/2026-08-03-issue-168-candidate-ledger.md
python3 scripts/catalog_candidate.py verify --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json
```

`prepare`는 exact 9 worktree가 이미 생성돼 있어야 하며 approved origin, base/branch/HEAD/clean/path, catalog SHA와 offline cache source/SHA를 read-back한다. 하나라도 불일치하면 manifest나 ledger를 만들지 않고 stop condition을 출력한다. Runbook에는 worktree 생성 명령, fixed branch/path, expected base SHA와 이 두 bootstrap 명령을 그대로 싣는다.

**Rollback/rerun:** receipt mismatch는 append로 덮지 않고 candidate를 `failed`로 표시하고 새 candidate SHA directory에서 재시작한다.

### Task 5: credential-free manifest-only G1–G8 runner 구현

**Complexity:** high
**Depends on:** Task 4
**Write scope:** central runner/tests/fixtures

**Files:**

- Create: `scripts/run-catalog-validation.py`
- Create: `tests/test_run_catalog_validation.py`
- Create: `tests/fixtures/catalog-validation/manifest-valid.json`
- Create: `tests/fixtures/catalog-validation/manifest-forbidden-task.json`
- Create: `tests/fixtures/catalog-validation/cache-manifest-valid.json`

- [ ] **Step 1: security/scheduler RED tests 작성**

Cover: credential/proxy/SSH/Gradle init injection removal, forbidden publish/sign/upload task, task graph `dependsOn`/`finalizedBy` rejection, dynamic version/source repository rejection, cache source allowlist/SHA/cache miss, manifest mutation/owner/mode/symlink, `sandbox-exec` absence BLOCKED, network denial fixture, same-manifest predecessor PASS requirement, G6 `25m × 4 wave + 20m`, G7 60m, G8 90m, startup/cleanup reserve 30m, total 5h30m, impossible-budget pre-stage failure.

- [ ] **Step 2: RED 확인**

Run: `python3 -m unittest tests/test_run_catalog_validation.py -v`
Expected: missing runner import/CLI failure.

- [ ] **Step 3: exact CLI와 fail-closed stage 구현**

```python
class Stage(enum.Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"
    G4 = "G4"
    G5 = "G5"
    G6 = "G6"
    G7 = "G7"
    G8 = "G8"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--stage", choices=[stage.value for stage in Stage], required=True)
    args = parser.parse_args()
    return run_stage(load_and_verify_manifest(args.manifest), Stage(args.stage))
```

Runner는 absolute manifest path만 허용하고 symlink/outside-workspace/path mutation을 child 생성 전에 거부한다. Child environment allowlist는 `PATH`, `JAVA_HOME`, `LANG`, `LC_ALL`, temporary `HOME`, `GRADLE_USER_HOME`, Maven local repository만 포함한다. 모든 Gradle command에 `--offline --no-daemon --no-configuration-cache --no-build-cache --console=plain`을 주입한다. `sandbox-exec` profile은 workspace/JDK/read-only cache/temporary home만 허용하고 outbound network와 임의 process를 거부한다.

Stage N은 같은 manifest SHA, cache-manifest SHA, catalog SHA의 N-1 prerequisite가 충족될 때만 child process를 만들 수 있다. G1만 predecessor 없이 시작할 수 있다. G1/G2는 exact central commit에 bind된 trusted-worktree review receipt와 `ci-provenance.json`을 read-back하며 누락/stale/mismatch면 zero-child `BLOCKED`다. G2 receipt는 `path_sha=PASS`와 `declared_ref=PASS|BLOCKED_UNTIL_TAG`를 분리하며, G3 prerequisite는 `path_sha=PASS`를 요구하되 declared-ref hold를 aggregate ledger에 끝까지 보존한다. 그 외 stage는 predecessor aggregate `PASS`가 필요하다. 누락/실패/다른 SHA predecessor, 직접 G6/G7/G8 호출은 `zero-child-launch` receipt로 실패한다. G2 partial-hold→G3 허용과 G2 path/SHA failure→G3 zero-launch fixture를 모두 둔다.

| budget item | hard budget | scheduler contract |
| --- | ---: | --- |
| startup/cleanup | 30m | sandbox/profile creation, cancellation drain, final receipt fsync reserve |
| G1–G5 | 30m | inventory/governance preflight; no heavy child after reserve exhaustion |
| G6 | 120m | 8 publisher jobs, 2 workers, 25m × 4 waves + 20m audit/effective-model reserve |
| G7 | 60m | at most 2 repository chains, 10m × 5 waves + 10m reserve |
| G8 | 90m | 10 root builds, 2 workers, 15m × 5 waves + 15m reserve |
| whole train | 330m | sum of all named budgets; stage starts only when its full reserve remains |

G6–G8 timeout은 공통으로 process group terminate→deadline 후 kill→30초 drain을 수행하고, 새 job scheduling을 즉시 중지하며 per-job/stage diagnostic receipt에 command, elapsed time, exit/timeout state와 bounded last 80 log lines를 기록한다. Cancellation/restart fixture는 orphan child 0건과 incomplete artifact 미재사용을 검증한다. G7 manifest는 exact `repository/help/compile/graph` 27 commands와 canonical `insights[]`를 생성한다. 각 insight object의 exact fields는 `authority_id`, `line_id`, `repository`, `project_path`, exact `coordinate`, exact `configuration`, `reason`, `expected_resolved_version`, `artifact_path`이며 `(repository, authority_id, line_id, coordinate, configuration)` 순서로 정렬·deduplicate한다. Runner command는 `./gradlew <project_path>:dependencyInsight --dependency <group:artifact> --configuration <configuration>`이고 configuration 기본값은 명시적인 `compileClasspath`다. `compatibility-line`, `bom-managed-versionless`, intentional version delta 또는 changed normalized graph의 affected authority-id마다 정확히 하나 이상의 insight를 요구하며 누락/extra/wildcard coordinate를 거부한다. Per-insight stdout/stderr SHA와 resolved selection을 artifact/receipt/ledger에 bind하는 positive/negative fixture를 둔다. 각 repository chain은 help→compile→graph→insights를 한 10-minute budget 안에서 순차 실행한다. Preflight가 2-worker five-wave/10-minute reserve 안에 command list를 배치할 수 없으면 child를 시작하지 않는다. G8은 central 포함 10 root build를 15-minute chain으로 두 개씩 실행하며 같은 cancellation/drain contract를 사용한다.

Evidence root는 manifest가 bind한 central raw `gradle/libs.versions.toml` bytes의 lowercase SHA-256인 `<catalog-sha256>`를 사용해 `build/catalog-authority/<catalog-sha256>/`로 고정한다. 다른 digest, uppercase, short SHA 또는 manifest/catalog mismatch는 artifact 생성 전 실패한다. G3와 pre-G8 full scan은 이 root의 `inventory.json`과 `summary.json`을 atomic regenerate하며 aggregate receipt가 두 SHA를 필수로 bind한다; `baseline/` audit files는 candidate evidence로 허용하지 않는다. Immutable job receipt는 `receipts/<stage>/<job>.json`, bounded/full logs는 `logs/<stage>/<job>.log`, aggregate stage receipt는 `receipts/<stage>/aggregate.json`에 둔다. Receipt schema는 command argv, monotonic start/end/elapsed, exit/timeout/cancellation, manifest/catalog/cache/input/output SHA, inventory/summary SHA, bounded last-80 lines SHA, full-log SHA와 artifact links를 필수로 하고 ledger가 모든 aggregate receipt SHA를 연결한다. Unit fixture는 raw catalog bytes→SHA→path 계산, baseline substitution과 digest substitution rejection을 검증한다.

- [ ] **Step 4: RED→GREEN fixture proof**

Run: `python3 -m unittest tests/test_run_catalog_validation.py -v`
Expected: all negative fixtures are rejected and the harmless fixture creates `preflight.json` without accessing user credentials.

- [ ] **Step 5: G1–G5 dry run**

```bash
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G1
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G2
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G3
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G4
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G5
```

Expected before migration: G1/G2 path checks and G3 baseline pass; G4 reports no migration; G5 may fail only for the intentionally incomplete disposition/catalog migration. Direct G6, failed-predecessor G7, cross-manifest predecessor fixtures all exit before child launch.

**Rollback/rerun:** sandbox proof가 없거나 cache가 불완전하면 unsandboxed fallback 없이 `BLOCKED`; trusted baseline cache preparation을 별도 local read-only step으로 수행한 뒤 같은 manifest/cache SHA로 재시도한다.

### Task 6: publication POM candidate mode를 offline으로 고정

**Complexity:** medium
**Depends on:** Task 5
**Write scope:** central POM verifier/tests/settings

**Files:**

- Modify: `scripts/verify-publication-poms.py`
- Modify: `tests/test_verify_publication_poms.py`
- Modify: `config/publication-pom-maven-settings.xml`

- [ ] **Step 1: candidate mode RED tests 작성**

Assertions: `-U` absent, `--offline` present, cache manifest required, fixed eight-publisher registry only, max two concurrent jobs, 25-minute publisher timeout, process-group terminate/kill and 30-second drain receipt, no-new-job after failure/timeout, bounded diagnostic tail, resume invalidation, one effective-model pass, missing/versionless dependency-management fails.

- [ ] **Step 2: RED 확인**

Run: `python3 -m unittest tests/test_verify_publication_poms.py -v`
Expected: candidate-mode argument and offline assertions fail.

- [ ] **Step 3: candidate mode 구현**

Add CLI: `--candidate-manifest`, `--offline`, `--max-workers 2`. Candidate mode requires runner-provided repository map/cache/Maven repo and refuses direct network refresh. Existing ordinary CI mode remains unchanged unless explicit candidate flags are present.

- [ ] **Step 4: GREEN 확인**

Run: `python3 -m unittest tests/test_verify_publication_poms.py -v`
Expected: all existing audit/effective-model tests and new candidate tests pass.

- [ ] **Step 5: G6 fixture integration test**

Run: `python3 -m unittest tests/test_run_catalog_validation.py tests/test_verify_publication_poms.py -v` with the candidate fixture manifest.
Expected: the runner invokes the fixed publisher registry, structural audit precedes the single effective-model call, and no direct network/publish command is admitted. The real eight-publisher G6 run remains in Task 11 after migration.

**Rollback/rerun:** one publisher failure stops new jobs, preserves logs/POMs, marks G6 failed, and reruns only after that publisher candidate is repaired.

### Task 7: 중앙 catalog authority와 compatibility disposition 적용

**Complexity:** high
**Depends on:** Tasks 2, 4, 6
**Write scope:** central catalog/config/build/tests

**Files:**

- Modify: `gradle/libs.versions.toml`
- Modify: `gradle/libs.versions.toml.sha256`
- Modify: `config/central-catalog-authority-dispositions.json`
- Modify: `config/central-catalog-version-deltas.json`
- Modify: `config/central-catalog-exceptions.toml`
- Modify: `build.gradle.kts` only when a published dependency lacks valid imported-BOM management
- Modify: `tests/test_catalog_checksum.py`
- Modify: `tests/test_sync_shared_versions.py`

- [ ] **Step 1: same-version multi-repo authority를 central alias로 추가**

320 repeated coordinate 중 동일 resolved version 287개와 공유 plugin ID를 canonical alias/version key로 정렬한다. Alias grammar와 synthetic namespace test를 먼저 통과시킨다. Generated bluetape module block은 `scripts/sync-managed-catalog.py --repository-map build/catalog-authority/prepare/candidate-repositories.json --write --check`로만 갱신하고 외부 alias를 그 generated block에 넣지 않는다.

- [ ] **Step 2: 33 conflict coordinate를 증거별로 분리**

Patch/minor alignment는 before/after graph와 `central-catalog-version-deltas.json`에 기록한다. BOM-managed는 generated POM/effective model 근거를 disposition에 연결한다. Major/ABI drift는 `spring-boot3/4`, `jackson2/3`, `kafka3/4`와 같은 canonical `line-id` 및 중앙 alias로 유지한다.

- [ ] **Step 3: 37 repository-only coordinate와 9 plugin ID 분류**

재사용 가능하면 중앙 alias/version authority로 승격하고, 실제 single-repository/setting-time 제약만 exact issue/review date가 있는 `structural-repo-owned`로 남긴다.

- [ ] **Step 4: BOM constraint 판단**

Catalog alias 추가 자체는 constraint를 만들지 않는다. Published regular dependency가 versionless가 되며 imported BOM이 관리하지 않는 경우에만 `build.gradle.kts` constraint를 추가하고 Task 6 POM test를 먼저 RED로 만든다.

- [ ] **Step 5: checksum과 중앙 unit proof**

Run:

```bash
scripts/sync-managed-catalog.py --repository-map build/catalog-authority/prepare/candidate-repositories.json --write --check --summary
python3 -m unittest tests/test_catalog_authority.py tests/test_sync_managed_catalog.py tests/test_sync_shared_versions.py tests/test_catalog_checksum.py tests/test_central_catalog_version_deltas.py -v
```

Expected: checksum exact match, orphan/duplicate authority zero, compatibility lines preserved.

**Rollback/rerun:** undocumented graph delta가 발견되면 해당 authority pair만 이전 catalog/disposition으로 복원하고 Task 7 Step 2부터 재분류한다.

### Task 8: 9개 downstream repository를 중앙 alias/accessor로 전환

**Complexity:** very high
**Depends on:** Task 7 and clean candidate map
**Write scope:** 9개 candidate worktree only

**Common files in every repository:**

- Modify: `settings.gradle.kts` only if the verified exact `bt4k` loader/ref/path/SHA contract needs repair
- Modify: root `build.gradle.kts` for the existing `VersionCatalogsExtension.named("bt4k")`, `bt4kLibrary`, `bt4kVersion` entrypoint and root resolution rules
- Modify: `gradle/libs.versions.toml`
- Inspect: `gradle.properties`; only `bluetape4k-exposed/gradle.properties` has an extra governed `bluetape4kVersion` candidate
- Inspect: `.github/dependabot.yml`; all nine currently contain GitHub Actions updates only, so Gradle dependency ignore mutation is N/A unless Task 9 detects a Gradle ecosystem entry
- Modify: `.github/workflows/ci.yml` only for the single-repository central guard/ref parity
- Modify: inventory가 지목한 exact `*.gradle.kts` files only

**Exact hard-coded external version files:**

| repository | files |
| --- | --- |
| projects | `build.gradle.kts`; `spring-boot/hibernate-lettuce-demo/build.gradle.kts`; `spring-boot/hibernate-lettuce/build.gradle.kts`; `data/hibernate/build.gradle.kts`; `data/hibernate-reactive/build.gradle.kts`; `examples/jpa-blazepersistence-demo/build.gradle.kts`; `examples/jpa-querydsl-demo/build.gradle.kts`; `cache/hibernate-cache-lettuce/build.gradle.kts`; `testing/mock-web-server/build.gradle.kts`; `testing/mock-webflux-server/build.gradle.kts`; `utils/geo/build.gradle.kts`; `infra/opentelemetry/build.gradle.kts` |
| aws | `build.gradle.kts` |
| experimental | no literal external version-bearing Kotlin DSL file; root `build.gradle.kts` accessor use and local catalog still migrate |
| exposed | `build.gradle.kts`; `spring-boot/batch-exposed/build.gradle.kts`; `gradle.properties`; the exact `bluetape4kVersion` consumers listed below |
| graph | `build.gradle.kts` including the Detekt-supported Kotlin compatibility constant |
| image | `build.gradle.kts` |
| javers | `build.gradle.kts`; `benchmark/javers-exposed-benchmark/build.gradle.kts` |
| leader | `build.gradle.kts`; `benchmark/build.gradle.kts`; `leader-k8s/build.gradle.kts`; `examples/k8s-lease/build.gradle.kts`; `examples/k8s-operator/build.gradle.kts`; `leader-spring-boot/build.gradle.kts` |
| text | `build.gradle.kts`; `tokenizer-korean/build.gradle.kts` |

Inventory는 `.worktrees/**`, `build/**`, `.gradle/**`를 제외하고 위 files의 literal coordinate/plugin version, `useVersion`, resolution `force`, version variable를 모두 분류한다. `useVersion(bt4kVersion("kotlinx-serialization"))` 같은 표현은 local authority가 아닌 중앙 consumer로 기록한다.

9개 Settings file 모두 exact catalog name `bt4k`, manifest-declared canonical path, declared immutable ref field, raw catalog SHA 검증과 override 금지 contract를 assertion한다. Existing loader가 이 contract와 일치할 때만 bytes를 보존한다. `tests/test_sync_shared_versions.py`의 9-entry fixture와 `scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --repository-map build/catalog-authority/prepare/candidate-repositories.json --verify-catalog-loaders --check --summary`가 repository별 loader/ref/path/SHA를 manifest와 대조하며 누락·다른 catalog name·broad discovery를 거부한다.

`bluetape4k-exposed/gradle.properties`의 `bluetape4kVersion` exact consumers는 root `build.gradle.kts`, `spring-boot/{batch-exposed,r2dbc,jdbc,spring-modulith}/build.gradle.kts`, `ktor/exposed/build.gradle.kts`, `exposed/{jdbc-redisson,clickhouse,postgresql,r2dbc-lettuce,jdbc-tests,jackson2,measured,core,cache,jackson3,trino,r2dbc,dao,bigquery,jdbc-caffeine,jdbc,r2dbc-tests,tink,jdbc-lettuce,mysql8,r2dbc-redisson,duckdb,r2dbc-caffeine,fastjson2,timefold-solver-persistence}/build.gradle.kts`, `examples/{jdbc-demo,exposed-bigquery-dry-run,exposed-clickhouse-oltp-olap,r2dbc-demo}/build.gradle.kts`, `utils/batch/build.gradle.kts`다. 이 property는 central `bluetape4k-core` authority로 대체 가능한지 resolved graph로 판정하고, 36개 consumer를 한 conversion unit으로 검증한다.

- [ ] **Step 1: repository별 before graph 고정**

G3 artifact에 각 repository `help`, representative dependency graph와 affected coordinate별 `dependencyInsight`를 저장한다. 변환 전에 graph가 생성되지 않는 repository는 수정하지 않는다.

- [ ] **Step 2: direct central aliases로 변환**

Catalog/module/plugin usage를 `bt4k.*`와 `bt4k.plugins.*`로 바꾸고 동일 coordinate/plugin ID의 local explicit alias/version key를 제거한다. Alias 이름을 유지해야 하는 경우에는 versionless local alias와 proven dependency management만 허용한다.

- [ ] **Step 3: hard-coded 43개 후보 처리**

Module dependency/plugin literal은 central accessor로 바꾸고 `settings.pluginManagement` 이전 항목만 exact `structural-repo-owned` exception으로 남긴다. 문자열이 test fixture/data이면 declaration-form classifier evidence로 제외한다.

- [ ] **Step 4: repository별 targeted RED/GREEN**

각 repository에서 변환 직전 literal/alias assertion test 또는 guard가 실패하는지 확인하고, 변환 뒤 `./gradlew help`와 아래 compile/graph matrix를 runner G7로 통과시킨다.

| repository | compile task | graph task |
| --- | --- | --- |
| projects | `:bluetape4k-core:compileKotlin` | `:bluetape4k-core:dependencies --configuration compileClasspath` |
| aws | `:bluetape4k-aws-java:compileKotlin` | `:bluetape4k-aws-java:dependencies --configuration compileClasspath` |
| experimental | `:shared:compileKotlin` | `:shared:dependencies --configuration compileClasspath` |
| exposed | `:bluetape4k-exposed-core:compileKotlin` | `:bluetape4k-exposed-core:dependencies --configuration compileClasspath` |
| graph | `:bluetape4k-graph-core:compileKotlin` | `:bluetape4k-graph-core:dependencies --configuration compileClasspath` |
| image | `:bluetape4k-images:compileKotlin` | `:bluetape4k-images:dependencies --configuration compileClasspath` |
| javers | `:javers-core:compileKotlin` | `:javers-core:dependencies --configuration compileClasspath` |
| leader | `:bluetape4k-leader-core:compileKotlin` | `:bluetape4k-leader-core:dependencies --configuration compileClasspath` |
| text | `:tokenizer-core:compileKotlin` | `:tokenizer-core:dependencies --configuration compileClasspath` |

- [ ] **Step 5: migration delta reconcile**

G4 full inventory를 재생성해 every before occurrence가 same `(authority-id,line-id)` after record 또는 explicit structural/BOM evidence로 연결되는지 검사한다. 문서화되지 않은 deletion/addition/version delta는 실패다.

- [ ] **Step 6: repository별 Lore commit은 verify barrier 뒤에만 생성**

모든 entry가 G1–G7 PASS일 때 central → projects → aws → experimental → exposed → graph → image → javers → leader → text 순서로 local candidate commit을 만든다. 중간 실패 시 성공 commit과 실패 worktree를 보존하고 default branch는 건드리지 않는다.

**Rollback/rerun:** repository failure는 후속 repository 변환을 중지하고 last-known-good SHA에서 별도 repair worktree를 만든다. reset/revert 예외/기존 worktree 삭제는 하지 않는다.

| failure state | resume decision | exact replay |
| --- | --- | --- |
| child timeout/output incomplete, input SHA와 HEAD unchanged | same manifest에서 failed stage만 repair 후 predecessor receipt read-back부터 resume | `catalog_candidate.py verify` → failed G-stage → 이후 stage 순차 실행 |
| source edit/local commit/HEAD 또는 catalog/disposition/cache/map SHA 변경 | old candidate `stale`, new manifest 필수 | prepare/verify → G1 topology → G2 path/ref/provenance → G3/G4 graph delta → G6 POM → G7 compile/graph → G8 build |
| partial downstream commit | 성공 commit/worktree 보존, 실패 repository LKG에서 별도 repair worktree, new manifest 필수 | exact 10 HEAD/diff read-back → prepare/verify → G1부터 전체 replay |
| immutable ref만 미확정, path/SHA와 G3–G8 PASS | source resume 금지, `blocked-until-tag` 유지 | 승인 tag/ref evidence로 G2 declared-ref만 재진입 후 closeout |

### Task 9: Dependabot, CI, catalog governance gate 확장

**Complexity:** medium
**Depends on:** Task 7 disposition, Task 8 exact central names
**Write scope:** central scripts/tests/CI and downstream generated ignore blocks

**Files:**

- Modify: `scripts/sync-dependabot-ignores.py`
- Modify: `tests/test_sync_dependabot_ignores.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ci_catalog_governance.py`
- Inspect: `.github/dependabot.yml` in all 9 candidate repositories

- [ ] **Step 1: new authority names의 generated ignore RED test 작성**

Central library coordinate/plugin ID set에서 Dependabot names를 deterministic 생성하고 unknown/manual duplicate/removed authority를 거부한다.

- [ ] **Step 2: RED 확인 후 generator 구현**

Run: `python3 -m unittest tests/test_sync_dependabot_ignores.py tests/test_ci_catalog_governance.py -v` before and after implementation.
Expected: RED on new central names, then GREEN with idempotent generated blocks.

- [ ] **Step 3: downstream ownership policy check**

```bash
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --repository-map build/catalog-authority/prepare/candidate-repositories.json --repo bluetape4k-projects --repo bluetape4k-aws --repo bluetape4k-experimental --repo bluetape4k-exposed --repo bluetape4k-graph --repo bluetape4k-image --repo bluetape4k-javers --repo bluetape4k-leader --repo bluetape4k-text --check --summary
```

현재 9개 file은 `package-ecosystem: github-actions`만 가지므로 Gradle dependency ignore는 concrete N/A다. Script는 Actions-only file을 변경하지 않는 기존 contract를 유지하고, 향후 Gradle ecosystem이 존재할 때만 중앙 dependency names의 generated ignore block을 요구한다. Candidate repository map을 지원해 default checkout을 읽거나 수정하지 않는다.

- [ ] **Step 4: CI fixture guard 갱신**

PR fixture는 repo-local deterministic inventory/disposition check를 실행하고, full workspace audit는 non-PR path에 유지한다. Candidate runner는 CI에서 publish/sign credential을 요구하거나 task를 실행하지 않는다.

**Rollback/rerun:** generated block 외 diff가 생기면 write를 중단하고 parser/generator를 repair한다.

### Task 10: 한국어 runbook, candidate ledger, contributor surface 갱신

**Complexity:** medium
**Depends on:** Tasks 4–9
**Write scope:** central docs/guidance only

**Files:**

- Modify: `docs/version-management.ko.md`
- Modify: `README.md`
- Modify: `README.ko.md`
- Modify: `AGENTS.md`
- Modify: `docs/releases/2026-08-03-issue-168-candidate-ledger.md`

- [ ] **Step 1: runbook에 exact G1–G8 command와 실패 상태 작성**

Candidate map/lock, disposition lifecycle, path/ref 분리, cache preparation, runner-only command, mixed-state/repair, `candidate-ready`/`blocked-until-tag`를 한국어로 설명한다. Publish/PR/tag/merge 권한이 아님을 명시한다.

- [ ] **Step 2: README locale parity와 AGENTS command 갱신**

README 두 locale은 contributor-facing central authority/report usage를 동등하게 설명한다. 두 README에 동일 순서의 command matrix를 두어 absolute `prepare`/`verify`, repository-map-bound `sync-managed-catalog`/`sync-shared-versions`/Dependabot, runner G1–G8, partial-repair/new-candidate replay, `blocked-until-tag`와 post-tag G2 re-entry를 모두 싣는다. Test는 두 locale의 normalized command ID 집합이 exact match하고 기존 broad `--workspace ..` 단독 예제가 남지 않는지 검사한다. AGENTS는 English command/rule만 추가한다.

- [ ] **Step 3: ledger receipt chain 생성·read-back**

Ledger에는 schema version, immutable candidate ID, prior/current receipt SHA, atomic timestamp, 10개 worktree base/expected/actual HEAD, canonical source diff hash와 계산/exclusion contract, catalog path/ref/SHA, G1–G8 상태, delta/POM/artifact links, repair state를 기록한다.

- [ ] **Step 4: docs verification**

Run: `git diff --check` and repository-wide link/path search.
Expected: no whitespace errors; all mentioned commands/files exist; README locale sections match in scope.

### Task 11: 전체 검증, review, local handoff

**Complexity:** high
**Depends on:** Tasks 1–10
**Write scope:** verification evidence, review, lesson; no remote side effect

**Files:**

- Create: `docs/review/2026-08-03-issue-168-external-version-authority-review.md`
- Create: `docs/lessons/2026-08-03-external-version-authority-train.md`
- Modify: `docs/lessons/README.md`

- [ ] **Step 1: central targeted tests**

```bash
python3 -m unittest tests/test_catalog_authority.py tests/test_catalog_candidate.py tests/test_run_catalog_validation.py tests/test_sync_managed_catalog.py tests/test_sync_shared_versions.py tests/test_verify_publication_poms.py tests/test_sync_dependabot_ignores.py tests/test_ci_catalog_governance.py tests/test_catalog_checksum.py tests/test_central_catalog_version_deltas.py -v
```

Expected: all pass.

- [ ] **Step 2: six-perspective implemented-diff review와 main-session integration**

Performance, stability, security, operator/Ops, developer/API, user/caller lenses review the exact current diffs and targeted evidence. P0/P1 is repaired and affected tests/lenses rerun; P2/P3 is fixed or issue-linked with rationale. `main-session integration`은 review 결과를 현재 worktree에 반영한다는 뜻이며 merge/push를 의미하지 않는다.

- [ ] **Step 3: review/lesson 갱신 후 full central tests/static/build**

Review와 lesson에 최종 finding/repair/evidence를 기록한 뒤 아래 검증을 실행한다. 이후 G8 종료까지 candidate ledger state record 외 source edit는 금지한다.

```bash
python3 -m py_compile scripts/catalog_authority.py scripts/catalog_candidate.py scripts/run-catalog-validation.py scripts/sync-shared-versions.py scripts/verify-publication-poms.py scripts/sync-dependabot-ignores.py tests/*.py
python3 -m unittest discover -s tests -p 'test_*.py'
scripts/sync-managed-catalog.py --repository-map build/catalog-authority/prepare/candidate-repositories.json --check --summary
scripts/sync-shared-versions.py --workspace /Users/debop/work/bluetape4k --repository-map build/catalog-authority/prepare/candidate-repositories.json --check --summary
scripts/sync-dependabot-ignores.py --workspace /Users/debop/work/bluetape4k --repository-map build/catalog-authority/prepare/candidate-repositories.json --repo bluetape4k-projects --repo bluetape4k-aws --repo bluetape4k-experimental --repo bluetape4k-exposed --repo bluetape4k-graph --repo bluetape4k-image --repo bluetape4k-javers --repo bluetape4k-leader --repo bluetape4k-text --check --summary
```

Expected: all exit 0 in path mode. Gradle/Maven commands are intentionally absent here and execute only through runner G1–G8 after the final candidate freeze.

- [ ] **Step 4: final local commits와 candidate freeze**

모든 source, README/runbook, review, lesson repair를 Lore commit으로 완료한다. 그 뒤 central+9 downstream actual HEAD와 canonical source diff hash를 read-back하고 새 immutable candidate manifest/aggregate commit receipt를 생성한다. Candidate ledger는 `validation-pending` snapshot까지 commit하고, 이후 G1–G8 state update만 self-reference exclusion path에서 허용한다. 다른 post-freeze source edit/commit은 기존 receipt를 stale로 만들며 새 manifest로 G1부터 재실행해야 한다.

- [ ] **Step 5: final SHA에서 G1–G8 sequential validation**

G7 PASS 뒤 G8 직전에 runner가 incremental cache를 사용하지 않고 exact 9-repository full inventory와 summary를 한 번 재생성한다. 새 inventory/summary SHA와 864/43 reconciliation 결과를 G8 prerequisite receipt와 ledger에 bind한다. Task 8의 각 local commit과 Task 10의 마지막 source edit 뒤 coordinator가 actual HEAD와 canonical source diff hash를 계산해 immutable candidate manifest SHA에 종속된 별도 aggregate commit receipt의 `expected_post_commit_head`와 `expected_source_diff_sha256` 필드로 원자적으로 고정한다. Candidate manifest bytes는 생성 뒤 절대 변경하지 않으며 mutation은 `BLOCKED`다. G8 preflight는 aggregate commit receipt의 manifest SHA가 원본과 일치하는지 먼저 확인한 뒤 central+9 downstream actual HEAD/diff hash를 expected 필드들과 exact 비교하고, candidate ledger prior-record SHA도 별도 검증한다. Inventory scan 실패, G7 이후 source byte drift, commit 누락, mixed HEAD 또는 extra diff가 하나라도 있으면 G8 child launch는 0건이며 failed receipt를 남긴다. Positive/negative fixture가 manifest 불변성, aggregate receipt field 생성/read-back, exact match와 각 mismatch를 검증한다.

```bash
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G1
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G2
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G3
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G4
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G5
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G6
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G7
scripts/run-catalog-validation.py --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --stage G8
```

Expected: publisher POM/effective model, 9 targeted repository commands, 10 root builds, receipt read-back pass. Heavy jobs use runner max concurrency 2 and no Testcontainers/native parallelism.

- [ ] **Step 6: immutable ref hold와 final read-back**

No catalog tag is authorized. G2 declared-ref check therefore records `blocked-until-tag`; path/SHA lock and all other applicable gates remain independently visible. Ledger는 repository별 blocked declared-ref entry에 required tag/ref name, expected peeled 40/64-char commit, catalog SHA, owner, authority needed, next action과 preserved path/SHA receipt를 기록하고 실패/partial gate와 별도 상태로 표시한다. Tag authority와 실제 immutable ref가 나중에 확보된 뒤에만 `python3 scripts/catalog_candidate.py promote-ref --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json --tag <approved-tag> --peeled-commit <approved-commit>`으로 새 ref evidence receipt를 만들고, 같은 absolute manifest의 G2를 재실행해 declared-ref를 PASS로 전환한 뒤 closeout한다. Source/HEAD/SHA drift가 있으면 이 단축 경로를 거부하고 새 candidate G1부터 시작한다. 이번 실행에서는 tag/push/PR/publish command를 실행하지 않는다.

각 10개 worktree에서 `git status --porcelain=v1 -z`, branch, actual HEAD와 canonical source diff SHA를 read-back해 aggregate receipt와 비교한다. Receipt/log/artifact SHA와 G1–G8 상태를 `python3 scripts/catalog_candidate.py verify --manifest /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-manifest.json`으로 재검증한다. `python3 scripts/catalog_candidate.py snapshot-remote-state --repository-map /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/issue-168-central-catalog-authority/build/catalog-authority/prepare/candidate-repositories.json --output <absolute-snapshot-path>`는 `env -i` equivalent의 Python standard-library HTTPS client로 public GitHub API만 호출한다. Credential/token/cookie/user config/proxy 환경을 제거하고 `ProxyHandler({})`, redirect-disabled handler, system TLS verification, exact host `api.github.com`, GET-only method와 `/repos/bluetape4k/<manifest-repo>/{git/matching-refs/heads/,git/matching-refs/tags/,pulls,releases,actions/runs}` path/query/page-size allowlist를 적용한다. `Link` pagination도 same scheme/host/allowlisted path만 허용하며 token 없이 실행한다. Bootstrap 전 snapshot과 G8 후 canonical response SHA/count가 같아야 한다. Ledger는 attempted host/path, redirect/proxy rejection, response/status SHA를 bind한다. Maven proof는 외부 API credential을 사용하지 않고 runner receipt의 `publish_task_attempts=0`, `outbound_connect_attempts=0`, stripped publishing-env 목록과 sandbox deny log SHA로 고정한다. Credential/proxy/redirect/host/path/query/pagination negative fixture, mocked before/after drift와 Maven zero-counter fixture를 테스트한다. Candidate ledger state update 외 diff가 있거나 GitHub snapshot이 달라지거나 Maven zero-counter proof가 깨지면 handoff는 실패다.

- [ ] **Step 7: final DoD**

Report required checks, inventory/disposition counts, changed repositories/files, test/POM/graph results, exact candidate SHAs, no external side effects, and unchecked release hold. Final state is `PENDING — blocked-until-tag` unless immutable ref authority is separately granted later.

## 위험 예측

| 위험 | 신호 | 완화 | rollback/rerun |
| --- | --- | --- | --- |
| compatibility line collapse | same coordinate의 before major가 after에서 하나로 합쳐짐 | canonical `line-id`, exact dependencyInsight | 해당 pair 복원 후 Task 7/8 재실행 |
| versionless published dependency | generated POM에 version/management 없음 | G6 structural/effective-model fail closed | central alias/constraint 복원 후 publisher만 재실행 |
| candidate catalog substitution | path/ref/SHA 중 하나 불일치 | G1/G2 separate lock and no-follow read | 새 candidate manifest 생성부터 재시작 |
| credential/network side effect | env/preflight 또는 sandbox deny log | minimal env, offline cache, forbidden task graph | stage BLOCKED; unsandboxed fallback 금지 |
| mixed multi-repo state | 일부 commit 뒤 후속 failure | fixed commit order, aggregate receipt, no default branch writes | worktree 보존, repair commit, G1부터 read-back |
| validation timeout hang | remaining budget < stage worst-case | compositional scheduler and diagnostics | failed stage만 repair 후 동일 manifest 재실행 |
| generator overreach | generated block 밖 downstream diff | canonical candidate map and diff scope check | generator repair, candidate diff discard 없이 증거 보존 |

## 계획 자체의 완료 기준

- 모든 설계 acceptance criterion이 task/command에 매핑되어 있다.
- 구현 순서가 inventory → topology/runner → central authority → downstream migration → verification이다.
- 모든 변경 task에 RED/GREEN 또는 명시적 migration proof가 있다.
- shared catalog hazard, publication POM, checksum, Dependabot, CI, docs, rollback이 배정되어 있다.
- 구현 전 plan review의 최신 통합 결과가 P0=0/P1=0이고 사용자가 이 계획을 승인한다.
