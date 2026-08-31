# Routine SNAPSHOT Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 9개 JVM publisher가 사용자 입력 없이 event source SHA를 발행하게 하고, 반복 SNAPSHOT을 막는 reviewer·handoff 절차와 중복 PR을 제거한다.

**Architecture:** 자동 실행은 `workflow_run.head_sha`, 수동 실행은 `github.sha`를 단일 source identity로 사용한다. 기존 action-pin PR 8개에 자동 SHA 변경을 통합하고 Projects PR `#1584`만 별도로 유지해 저장소마다 생존 PR을 하나로 줄인다. Stable release exact-candidate 계약, environment secret, develop branch policy, immutable action ref는 변경하지 않는다.

**Tech Stack:** GitHub Actions YAML, Python `unittest`, `actionlint`, GitHub REST API via `gh`, Gradle publication workflows

---

## 파일 구조와 생존 PR

| 저장소 | 작업 worktree / PR | 수정 파일 | 책임 |
| --- | --- | --- | --- |
| Projects | `.worktrees/fix/issue-1578-snapshot-source` / `#1584` | `.github/workflows/publish-snapshot.yml`, `scripts/test_release_workflow_policy.py`, `docs/lessons/2026-08-31-issue-1578-snapshot-source-identity.md` | 수동 입력·TenantContext receipt 제거, dispatch SHA 회귀 방지 |
| AWS | `.worktrees/fix/issue-1578-action-pinning` / `#604` | `.github/workflows/publish-snapshot.yml` | 자동·수동 event SHA checkout |
| Dependencies | `.worktrees/fix/issue-1578-action-pinning` / `#222` | `.github/workflows/publish-snapshot.yml`, 본 설계·계획 문서 | 자동·수동 event SHA checkout, 생태계 결정 기록 |
| Exposed | `.worktrees/fix/issue-1578-action-pinning` / `#773` | `.github/workflows/publish-snapshot.yml` | default-branch checkout 제거 |
| Graph | `.worktrees/fix/issue-1578-action-pinning` / `#598` | `.github/workflows/publish-snapshot.yml` | 고정 `develop` checkout 제거 |
| Image | `.worktrees/fix/issue-1578-action-pinning` / `#617` | `.github/workflows/publish-snapshot.yml` | 수동 Nightly run 입력 제거, 자동 Nightly job 검증 유지 |
| Javers | `.worktrees/fix/issue-1578-action-pinning` / `#361` | `.github/workflows/publish-snapshot.yml` | 자동·수동 event SHA checkout |
| Leader | `.worktrees/fix/issue-1578-action-pinning` / `#849` | `.github/workflows/publish-snapshot.yml` | 자동·수동 event SHA checkout |
| Text | `.worktrees/fix/issue-1578-action-pinning` / `#312` | `.github/workflows/publish-snapshot.yml` | 자동·수동 event SHA checkout |

중복 source PR `#605`, `#223`, `#774`, `#599`, `#618`, `#362`, `#850`,
`#313`은 생존 PR의 동등한 exact-head CI가 준비된 뒤 닫는다. PR 병합은 이
계획의 자동 실행 범위가 아니며 fresh exact-head 승인을 받기 전에 정지한다.

### Task 1: 실행 전 live state와 write scope 고정

**Files:**
- Verify only: 위 표의 11개 파일

- [ ] **Step 1: 모든 생존 worktree가 clean인지 확인**

```bash
for spec in \
  'bluetape4k-projects fix/issue-1578-snapshot-source' \
  'bluetape4k-aws fix/issue-1578-action-pinning' \
  'bluetape4k-dependencies fix/issue-1578-action-pinning' \
  'bluetape4k-exposed fix/issue-1578-action-pinning' \
  'bluetape4k-graph fix/issue-1578-action-pinning' \
  'bluetape4k-image fix/issue-1578-action-pinning' \
  'bluetape4k-javers fix/issue-1578-action-pinning' \
  'bluetape4k-leader fix/issue-1578-action-pinning' \
  'bluetape4k-text fix/issue-1578-action-pinning'
do
  repo="${spec%% *}"
  branch="${spec#* }"
  git -C "/Users/debop/work/bluetape4k/$repo/.worktrees/$branch" status --short --branch
done
```

Expected: Dependencies만 승인된 설계·계획 commit 때문에 upstream보다 앞서며,
모든 worktree에 미추적·미커밋 파일이 없다.

- [ ] **Step 2: 생존 PR의 exact head를 기록**

