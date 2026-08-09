# Phase 1: 실제 문서 수집 및 색인

## 목표

예제 3건 대신 `tax.docx` 원문을 Chroma 벡터 검색 대상으로 사용한다.

## 처리 흐름

```text
tax.docx
  -> 조문 파싱
  -> data/processed/tax_articles.json
  -> 구조 기반 청킹
  -> Ollama 임베딩
  -> chroma_db
```

## 1. 정규화

```bash
python scripts/ingest.py
```

- 현행 조문 325개 생성
- 장·절·조문·시행일·원본 해시 보존
- 부칙과 미래 시행 조문 제외

## 2. 청킹

- 최대 길이: 1,800자
- 짧은 조문: 조문 전체를 한 청크로 사용
- 긴 조문: 항·호 경계를 우선해 분할
- 분할된 청크에도 법령명·조문 번호·제목 반복
- 결과: 325개 조문 -> 354개 청크

## 3. 색인

```bash
ollama pull snowflake-arctic-embed2
python scripts/index.py
```

- 기본 임베딩: `snowflake-arctic-embed2`
- 청크 ID를 고정적으로 생성
- 원본 SHA-256과 임베딩 모델을 Chroma 메타데이터에 저장
- 동일한 원본·모델·청크가 이미 있으면 `skipped`
- 원본이나 모델이 바뀌면 기존 컬렉션을 재생성

## 4. 검색 확인

```bash
python scripts/search.py "소득은 어떻게 구분되나요?"
python scripts/search.py "소득세 과세기간은?"
python scripts/search.py "근로소득 원천징수영수증은 언제 발급하나요?"
```

검증 결과:

- 소득 구분 -> 제4조 1위
- 과세기간 -> 제5조 1위
- 근로소득 원천징수영수증 -> 제143조 1위

## 임베딩 모델 검증 기록

- `bge-m3`: 현재 Ollama 환경에서 일부 한국어 법령 문장이 `NaN` 오류를 반환
- `nomic-embed-text`: 색인은 성공했으나 한국어 검색 품질이 기준에 미달
- `snowflake-arctic-embed2`: 색인 성공 및 핵심 질문 3개 검색 기준 통과

핵심 학습 포인트: 임베딩 모델은 이름만 보고 선택하지 않고, 실제 데이터와 기준 질문으로 검증해야 한다.
