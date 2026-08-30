# Issue #213 SNAPSHOT Catalog Ref Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SNAPSHOT consumer가 중앙 catalog의 검증된 이력 안에서 immutable ref를 앞으로 이동해도 개발선 검사가 통과하되, rollback·settings/CI 불일치·candidate history 밖 ref는 계속 차단한다.

**Architecture:** manifest의 `snapshot-catalog-ref`와 저장소별 override를 exact head가 아니라 minimum ref로 해석한다. 중앙 `bluetape4k-dependencies` checkout에서 `git merge-base --is-ancestor`를 사용해 `minimum <= actual <= HEAD`를 검증하고, stable release 검사는 기존 exact 계약을 유지한다. CI는 ancestry 판정에 필요한 전체 이력을 checkout한다.

**Tech Stack:** Python 3.13 표준 라이브러리, `unittest`, Git CLI, GitHub Actions YAML, Gradle

---

## 파일 구조

- `tests/test_post_publish_next_development_line.py`: 임시 Git repository를 만드는 fixture와 forward drift, rollback, history 이탈, settings/CI parity 회귀 테스트를 소유한다.
- `scripts/verify-post-publish-next-development-line.py`: catalog ref 파싱, Git object 존재 확인, ancestry 검증, consumer 정책 오류 메시지를 소유한다.
- `.github/workflows/ci.yml`: `Build BOM` job이 ancestry 검증에 필요한 전체 중앙 history를 checkout하도록 보장한다.
- `docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md`: manifest ref가 exact head가 아닌 immutable minimum이라는 운영 의미를 기록한다.
- `config/post-publish-next-development-line.json`: SHA 값과 key는 변경하지 않는다. 기존 `snapshot-catalog-ref`와 override 값은 호환성을 위해 그대로 두고 minimum 기준선으로 재해석한다.

### Task 1: 실제 Git history 기반 회귀 테스트 작성

**Files:**
- Modify: `tests/test_post_publish_next_development_line.py:1-10`
- Modify: `tests/test_post_publish_next_development_line.py:258-336`

- [ ] **Step 1: 테스트용 Git helper를 추가한다**

`subprocess` import와 아래 helper를 test module 상단에 추가한다. fixture는 `develop`의 선형 history와 별도 side commit을 만들며, 모든 SHA를 실제 Git object로 제공한다.

```python
import subprocess


def run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_catalog(repository: Path, content: str, message: str) -> str:
    catalog = repository / "gradle" / "libs.versions.toml"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    catalog.write_text(content, encoding="utf-8")
    run_git(repository, "add", str(catalog.relative_to(repository)))
    run_git(repository, "commit", "-m", message)
    return run_git(repository, "rev-parse", "HEAD")


def create_catalog_history(repository: Path) -> dict[str, str]:
    repository.mkdir(parents=True)
    run_git(repository, "init", "--initial-branch=develop")
    run_git(repository, "config", "user.name", "Bluetape Test")
    run_git(repository, "config", "user.email", "test@bluetape4k.invalid")

    rollback = commit_catalog(repository, '[versions]\nmarker = "rollback"\n', "rollback")
    minimum = commit_catalog(repository, '[versions]\nmarker = "minimum"\n', "minimum")
    forward = commit_catalog(repository, '[versions]\nmarker = "forward"\n', "forward")
    candidate = commit_catalog(repository, '[versions]\nmarker = "candidate"\n', "candidate")

    run_git(repository, "switch", "--detach", minimum)
    outside = commit_catalog(repository, '[versions]\nmarker = "outside"\n', "outside")
    run_git(repository, "switch", "develop")
    return {
        "rollback": rollback,
        "minimum": minimum,
        "forward": forward,
        "candidate": candidate,
        "outside": outside,
    }


def write_snapshot_consumer(repository: Path, settings_ref: str, ci_ref: str) -> None:
    workflow = repository / ".github" / "workflows" / "ci.yml"
    workflow.parent.mkdir(parents=True)
    (repository / "settings.gradle.kts").write_text(
        f'catalogRef.orElse("{settings_ref}")\n', encoding="utf-8"
    )
    workflow.write_text(
        "env:\n"
        "  BLUETAPE4K_DEPENDENCIES_CATALOG_REF: "
        f"'{ci_ref}'\n",
        encoding="utf-8",
    )


def snapshot_policy(
    minimum_ref: str,
    override_ref: str | None = None,
) -> dict[str, object]:
    policy: dict[str, object] = {
        "snapshot-catalog-ref": minimum_ref,
        "snapshot-catalog-repositories": ["internal-library"],
        "official-release-repositories": [],
    }
    if override_ref is not None:
        policy["snapshot-catalog-ref-overrides"] = {
            "internal-library": override_ref,
        }
    return {
        "stable-version": "1.4.0",
        "consumer-policy": policy,
    }
```

