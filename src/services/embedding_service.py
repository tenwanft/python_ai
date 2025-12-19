from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.utils.helpers import read_online_pdf_text
from src.core.config import settings

# 把文章切块
def split_text_into_chunks(text:str,chunk_size:int=10000,chunk_overlap:int =100)->list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return splitter.split_text(text)

# 使用 LangChain 的 HuggingFaceEmbeddings（本地模型，不需要 API Key）
# 选择通用中英文模型：moka-ai/m3e-base；如需更小英文模型可改为 BAAI/bge-small-en-v1.5
_DEF_MODEL = "moka-ai/m3e-base"
_DEF_MODEL_KWARGS = {"device": "cpu"}
_DEF_ENCODE_KWARGS = {"normalize_embeddings": True}

# 单条文本嵌入
def create_embedding(text:str)->list[float]:
    embedder = HuggingFaceEmbeddings(model_name=_DEF_MODEL, model_kwargs=_DEF_MODEL_KWARGS, encode_kwargs=_DEF_ENCODE_KWARGS)
    return embedder.embed_query(text)

# 获取（或创建）Chroma 向量库，绑定 HuggingFaceEmbeddings
def get_chroma_store(persist_directory:str = "vector_store/chroma_db", collection_name:str = "papers", embeddings: HuggingFaceEmbeddings | None = None) -> Chroma:
    if embeddings is None:
        embeddings = HuggingFaceEmbeddings(model_name=_DEF_MODEL, model_kwargs=_DEF_MODEL_KWARGS, encode_kwargs=_DEF_ENCODE_KWARGS)
    return Chroma(collection_name=collection_name, embedding_function=embeddings, persist_directory=persist_directory)

# 将文本块写入 Chroma，并返回写入的 id 列表
def add_text_chunks_to_chroma(chunks:list[str], store:Chroma, metadatas:list[dict] | None = None, ids:list[str] | None = None) -> list[str]:
    return store.add_texts(texts=chunks, metadatas=metadatas, ids=ids)

# 基于查询进行相似检索（支持按 metadata 过滤）
def query_similar_texts(query:str, store:Chroma, k:int = 4, where_filter: dict | None = None):
    return store.similarity_search(query, k=k, filter=where_filter)


