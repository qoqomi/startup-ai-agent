# rag/rag_system.py (개선 버전 - 캐싱 추가)
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()


class RAGSystem:
    """RAG 시스템 - 캐싱 지원"""

    def __init__(self, doc_dir: str = "documents"):
        self.doc_dir = Path(doc_dir)
        self.doc_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.doc_dir / "faiss_index"
        self.vectorstore = None

        self.embeddings = HuggingFaceEmbeddings(
            model_name="jhgan/ko-sroberta-multitask",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def load_documents(self) -> List:
        """documents/ 폴더의 지원 파일 로드"""
        print("\n[INFO] 문서 로드 중...")

        docs = []
        patterns = ["*.pdf", "*.PDF", "*.docx", "*.DOCX", "*.txt", "*.md", "*.MD"]
        files = []
        for pattern in patterns:
            files.extend(sorted(self.doc_dir.glob(pattern)))

        if not files:
            print(f"[WARN] {self.doc_dir} 폴더에 사용 가능한 문서가 없습니다.")
            return []

        for file_path in sorted(files):
            loader = self._resolve_loader(file_path)
            if not loader:
                print(f"[WARN] 지원되지 않는 형식: {file_path.name}")
                continue

            print(f"  - {file_path.name}")
            try:
                loaded_docs = loader.load()
            except Exception as exc:
                print(f"[ERROR] 로드 실패 ({file_path.name}): {exc}")
                continue

            for doc in loaded_docs:
                doc.metadata.setdefault("source_file", file_path.name)

            docs.extend(loaded_docs)

        print(f"[SUCCESS] {len(docs)}개 문서 청크 로드 완료")
        return docs

    def _resolve_loader(self, path: Path):
        """파일 확장자에 맞는 로더 반환"""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return PyPDFLoader(str(path))
        if suffix == ".docx":
            return Docx2txtLoader(str(path))
        if suffix in {".txt", ".md"}:
            return TextLoader(str(path), autodetect_encoding=True)
        return None

    def build(self):
        """벡터 스토어 구축 (캐시 우선)"""
        print("\n[INFO] RAG 시스템 구축 중...")

        # 캐시 존재 시 로드
        if self.cache_path.exists():
            print("[INFO] 기존 벡터 스토어 로드 중...")
            try:
                self.vectorstore = FAISS.load_local(
                    str(self.cache_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                print("[SUCCESS] 캐시 로드 완료\n")
                return
            except Exception as e:
                print(f"[WARN] 캐시 로드 실패: {e}, 재생성 진행")

        # 새로 생성
        docs = self.load_documents()
        if not docs:
            print("[WARN] 문서 없음, 벡터 스토어 미생성")
            self.vectorstore = None
            return

        print("\n[INFO] 텍스트 분할 중...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
        )
        splits = text_splitter.split_documents(docs)
        print(f"[SUCCESS] {len(splits)}개 청크 생성")

        print("\n[INFO] 벡터 스토어 생성 중...")
        self.vectorstore = FAISS.from_documents(splits, self.embeddings)

        # 캐시 저장
        print("[INFO] 벡터 스토어 저장 중...")
        self.vectorstore.save_local(str(self.cache_path))
        print("[SUCCESS] 벡터 스토어 저장 완료\n")

    def search(self, query: str, k: int = 5) -> str:
        """검색 - 결과 품질 향상"""
        if not self.vectorstore:
            return "[ERROR] Vector store not initialized"

        # 유사도 검색
        docs = self.vectorstore.similarity_search(query, k=k)

        if not docs:
            print(f"[WARN] 검색 결과 없음: '{query}'")
            return ""

        # 결과 포맷팅 (더 많은 정보)
        results = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source_file", "Unknown")
            page = doc.metadata.get("page", "?")
            content = doc.page_content.strip()

            # 너무 길면 자르되, 마지막 문장은 완성
            if len(content) > 500:
                content = content[:500]
                last_period = content.rfind(".")
                if last_period > 0:
                    content = content[: last_period + 1]
                content += "..."

            results.append(f"[결과 {i} | 출처: {source}, p.{page}]\n{content}")

        return "\n\n---\n\n".join(results)

    def get_stats(self) -> dict:
        """벡터 스토어 통계"""
        if not self.vectorstore:
            return {"status": "not_initialized"}

        return {
            "status": "ready",
            "num_vectors": self.vectorstore.index.ntotal,
            "cache_exists": self.cache_path.exists(),
        }
