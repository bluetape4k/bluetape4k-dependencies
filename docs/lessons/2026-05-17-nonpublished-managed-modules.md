# 발행하지 않는 관리 대상 모듈

## 배경

`bluetape4k-dependencies`는 인접 저장소에서 카탈로그 별칭과 BOM 제약 조건을
생성한다. 생성기는 업스트림 BOM과 동일한 발행 가능 모듈 정책을 사용해야 한다.

## 결정

`scripts/sync-managed-catalog.py`에서 `examples/`, `*-examples`, `*-demo`,
`benchmark/`, `*-benchmark` 모듈을 제외한 다음 관리 카탈로그와 제약 조건 블록을
다시 생성한다.

## 결과

생성된 graph 모듈 집합에서 벤치마크 별칭과 제약 조건이 제거되었으며, 앞으로
발행하지 않는 모듈은 dependencies BOM에 포함되지 않는다.

## 검증

- `python3 -m unittest tests/test_sync_managed_catalog.py`
- `scripts/sync-managed-catalog.py --write --check --summary`
- `./gradlew generatePomFileForBluetapeDependenciesPublication generatePomFileForBluetapeVersionCatalogPublication --no-daemon --no-configuration-cache --no-build-cache`
- 생성된 dependencies 메타데이터를 검사한 결과 `examples`, `demo`,
  `benchmark` 항목이 없었다.
