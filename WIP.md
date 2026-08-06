# WIP - bluetape4k-dependencies

Snapshot: 2026-08-06 KST
Scope: dependencies 1.5.0 개발선.

## 현재 상태

`bluetape4k-dependencies:1.4.0` 안정 배포 train은 완료됐다. 선행 라이브러리
8개, 최종 catalog `catalog/2026-08-06-03`, dependencies BOM, GitHub Release,
Maven Central metadata와 Central-only consumer를 모두 검증했다. issue #168과
#171 및 milestone `1.4.0`도 최종 증거와 함께 닫았다.

현재 개발 버전은 `1.5.0`이다. `snapshotVersion`은 비워 두며, 다음 catalog
train이 승인되기 전에는 새로운 stable tag나 publication을 만들지 않는다.

## 1.4.0 완료 증거

- Release PR #174 merge: `8a738f084de98323b5651c548b9d2c354fb22329`.
- PR CI `31079582802`, post-merge CI `31080318880`: PASS.
- GitHub-valid signed tag: `1.4.0`, exact merge로 peel 확인.
- Publish Release run `31081143359`: PASS.
- Maven Central POM/module: HTTP 200.
- 공개 POM: 77 dependency-management entries, 18 imported BOMs,
  missing version 0, SNAPSHOT 0, SHA-256
  `d6b4305d5fba5ec960532b34864254fd9ed844cb67adbecff1d00eca8f0eb967`.
- Central-only consumer: 8개 대표 Bluetape 모듈의 versionless resolution PASS.
- Type P receipt: `20260806T074128Z-5d92140b`, sequence 14, checksum
  `733c25592a3d02437e1b0686769cf93152b30c3c1c78035628389a1d7161c69c`.

## 다음 우선순위

1. 외부 dependency/plugin 변경은 중앙 catalog authority와 delta receipt를 먼저
   갱신한다.
2. 관리 저장소는 immutable catalog ref를 사용하고, 예외가 필요한 경우에만
   명시적 authority record를 추가한다.
3. 다음 stable train은 새 release checklist와 explicit publication authority를
   확보한 뒤 시작한다.

`bluetape4k-workshop`과 예제/application 저장소는 stable publication scope에서
계속 제외한다. `bluetape4k-experimental`은 catalog-only consumer로 유지한다.