```bash
gh pr view 1584 --repo bluetape4k/bluetape4k-projects --json state,headRefOid,baseRefName
gh pr view 604 --repo bluetape4k/bluetape4k-aws --json state,headRefOid,baseRefName
gh pr view 222 --repo bluetape4k/bluetape4k-dependencies --json state,headRefOid,baseRefName
gh pr view 773 --repo bluetape4k/bluetape4k-exposed --json state,headRefOid,baseRefName
gh pr view 598 --repo bluetape4k/bluetape4k-graph --json state,headRefOid,baseRefName
gh pr view 617 --repo bluetape4k/bluetape4k-image --json state,headRefOid,baseRefName
gh pr view 361 --repo bluetape4k/bluetape4k-javers --json state,headRefOid,baseRefName
gh pr view 849 --repo bluetape4k/bluetape4k-leader --json state,headRefOid,baseRefName
gh pr view 312 --repo bluetape4k/bluetape4k-text --json state,headRefOid,baseRefName
```

Expected: 9개 모두 `OPEN`, base `develop`; 변경 전 head를 실행 기록에 보존한다.

### Task 2: Projects 정책 테스트를 input-free 계약으로 전환

**Files:**
- Modify: `/Users/debop/work/bluetape4k/bluetape4k-projects/.worktrees/fix/issue-1578-snapshot-source/scripts/test_release_workflow_policy.py`

- [ ] **Step 1: guarded publish 상수를 제거하고 공통 검증의 expected guard를 `None`으로 변경**

```python
workflow_jobs = {
    "ci.yml": ("build", None),
    "release.yml": ("publish", None),
    "publish-snapshot.yml": ("publish", None),
}
```

`SNAPSHOT_PUBLISH_JOB_IF` 상수는 삭제한다.

- [ ] **Step 2: `snapshot_policy_errors()`를 input-free 계약으로 교체**

```python
def snapshot_policy_errors(workflow: str) -> list[str]:
    errors = privileged_action_ref_errors(workflow)
    snapshot_runs = workflow_step_runs(workflow, "publish", "Publish SNAPSHOT")
    snapshot_command_valid = snapshot_runs == [(SNAPSHOT_PUBLICATION_RUN, False)]
    snapshot_task_count = publication_task_invocation_count(
        workflow, "nmcpPublishAggregationToCentralPortalSnapshots"
    )
    if not snapshot_command_valid:
        errors.append("snapshot workflow must invoke the exact Maven snapshot task")
    if snapshot_task_count != 1:
        errors.append(
            "snapshot publication task must have exactly one executable invocation"
        )
    if GITHUB_RELEASE.search(workflow) or ISSUE_RELEASE_MACHINERY.search(workflow):
        errors.append("snapshot workflow must not contain release or issue-specific machinery")
    if "contents: write" in workflow or "issues: write" in workflow:
        errors.append("snapshot workflow must not request repository write permissions")
    if job_ids(workflow) != {"publish"}:
        errors.append("snapshot workflow must contain only the publication job")
    errors.extend(publication_validation_errors(workflow, "publish"))
    if not snapshot_command_valid:
        errors.append("snapshot publication must disable the configuration cache")
    if "workflow_run:" in workflow or "github.event.workflow_run" in workflow:
        errors.append("projects snapshot workflow must remain manual dispatch only")
    if "workflow_dispatch:" not in workflow:
        errors.append("snapshot workflow must be manually dispatchable")
    for removed_input in (
        "verified_ci_run_id",
        "expected_head_sha",
        "handoff_issue_number",
        "validation_run_id",
    ):
        if removed_input in workflow:
            errors.append(f"snapshot workflow must not require {removed_input}")
    for removed_machinery in (
        "validate-full-nightly:",
        "record-handoff:",
        "create_snapshot_handoff.py",
        "tenant-context-handoff",
        "gh issue comment",
        "#1562",
    ):
        if removed_machinery in workflow:
            errors.append(f"snapshot workflow must not contain {removed_machinery}")
    if "environment: maven-central-release" not in workflow:
        errors.append("snapshot publication must use the protected Maven Central environment")
    if "          ref: ${{ github.sha }}" not in workflow:
        errors.append("snapshot publication must checkout the dispatch SHA")
    if "EXPECTED_HEAD_SHA: ${{ github.sha }}" not in workflow:
        errors.append("snapshot publication must verify the dispatch SHA")
    if "git rev-parse HEAD" not in workflow:
        errors.append("snapshot publication must verify the exact checkout SHA")
    if "SOURCE_SHA: ${{ github.sha }}" not in workflow:
        errors.append("snapshot summary must record the dispatch SHA")
    return errors
```

- [ ] **Step 3: exact-head/handoff tests를 다음 회귀 테스트로 교체**