- [ ] **Step 2: minimum equality와 forward drift 허용 테스트를 작성한다**

기존 repository-specific override 성공 테스트는 실제 Git history 기반의 equality 테스트로 교체하고, 기본 minimum 이후의 forward ref 테스트를 추가한다.

```python
def test_consumer_policy_accepts_repository_specific_catalog_minimum(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            refs["minimum"],
            refs["minimum"],
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["rollback"], refs["minimum"]),
            central,
        )

    self.assertEqual(errors, [])


def test_consumer_policy_accepts_catalog_ref_after_minimum(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            refs["forward"],
            refs["forward"],
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertEqual(errors, [])
```

- [ ] **Step 3: forward drift 테스트가 현재 exact 비교에서 실패하는지 확인한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest \
  tests.test_post_publish_next_development_line.PostPublishNextDevelopmentLineTest.test_consumer_policy_accepts_catalog_ref_after_minimum
```

Expected: `verify_consumer_policy()`가 세 번째 인자를 받지 못하거나 forward SHA를 manifest SHA와 다르다고 보고하여 `FAILED (failures=1)` 또는 `ERROR`.

- [ ] **Step 4: rollback, candidate history 이탈, parity 불일치 테스트를 추가한다**

```python
def test_consumer_policy_rejects_catalog_ref_before_minimum(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            refs["rollback"],
            refs["rollback"],
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertIn(
        "internal-library snapshot catalog ref "
        f"{refs['rollback']} is older than minimum {refs['minimum']}",
        errors,
    )


def test_consumer_policy_rejects_catalog_ref_outside_candidate_history(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            refs["outside"],
            refs["outside"],
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertIn(
        "internal-library snapshot catalog ref "
        f"{refs['outside']} is outside candidate HEAD history",
        errors,
    )


def test_consumer_policy_rejects_settings_and_ci_catalog_ref_mismatch(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            refs["forward"],
            refs["minimum"],
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertIn(
        "internal-library settings catalog ref "
        f"{refs['forward']} must match CI catalog ref {refs['minimum']}",
        errors,
    )


def test_consumer_policy_rejects_non_sha_catalog_ref(self) -> None:
    module = load_script()

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            "develop",
            "develop",
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertIn(
        "internal-library settings catalog ref must be a lowercase "
        "40-character Git SHA, got 'develop'",
        errors,
    )


def test_consumer_policy_rejects_missing_catalog_commit(self) -> None:
    module = load_script()
    missing_ref = "f" * 40

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        central = root / "central"
        workspace = root / "workspace"
        refs = create_catalog_history(central)
        write_snapshot_consumer(
            workspace / "internal-library",
            missing_ref,
            missing_ref,
        )

        errors = module.verify_consumer_policy(
            workspace,
            snapshot_policy(refs["minimum"]),
            central,
        )

    self.assertIn(
        f"internal-library snapshot catalog ref {missing_ref} "
        "is missing from central history",
        errors,
    )
```

- [ ] **Step 5: 새 회귀 테스트들이 아직 GREEN이 아님을 확인한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest tests.test_post_publish_next_development_line
```

Expected: 새 history-aware 호출 또는 새 오류 메시지 때문에 suite가 실패하며, 기존 테스트의 비관련 실패는 없다.

### Task 2: minimum-to-actual-to-HEAD ancestry guard 구현

**Files:**
- Modify: `scripts/verify-post-publish-next-development-line.py:13-18`
- Modify: `scripts/verify-post-publish-next-development-line.py:26-31`
- Modify: `scripts/verify-post-publish-next-development-line.py:257-309`
- Modify: `scripts/verify-post-publish-next-development-line.py:384-414`
- Test: `tests/test_post_publish_next_development_line.py`

- [ ] **Step 1: ref parser가 임의 token을 읽은 뒤 형식을 별도로 검증하게 한다**

`subprocess`를 import하고 두 정규식을 다음과 같이 바꾼다. branch나 tag를 `None`으로 숨기지 않고 실제 invalid value로 보고해야 한다.

```python
import subprocess


CATALOG_REF = re.compile(r'\.orElse\("([^"\s]+)"\)')
CI_CATALOG_REF = re.compile(
    r"^\s*BLUETAPE4K_DEPENDENCIES_CATALOG_REF:\s*['\"]?([^'\"\s]+)['\"]?\s*$",
    re.MULTILINE,
)
```

- [ ] **Step 2: Git object와 ancestry helper를 추가한다**

`snapshot_catalog_ref_for_repository()` 아래에 다음 함수를 추가한다.

```python
def git_commit_exists(repository: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repository), "cat-file", "-e", f"{ref}^{{commit}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def git_is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "merge-base",
            "--is-ancestor",
            ancestor,
            descendant,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def verify_snapshot_catalog_history(
    repository_root: Path,
    consumer: str,
    minimum_ref: str,
    actual_ref: str,
) -> list[str]:
    if not git_commit_exists(repository_root, minimum_ref):
        return [
            f"{consumer} minimum snapshot catalog ref {minimum_ref} "
            "is missing from central history"
        ]
    if not git_commit_exists(repository_root, actual_ref):
        return [
            f"{consumer} snapshot catalog ref {actual_ref} "
            "is missing from central history"
        ]
    if not git_is_ancestor(repository_root, minimum_ref, actual_ref):
        return [
            f"{consumer} snapshot catalog ref {actual_ref} "
            f"is older than minimum {minimum_ref}"
        ]
    if not git_is_ancestor(repository_root, actual_ref, "HEAD"):
        return [
            f"{consumer} snapshot catalog ref {actual_ref} "
            "is outside candidate HEAD history"
        ]
    return []
```

- [ ] **Step 3: consumer 검사를 exact equality에서 parity와 ancestry로 교체한다**

함수 signature와 SNAPSHOT consumer loop를 다음 계약으로 바꾼다. stable/example version 검사는 loop 뒤의 기존 코드를 그대로 유지한다.

```python
def verify_consumer_policy(
    workspace: Path,
    manifest: dict[str, Any],
    repository_root: Path = REPO_ROOT,
) -> list[str]:
    errors: list[str] = []
    policy = manifest["consumer-policy"]
    stable_version = manifest["stable-version"]
    development_snapshot_repositories = policy.get(
        "development-snapshot-repositories", []
    )
    development_snapshot_version = None
    if development_snapshot_repositories:
        development_snapshot_version = (
            f"{manifest['development-version']}{manifest['snapshot-suffix']}"
        )

    for repository in policy["snapshot-catalog-repositories"]:
        minimum_snapshot_ref = snapshot_catalog_ref_for_repository(policy, repository)
        settings = workspace / repository / "settings.gradle.kts"
        ci_workflow = workspace / repository / ".github" / "workflows" / "ci.yml"
        if not settings.is_file():
            errors.append(f"missing snapshot consumer settings: {settings}")
            continue
        try:
            catalog_ref = read_catalog_ref(settings)
        except OSError as error:
            errors.append(f"cannot read {settings}: {error}")
            continue
        if catalog_ref is None or not GIT_SHA.fullmatch(catalog_ref):
            errors.append(
                f"{repository} settings catalog ref must be a lowercase 40-character Git SHA, "
                f"got {catalog_ref!r}"
            )
        if not ci_workflow.is_file():
            errors.append(f"missing snapshot consumer CI workflow: {ci_workflow}")
            continue
        try:
            ci_catalog_ref = read_ci_catalog_ref(ci_workflow)
        except OSError as error:
            errors.append(f"cannot read {ci_workflow}: {error}")
            continue
        if ci_catalog_ref is None or not GIT_SHA.fullmatch(ci_catalog_ref):
            errors.append(
                f"{repository} CI catalog ref must be a lowercase 40-character Git SHA, "
                f"got {ci_catalog_ref!r}"
            )
        if catalog_ref != ci_catalog_ref:
            errors.append(
                f"{repository} settings catalog ref {catalog_ref} "
                f"must match CI catalog ref {ci_catalog_ref}"
            )
        if (
            catalog_ref is not None
            and GIT_SHA.fullmatch(catalog_ref)
            and catalog_ref == ci_catalog_ref
        ):
            errors.extend(
                verify_snapshot_catalog_history(
                    repository_root,
                    repository,
                    minimum_snapshot_ref,
                    catalog_ref,
                )
            )
```

- [ ] **Step 4: 개발선 검사가 명시적으로 중앙 repository 경로를 전달하게 한다**

`verify_development()`의 consumer 검사 호출을 다음과 같이 바꾼다.

```python
errors.extend(verify_consumer_policy(workspace, manifest, central_root))
```

- [ ] **Step 5: targeted suite를 실행해 GREEN을 확인한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest tests.test_post_publish_next_development_line
```

Expected: 모든 test가 통과하고 `failures=0`, `errors=0`, `skipped=0`.

- [ ] **Step 6: implementation과 회귀 테스트를 커밋한다**

```bash
git add scripts/verify-post-publish-next-development-line.py \
  tests/test_post_publish_next_development_line.py
git commit -m "SNAPSHOT catalog ref의 안전한 전진을 허용한다" \
  -m "Constraint: settings와 CI ref 일치 및 minimum-to-HEAD ancestry를 모두 검증한다
Rejected: manifest exact SHA equality | 정상적인 downstream forward drift가 중앙 CI를 깨뜨린다
Confidence: high
Scope-risk: moderate
Directive: stable release의 exact candidate 계약은 완화하지 않는다
Tested: Python 3.13 post-publish next-development-line unit tests
Not-tested: 실제 workspace와 GitHub Actions 검증은 후속 단계에서 수행한다"
```

### Task 3: CI full-history 계약과 운영 문서 고정

**Files:**
- Modify: `tests/test_post_publish_next_development_line.py`
- Modify: `.github/workflows/ci.yml:60-72`
- Modify: `docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md:7-12`
- Modify: `docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md:47-56`

- [ ] **Step 1: Build BOM checkout의 full-history 회귀 테스트를 추가한다**

```python
def test_build_bom_checkout_fetches_full_history_for_catalog_ancestry(self) -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    build_job = workflow.split("\n  build:\n", maxsplit=1)[1].split(
        "\n  publication-pom-contract:\n", maxsplit=1
    )[0]

    self.assertRegex(
        build_job,
        r"- uses: actions/checkout@v7\n\s+with:\n\s+fetch-depth: 0",
    )
```

- [ ] **Step 2: checkout 회귀 테스트가 RED인지 확인한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest \
  tests.test_post_publish_next_development_line.PostPublishNextDevelopmentLineTest.test_build_bom_checkout_fetches_full_history_for_catalog_ancestry
```

Expected: `fetch-depth: 0`이 `build` job checkout에 없어 `FAILED (failures=1)`.

- [ ] **Step 3: Build BOM checkout에 전체 history를 요청한다**

`.github/workflows/ci.yml`의 `build` job 첫 checkout을 다음과 같이 바꾼다.

```yaml
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
```

- [ ] **Step 4: release checklist에서 minimum 의미와 불변 경계를 명시한다**

범위 항목을 다음 문구로 교체한다.

```markdown
- 중앙 catalog 기본 minimum ref: `91f9ea9336b5ea991f5675323a1cf25ccfd6f5ed`
- 중앙 catalog minimum ref 예외: `bluetape4k-exposed`, `bluetape4k-graph`는
  `df64293753a9491b337852a158f89d4a93a1734a`
- SNAPSHOT consumer 실제 ref: 저장소별 minimum과 같거나 그 후속이며, 현재 중앙 candidate `HEAD`의 조상이어야 함
```

버전 계약 표의 SNAPSHOT catalog 행은 다음 문구로 교체한다.

```markdown
| SNAPSHOT catalog | manifest의 immutable SHA를 저장소별 minimum으로 사용하고, settings/CI가 일치하는 `minimum <= actual <= candidate HEAD`만 허용 |
```

- [ ] **Step 5: targeted suite와 문서 감사를 실행한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest tests.test_post_publish_next_development_line
node /Users/debop/.codex/skills/bluetape-writer/scripts/audit-korean-terms.mjs \
  docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md
```

Expected: unit tests `failures=0`, `errors=0`, `skipped=0`; terminology audit `findings=0`.

- [ ] **Step 6: CI와 운영 문서 변경을 커밋한다**

```bash
git add .github/workflows/ci.yml \
  tests/test_post_publish_next_development_line.py \
  docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md
git commit -m "catalog ancestry 검사의 CI 재현성을 보장한다" \
  -m "Constraint: Build BOM job은 minimum과 consumer ref의 Git object를 모두 가져와야 한다
Rejected: shallow checkout 유지 | ancestry 실패와 object 부재를 구분할 수 없다
Confidence: high
Scope-risk: narrow
Directive: snapshot-catalog-ref key는 호환성을 위해 유지하고 minimum 의미로 해석한다
Tested: Python 3.13 targeted tests and Korean terminology audit
Not-tested: GitHub-hosted runner execution is verified after PR creation"
```

### Task 4: 전체 로컬 검증과 exact-head PR 전달

**Files:**
- Verify: `scripts/verify-post-publish-next-development-line.py`
- Verify: `tests/test_post_publish_next_development_line.py`
- Verify: `.github/workflows/ci.yml`
- Verify: `docs/releases/2026-08-21-dependencies-2.0.0-snapshot-consumer-checklist.md`
- Verify unchanged: `config/post-publish-next-development-line.json`

- [ ] **Step 1: Python 전체 suite를 실행한다**

Run:

```bash
/opt/homebrew/bin/python3.13 -m unittest discover -s tests -p 'test_*.py'
```

Expected: 모든 test가 통과하고, 기존 network-dependent skip 외 새 skip은 없다.

- [ ] **Step 2: 실제 workspace에서 consumer와 catalog governance를 검증한다**

Run:

```bash
/opt/homebrew/bin/python3.13 scripts/verify-post-publish-next-development-line.py \
  --workspace .. --summary
scripts/sync-managed-catalog.py --check --summary
scripts/sync-shared-versions.py --workspace .. --check --summary
scripts/sync-dependabot-ignores.py --workspace .. --check --summary
```

Expected: consumer boundary가 9 SNAPSHOT libraries, 3 official-release examples, 2 development-SNAPSHOT examples로 통과하고 모든 sync guard가 clean.

- [ ] **Step 3: cross-repository publication POM gate를 실행한다**

Run:

```bash
scripts/verify-publication-poms.py --workspace .. --summary
```

Expected: 등록된 publisher 전체 POM의 dependency-management version과 effective model이 통과하고 `failures=0`.

- [ ] **Step 4: Gradle, workflow 문법, diff를 검증한다**

Run:

```bash
./gradlew build --no-daemon --no-configuration-cache
actionlint .github/workflows/ci.yml
git diff --check origin/develop...HEAD
git status --short
```

Expected: Gradle build와 `actionlint`가 성공하고, whitespace error가 없으며, 계획된 파일 외 변경이 없다.

- [ ] **Step 5: 독립 review와 exact-head 상태를 확인한다**

독립 reviewer는 다음 범위를 검토한다.

```text
Compare origin/develop...HEAD. Verify that SNAPSHOT consumers may advance only when
settings and CI use the same lowercase 40-character SHA and
minimum <= actual <= candidate HEAD. Verify stable release behavior is unchanged.
Report only actionable findings with file and line evidence.
```

Run:

```bash
git rev-parse HEAD
git status --short
git log --oneline --decorate origin/develop..HEAD
```

Expected: worktree가 clean이고 review P0/P1 finding이 없으며 exact head SHA가 기록된다.

- [ ] **Step 6: 승인된 head/base로 PR을 생성한다**

Run:

```bash
git push -u origin fix/issue-213-snapshot-ref-drift
gh pr create \
  --repo bluetape4k/bluetape4k-dependencies \
  --base develop \
  --head fix/issue-213-snapshot-ref-drift \
  --assignee debop \
  --title "SNAPSHOT catalog ref의 안전한 전진을 허용한다" \
  --body-file /tmp/bluetape4k-dependencies-issue-213-pr.md
```

PR 본문은 한국어로 문제, `minimum <= actual <= candidate HEAD` 계약, 테스트 증거, `Refs #213`를 기록하고 마지막을 다음 섹션으로 끝낸다.

```markdown
## DoD Status

- [x] forward drift, rollback, parity mismatch, history 이탈 회귀 테스트
- [x] Python 전체 suite와 실제 workspace consumer guard
- [x] catalog sync, publication POM, Gradle build, actionlint
- [ ] exact-head GitHub Actions CI
- [ ] fresh merge 승인
```

- [ ] **Step 7: exact-head CI를 확인하고 merge-ready에서 정지한다**

Run:

```bash
gh pr checks --repo bluetape4k/bluetape4k-dependencies --watch <PR_NUMBER>
gh pr view --repo bluetape4k/bluetape4k-dependencies <PR_NUMBER> \
  --json headRefOid,baseRefName,mergeable,reviewDecision,statusCheckRollup
```

Expected: PR `headRefOid`가 Step 5의 SHA와 같고 모든 required check가 terminal success. merge, tag, workflow dispatch, publication은 실행하지 않는다.

## 자체 검토 결과

- 설계의 네 가지 consumer 조건은 Task 1과 Task 2에 각각 회귀 테스트와 구현 단계가 있다.
- stable exact candidate 계약은 `verify_stable()`을 수정하지 않고 전체 suite에서 보존한다.
- full history 요구는 Task 3의 RED/GREEN 테스트와 CI 수정으로 고정한다.
- 실제 workspace, publication POM, Gradle, workflow lint, 독립 review, exact-head CI는 Task 4에서 순차 검증한다.
- manifest key와 SHA 값은 변경하지 않아 기존 release train의 version authority를 보존한다.