```python
def test_snapshot_workflow_is_manual_and_input_free(self) -> None:
    workflow = (WORKFLOWS / "publish-snapshot.yml").read_text(encoding="utf-8")
    self.assertIn("workflow_dispatch:", workflow)
    self.assertNotIn("workflow_run:", workflow)
    for removed in (
        "verified_ci_run_id", "expected_head_sha", "handoff_issue_number",
        "validation_run_id", "validate-full-nightly:", "record-handoff:", "#1562",
    ):
        self.assertNotIn(removed, workflow)
    self.assertEqual([], snapshot_policy_errors(workflow))

def test_snapshot_checkout_uses_dispatch_sha(self) -> None:
    workflow = (WORKFLOWS / "publish-snapshot.yml").read_text(encoding="utf-8")
    self.assertIn("ref: ${{ github.sha }}", workflow)
    self.assertIn("EXPECTED_HEAD_SHA: ${{ github.sha }}", workflow)
    self.assertIn('test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"', workflow)
    self.assertIn("SOURCE_SHA: ${{ github.sha }}", workflow)

def test_snapshot_publication_rejects_checkout_source_drift(self) -> None:
    workflow = (WORKFLOWS / "publish-snapshot.yml").read_text(encoding="utf-8")
    mutated = workflow.replace("          ref: ${{ github.sha }}", "          ref: develop", 1)
    self.assertIn(
        "snapshot publication must checkout the dispatch SHA",
        snapshot_policy_errors(mutated),
    )

def test_snapshot_workflow_has_no_issue_handoff(self) -> None:
    workflow = (WORKFLOWS / "publish-snapshot.yml").read_text(encoding="utf-8")
    self.assertNotIn("issues: write", workflow)
    self.assertNotIn("create_snapshot_handoff.py", workflow)
    self.assertNotIn("tenant-context-handoff", workflow)
    self.assertNotIn("gh issue comment", workflow)
```

`test_publication_jobs_reject_execution_guard_bypasses`의 Snapshot fixture는
`publish:` 바로 아래에 `if: false` 또는 `continue-on-error: true`를 삽입한다.

- [ ] **Step 4: RED 확인**

```bash
python3 -B -m scripts.test_release_workflow_policy
```

Expected: 새 input-free assertions가 현재 3-input, 3-job workflow 때문에 실패한다.

### Task 3: Projects workflow와 lesson을 최소 계약으로 교체

**Files:**
- Modify: `/Users/debop/work/bluetape4k/bluetape4k-projects/.worktrees/fix/issue-1578-snapshot-source/.github/workflows/publish-snapshot.yml`
- Modify: `/Users/debop/work/bluetape4k/bluetape4k-projects/.worktrees/fix/issue-1578-snapshot-source/docs/lessons/2026-08-31-issue-1578-snapshot-source-identity.md`

- [ ] **Step 1: publication workflow를 다음 단일 job 구조로 교체**

```yaml
name: Publish Snapshot

permissions:
  contents: read

on:
  workflow_dispatch:

concurrency:
  group: publish-snapshot
  cancel-in-progress: false

env:
  JAVA_VERSION: '25'
  JAVA_DISTRIBUTION: 'temurin'
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'

jobs:
  publish:
    name: Publish SNAPSHOT to Maven Central
    permissions:
      contents: read
    runs-on: ubuntu-latest
    environment: maven-central-release
    timeout-minutes: 50
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          ref: ${{ github.sha }}
          fetch-depth: 0

      - name: Verify exact checkout
        env:
          EXPECTED_HEAD_SHA: ${{ github.sha }}
        run: test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"

      - uses: actions/setup-java@dd06d9cba3e5552c54d9f8ea23572deb30010f7c # v6.0.0
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: ${{ env.JAVA_DISTRIBUTION }}

      - uses: gradle/actions/setup-gradle@9c971963bec38e04b3d30dcc455b5382be2fdbfb # v6.3.0
        with:
          gradle-version: wrapper
          cache-read-only: true

      - name: Validate publication metadata
        timeout-minutes: 10
        run: |
          ./gradlew generatePomFileForBluetape4kPublication checkPomFileForBluetape4kPublication generateMetadataFileForBluetape4kPublication \
            -PsnapshotVersion=-SNAPSHOT \
            --no-daemon --no-configuration-cache --no-build-cache
          ruby scripts/publication/validate_poms.rb
          ruby scripts/publication/validate_module_metadata.rb

      - name: Publish SNAPSHOT
        timeout-minutes: 25
        run: >-
          ./gradlew nmcpPublishAggregationToCentralPortalSnapshots
          -PsnapshotVersion=-SNAPSHOT
          --no-daemon
          --no-configuration-cache
          --no-build-cache
        env:
          GRADLE_OPTS: "-Dorg.gradle.daemon=false"
          CENTRAL_USERNAME: ${{ secrets.CENTRAL_USERNAME }}
          CENTRAL_PASSWORD: ${{ secrets.CENTRAL_PASSWORD }}
          SIGNING_KEY_ID: ${{ secrets.SIGNING_KEY_ID }}
          SIGNING_KEY: ${{ secrets.SIGNING_KEY }}
          SIGNING_PASSWORD: ${{ secrets.SIGNING_PASSWORD }}

      - name: Summarize publication source
        env:
          SOURCE_SHA: ${{ github.sha }}
        run: |
          {
            echo "## SNAPSHOT publication"
            echo
            echo "- event: \`workflow_dispatch\`"
            echo "- source SHA: \`$SOURCE_SHA\`"
            echo "- repeated publication: allowed"
          } >> "$GITHUB_STEP_SUMMARY"
```

- [ ] **Step 2: lesson을 다음 결정과 실패 경계로 다시 작성**

```markdown
# 반복 SNAPSHOT source identity 단순화

## 결정

Projects의 수동 `Publish Snapshot`은 dispatch context의 `github.sha`를 직접
checkout하고 확인한다. CI run ID, 사용자가 복사한 SHA, handoff issue와
TenantContext 전용 receipt는 publication 입력이 아니다.

## 유지하는 경계

- Maven Central credential은 `maven-central-release` environment secret에서만 읽는다.
- external action은 immutable commit SHA를 사용한다.
- checkout 뒤 `git rev-parse HEAD`가 dispatch SHA와 다르면 publish 전에 실패한다.
- stable release exact candidate와 catalog checkpoint는 별도 release workflow에서 유지한다.

## 제거한 경계

- `verified_ci_run_id`, `expected_head_sha`, `handoff_issue_number`
- 특정 이슈 `#1562` 고정
- TenantContext public-resource receipt와 issue comment job
- 반복 SNAPSHOT을 stable handoff처럼 취급하는 승인 사슬
```

- [ ] **Step 3: GREEN 검증**

```bash
actionlint .github/workflows/publish-snapshot.yml
python3 -B -m scripts.test_release_workflow_policy
git diff --check origin/develop...HEAD
```

Expected: `actionlint` PASS, 정책 테스트 전체 PASS, whitespace error 0.

- [ ] **Step 4: Projects commit**

```bash
git add .github/workflows/publish-snapshot.yml scripts/test_release_workflow_policy.py docs/lessons/2026-08-31-issue-1578-snapshot-source-identity.md
git commit -m '반복 SNAPSHOT이 기능 handoff에 묶이지 않게 한다' \
  -m 'Constraint: stable release exact-candidate와 environment secret은 유지한다
Rejected: CI run ID와 SHA를 매번 입력 | workflow event가 이미 source identity를 제공한다
Confidence: high
Scope-risk: moderate
Directive: Projects Snapshot은 dispatch SHA만 checkout하고 특정 기능 이슈를 참조하지 않는다
Tested: actionlint; release workflow policy suite; git diff --check
Not-tested: hosted publication과 Maven Central read-back'
```

### Task 4: 단순 publisher 7곳을 event SHA 계약으로 통합

**Files:**
- Modify: AWS, Dependencies, Exposed, Graph, Javers, Leader, Text의 생존 worktree `.github/workflows/publish-snapshot.yml`

- [ ] **Step 1: 각 checkout에 동일 expression과 검증 step 적용**

각 저장소의 pinned `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7` 줄은 유지하고 바로
아래를 다음 구조로 맞춘다. Dependencies의 기존 `fetch-depth: 0`은 유지한다.

```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          ref: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}

      - name: Verify exact checkout
        env:
          EXPECTED_HEAD_SHA: ${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}
        run: test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"
```

Graph의 `ref: develop`은 위 expression으로 교체한다. 다른 build, publication,
secret, environment 구문은 변경하지 않는다.

- [ ] **Step 2: 저장소별 정적 계약 검증**

각 worktree에서 실행한다.

```bash
actionlint .github/workflows/publish-snapshot.yml .github/workflows/release.yml
python3 - <<'PY'
from pathlib import Path

workflow = Path('.github/workflows/publish-snapshot.yml').read_text(encoding='utf-8')
source = "${{ github.event_name == 'workflow_run' && github.event.workflow_run.head_sha || github.sha }}"
assert f"ref: {source}" in workflow
assert f"EXPECTED_HEAD_SHA: {source}" in workflow
assert 'git rev-parse HEAD' in workflow
assert 'ref: develop' not in workflow
assert 'environment: maven-central-release' in workflow
PY
git diff --check origin/develop...HEAD
```

Expected: 7개 저장소 모두 PASS; workflow source expression 2회 이상, mutable
`develop` checkout 0건.

- [ ] **Step 3: 저장소별 독립 commit**

각 저장소에서 파일 하나만 stage하고 다음 Lore 형식을 사용한다.

```bash
git add .github/workflows/publish-snapshot.yml
git commit -m '검증 event와 SNAPSHOT source가 어긋나지 않게 한다' \
  -m 'Constraint: 수동 SNAPSHOT 재발행은 허용하고 action SHA pin은 유지한다
Rejected: 기본 branch checkout | workflow_run 완료 뒤 HEAD가 이동할 수 있다
Confidence: high
Scope-risk: narrow
Directive: 자동 실행은 workflow_run.head_sha, 수동 실행은 github.sha를 사용한다
Tested: actionlint; event-SHA static contract; git diff --check
Not-tested: hosted publication과 Maven Central read-back'
```

### Task 5: Image의 수동 Nightly run 입력만 제거

**Files:**
- Modify: `/Users/debop/work/bluetape4k/bluetape4k-image/.worktrees/fix/issue-1578-action-pinning/.github/workflows/publish-snapshot.yml`

- [ ] **Step 1: RED 정적 검증 실행**

```bash
python3 - <<'PY'
from pathlib import Path

workflow = Path('.github/workflows/publish-snapshot.yml').read_text(encoding='utf-8')
assert 'validation_run_id:' not in workflow
assert 'override_full_validation:' not in workflow
assert 'head_sha=$DISPATCH_HEAD_SHA' in workflow
assert 'ref: ${{ needs.validate-full-nightly.outputs.head_sha }}' in workflow
assert 'git rev-parse HEAD' in workflow
PY
```

Expected: 현재 수동 입력과 checkout ref가 남아 있어 FAIL.

- [ ] **Step 2: `workflow_dispatch` 입력을 제거하고 manual branch를 자동 결정**

Workflow 상단은 다음과 같이 input-free로 만든다.

```yaml
on:
  workflow_run:
    workflows: ["Nightly"]
    types: [completed]
    branches: [develop]
  workflow_dispatch:
```

검증 step env와 script의 event 분기는 다음 계약을 사용한다.

```yaml
        env:
          GH_TOKEN: ${{ github.token }}
          EVENT_NAME: ${{ github.event_name }}
          WORKFLOW_RUN_ID: ${{ github.event.workflow_run.id }}
          WORKFLOW_RUN_CONCLUSION: ${{ github.event.workflow_run.conclusion }}
          WORKFLOW_RUN_HEAD_SHA: ${{ github.event.workflow_run.head_sha }}
          DISPATCH_HEAD_SHA: ${{ github.sha }}
        run: |
          set -euo pipefail

          if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
            echo "Manual SNAPSHOT publication uses dispatch SHA $DISPATCH_HEAD_SHA."
            echo "head_sha=$DISPATCH_HEAD_SHA" >> "$GITHUB_OUTPUT"
            echo "publish_eligible=true" >> "$GITHUB_OUTPUT"
            exit 0
          fi

          if [ "$WORKFLOW_RUN_CONCLUSION" != "success" ]; then
            echo "Nightly run $WORKFLOW_RUN_ID did not succeed: $WORKFLOW_RUN_CONCLUSION"
            echo "publish_eligible=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          if ! [[ "$WORKFLOW_RUN_HEAD_SHA" =~ ^[0-9a-f]{40}$ ]]; then
            echo "::error::Nightly run has no valid head SHA."
            exit 1
          fi

          validation_run_id="$WORKFLOW_RUN_ID"
          required_jobs=(
            "Test / image4j-java25"
            "Test / imageio-java25"
            "Test / kimagecombiner-java25"
            "Test / ocr-java25"
            "Test / images-vips-java25"
          )
          job_results="$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${validation_run_id}/jobs" \
            --paginate --jq '.jobs[] | [.name, .conclusion] | @tsv')"
          for required_job in "${required_jobs[@]}"; do
            if ! grep -Fqx "$required_job"$'\t'"success" <<< "$job_results"; then
              echo "::error::Required full validation job did not succeed: $required_job"
              exit 1
            fi
          done

          echo "Full OCR and VIPS validation succeeded in Nightly run $validation_run_id."
          echo "head_sha=$WORKFLOW_RUN_HEAD_SHA" >> "$GITHUB_OUTPUT"
          echo "publish_eligible=true" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 3: checkout과 summary를 output SHA에 연결**

```yaml
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7
        with:
          ref: ${{ needs.validate-full-nightly.outputs.head_sha }}

      - name: Verify exact checkout
        env:
          EXPECTED_HEAD_SHA: ${{ needs.validate-full-nightly.outputs.head_sha }}
        run: test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"
```

Publication 뒤에는 event와 output SHA만 summary에 기록한다. 수동 run ID,
override, issue handoff는 추가하지 않는다.

- [ ] **Step 4: GREEN 검증과 commit**

```bash
actionlint .github/workflows/publish-snapshot.yml .github/workflows/release.yml
python3 - <<'PY'
from pathlib import Path

workflow = Path('.github/workflows/publish-snapshot.yml').read_text(encoding='utf-8')
assert 'validation_run_id:' not in workflow
assert 'override_full_validation:' not in workflow
assert 'DISPATCH_HEAD_SHA: ${{ github.sha }}' in workflow
assert 'head_sha=$DISPATCH_HEAD_SHA' in workflow
assert 'head_sha=$WORKFLOW_RUN_HEAD_SHA' in workflow
assert 'ref: ${{ needs.validate-full-nightly.outputs.head_sha }}' in workflow
assert 'git rev-parse HEAD' in workflow
PY
git diff --check origin/develop...HEAD
git add .github/workflows/publish-snapshot.yml
git commit -m 'Image SNAPSHOT 재발행에 Nightly run 입력을 요구하지 않는다' \
  -m 'Constraint: 자동 Nightly의 OCR과 VIPS job 검증은 유지한다
Rejected: 수동 validation_run_id와 override | dispatch SHA가 이미 발행 source를 결정한다
Confidence: high
Scope-risk: moderate
Directive: 수동 실행은 github.sha, 자동 실행은 workflow_run.head_sha를 사용한다
Tested: actionlint; image event-SHA static contract; git diff --check
Not-tested: hosted publication과 Maven Central read-back'
```

### Task 6: 9개 environment에서 required reviewer만 제거

**Files:**
- GitHub environment state only: `maven-central-release`

- [ ] **Step 1: 변경 전 보호 규칙과 branch policy를 화면 출력으로 확인**

```bash
for repo in bluetape4k-projects bluetape4k-aws bluetape4k-dependencies bluetape4k-exposed bluetape4k-graph bluetape4k-image bluetape4k-javers bluetape4k-leader bluetape4k-text
do
  gh api "repos/bluetape4k/$repo/environments/maven-central-release" \
    --jq '[.name,.can_admins_bypass,.deployment_branch_policy,([.protection_rules[].type])]'
  gh api "repos/bluetape4k/$repo/environments/maven-central-release/deployment-branch-policies" \
    --jq '.branch_policies | map({name,type})'
done
```

Expected: reviewer rule 1개, branch policy rule, `develop` branch, secret 값은
응답에 포함되지 않는다.

- [ ] **Step 2: wait timer와 branch policy를 보존한 채 reviewer 배열만 비움**

```bash
for repo in bluetape4k-projects bluetape4k-aws bluetape4k-dependencies bluetape4k-exposed bluetape4k-graph bluetape4k-image bluetape4k-javers bluetape4k-leader bluetape4k-text
do
  gh api "repos/bluetape4k/$repo/environments/maven-central-release" |
    jq '{
      wait_timer: ([.protection_rules[] | select(.type == "wait_timer") | .wait_timer] | first // 0),
      prevent_self_review: false,
      reviewers: [],
      deployment_branch_policy: .deployment_branch_policy,
      can_admins_bypass: false
    }' |
    gh api --method PUT \
      "repos/bluetape4k/$repo/environments/maven-central-release" \
      --input - >/dev/null
done
```

Expected: API 2xx 9건. 기존 approval 대기 run은 취소하지 않으며 reviewer 제거로
각자 계속 실행될 수 있다.

- [ ] **Step 3: reviewer 제거와 보호 유지 read-back**

```bash
for repo in bluetape4k-projects bluetape4k-aws bluetape4k-dependencies bluetape4k-exposed bluetape4k-graph bluetape4k-image bluetape4k-javers bluetape4k-leader bluetape4k-text
do
  gh api "repos/bluetape4k/$repo/environments/maven-central-release" \
    --jq '{can_admins_bypass,reviewer_rules:[.protection_rules[]|select(.type=="required_reviewers")],deployment_branch_policy}'
  gh api "repos/bluetape4k/$repo/environments/maven-central-release/deployment-branch-policies" \
    --jq '.branch_policies | map({name,type})'
  gh api "repos/bluetape4k/$repo/environments/maven-central-release/secrets" \
    --jq '.secrets | map(.name) | sort'
done
```

Expected: `reviewer_rules=[]`, `can_admins_bypass=false`, `develop` policy 유지,
변경 전후 secret 이름 집합 동일.

### Task 7: 생존 PR push·본문 갱신 후 중복 PR 종료

**Files:**
- GitHub PR metadata only

- [ ] **Step 1: 9개 생존 branch를 각 upstream에 push**

```bash
git -C /Users/debop/work/bluetape4k/bluetape4k-projects/.worktrees/fix/issue-1578-snapshot-source push origin fix/issue-1578-snapshot-source
git -C /Users/debop/work/bluetape4k/bluetape4k-aws/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-dependencies/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-exposed/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-graph/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-image/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-javers/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-leader/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
git -C /Users/debop/work/bluetape4k/bluetape4k-text/.worktrees/fix/issue-1578-action-pinning push origin fix/issue-1578-action-pinning
```

Expected: non-force fast-forward 9건. `--force`를 사용하지 않는다.

- [ ] **Step 2: PR 본문을 실제 단일-PR 범위와 최신 head로 갱신**

Projects `#1584` 본문은 다음 내용으로 갱신한다.

```markdown
## 요약

반복 가능한 `2.0.0-SNAPSHOT` 발행을 특정 기능 handoff에서 분리합니다.
수동 실행은 dispatch SHA를 자동 checkout하고 검증하며, CI run ID, 사용자 입력
SHA, handoff issue와 TenantContext receipt를 요구하지 않습니다.

## 검증

- `actionlint .github/workflows/publish-snapshot.yml`
- `python3 -B -m scripts.test_release_workflow_policy`
- `git diff --check origin/develop...HEAD`

## DoD Status

Required checks: 로컬 PASS, hosted CI 확인 중

Final status: PENDING — exact-head hosted CI와 별도 merge 승인 대기
```

나머지 8개 생존 PR은 기존 본문을 보존하면서 `## What This Solves`에
`workflow_run.head_sha`와 `github.sha` 자동 선택을 추가하고, `## Validation`에
event-SHA 정적 계약 결과를 추가한다. 각 본문의 기존 `## DoD Status` head SHA는
push 뒤 live `headRefOid`로 교체한다.

- [ ] **Step 3: hosted CI가 exact head에서 terminal인지 확인**

```bash
for spec in \
  'bluetape4k-projects 1584' 'bluetape4k-aws 604' \
  'bluetape4k-dependencies 222' 'bluetape4k-exposed 773' \
  'bluetape4k-graph 598' 'bluetape4k-image 617' \
  'bluetape4k-javers 361' 'bluetape4k-leader 849' \
  'bluetape4k-text 312'
do
  repo="${spec%% *}"
  pr="${spec##* }"
  gh pr checks "$pr" --repo "bluetape4k/$repo" --watch
  gh pr view "$pr" --repo "bluetape4k/$repo" \
    --json headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
done
```

Expected: 9개 생존 PR의 새 exact head check failure 0. Dependencies의 failure가
현재 `develop` baseline과 동일하면 원인을 별도 복구하고, 실패 상태로 병합하거나
중복 PR을 닫지 않는다.

- [ ] **Step 4: 동등한 diff가 생존 PR에 있음을 확인하고 중복 PR 8개 종료**

```bash
gh pr close 605 --repo bluetape4k/bluetape4k-aws --comment '자동 event SHA 변경을 #604에 통합해 중복 PR을 닫습니다.'
gh pr close 223 --repo bluetape4k/bluetape4k-dependencies --comment '자동 event SHA 변경을 #222에 통합해 중복 PR을 닫습니다.'
gh pr close 774 --repo bluetape4k/bluetape4k-exposed --comment '자동 event SHA 변경을 #773에 통합해 중복 PR을 닫습니다.'
gh pr close 599 --repo bluetape4k/bluetape4k-graph --comment '자동 event SHA 변경을 #598에 통합해 중복 PR을 닫습니다.'
gh pr close 618 --repo bluetape4k/bluetape4k-image --comment '자동 SHA와 input-free 수동 실행을 #617에 통합해 중복 PR을 닫습니다.'
gh pr close 362 --repo bluetape4k/bluetape4k-javers --comment '자동 event SHA 변경을 #361에 통합해 중복 PR을 닫습니다.'
gh pr close 850 --repo bluetape4k/bluetape4k-leader --comment '자동 event SHA 변경을 #849에 통합해 중복 PR을 닫습니다.'
gh pr close 313 --repo bluetape4k/bluetape4k-text --comment '자동 event SHA 변경을 #312에 통합해 중복 PR을 닫습니다.'
```

Expected: 중복 PR 8개 `CLOSED`, source branch는 cleanup 단계까지 보존한다.

### Task 8: 불필요 이슈 정리와 merge-ready 정지

**Files:**
- GitHub issue metadata only

- [ ] **Step 1: 이미 완료됐거나 폐기된 강화 이슈 종료**

```bash
gh issue close 217 --repo bluetape4k/bluetape4k-dependencies \
  --comment 'Exposed tenant adapter의 central catalog 반영이 완료되어 닫습니다.'
gh issue close 1582 --repo bluetape4k/bluetape4k-projects \
  --comment '반복 가능한 SNAPSHOT에 stable exact-head handoff를 적용하지 않기로 결정했습니다. Stable release candidate 검증은 release 경계에서 유지합니다.'
```

Expected: Dependencies `#217`, Projects `#1582` `CLOSED`.

- [ ] **Step 2: 유지 이슈가 열린 상태인지 확인**

```bash
gh issue view 197 --repo bluetape4k/bluetape4k-dependencies --json state,milestone
gh issue view 1451 --repo bluetape4k/bluetape4k-projects --json state,milestone
```

Expected: 둘 다 `OPEN`; Dependencies `#197`은 Kotlin release 추적,
Projects `#1451`은 post-release milestone을 유지한다.

- [ ] **Step 3: merge-ready 보고 후 정지**

9개 PR 각각에 대해 exact head, terminal checks, mergeability, 미해결 thread,
environment read-back을 다시 확인한다. 이 시점에는 merge하지 않는다. 사용자에게
PR별 head SHA와 검증 결과를 제시하고 첫 merge 대상에 대한 fresh 승인을 받는다.

### Task 9: fresh 승인 뒤 순차 merge와 최종 이슈 종료

**Files:**
- GitHub PR/issue state only

- [ ] **Step 1: 각 PR을 합치기 직전에 exact-head 승인 재확인**

```bash
for spec in \
  'bluetape4k-projects 1584' 'bluetape4k-aws 604' \
  'bluetape4k-dependencies 222' 'bluetape4k-exposed 773' \
  'bluetape4k-graph 598' 'bluetape4k-image 617' \
  'bluetape4k-javers 361' 'bluetape4k-leader 849' \
  'bluetape4k-text 312'
do
  repo="${spec%% *}"
  pr="${spec##* }"
  gh pr view "$pr" --repo "bluetape4k/$repo" \
    --json headRefOid,baseRefOid,mergeable,mergeStateStatus,statusCheckRollup
done
```

Expected: 승인 시 제시한 head와 현재 head 동일, required failure 0. PR별로 fresh
승인을 따로 받으며 auto-merge를 사용하지 않는다.

- [ ] **Step 2: 승인된 PR만 병합**

승인된 PR 하나에 대해서만 다음 함수를 호출한다. `approved_head`에는 바로 전
사용자 승인 메시지에 제시한 40자리 SHA를 그대로 넣는다.

```bash
merge_approved_pr() {
  repo="$1"
  pr="$2"
  approved_head="$3"
  current_head="$(gh pr view "$pr" --repo "$repo" --json headRefOid --jq .headRefOid)"
  test "$current_head" = "$approved_head"
  gh pr merge "$pr" --repo "$repo" --rebase --match-head-commit "$approved_head"
  gh pr view "$pr" --repo "$repo" --json state,mergedAt,mergeCommit
}
```

병합 뒤 canonical `develop`과 PR state를 재확인하고 다음 PR 승인으로 이동한다.

- [ ] **Step 3: 구현이 실제 develop에 들어간 뒤 남은 이슈 종료**

```bash
gh issue close 769 --repo bluetape4k/bluetape4k-exposed \
  --comment 'Publish Snapshot이 workflow_run.head_sha를 checkout하고 검증하도록 반영되어 닫습니다.'
gh issue close 1578 --repo bluetape4k/bluetape4k-projects \
  --comment '9개 publisher의 action pin, 자동 source SHA, environment reviewer 단순화가 완료되어 닫습니다.'
```

Expected: Exposed `#769`, Projects `#1578` `CLOSED`.

- [ ] **Step 4: cleanup은 마지막에 별도 범위로 수행**

중복 source branch와 worktree는 모두 clean·merged/superseded임을 증명한 뒤에만
제거한다. 현재 진행 중인 Projects `#1561` worktree와 unrelated dirty state는
건드리지 않는다.

## 전체 검증 기준

- 9개 workflow에서 사용자 입력 SHA/run/issue가 0건이다.
- Projects는 repository 정책 회귀 test를, Image는 actionlint와 exact static
  contract 검증을 통과한다.
- 8개 automatic publisher의 checkout은 `workflow_run.head_sha`, manual dispatch는
  `github.sha`다.
- action ref는 모두 40자리 immutable SHA다.
- environment reviewer rule은 0건이고 secret 이름·develop policy·admin bypass
  설정은 유지된다.
- 승인 대기 중이던 SNAPSHOT run을 취소하지 않는다.
- 생존 PR 9개가 exact-head CI를 통과하고 중복 PR 8개가 닫힌다.
- Merge는 fresh approval 전 `PENDING`으로 남는다.
