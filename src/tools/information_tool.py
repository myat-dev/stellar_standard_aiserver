import os
import pandas as pd
from typing import Optional, Type, Any

from langchain.callbacks.manager import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document

from pydantic.v1 import BaseModel, Field
from src.helpers.conf_loader import RAG_CONF, MODELS_CONF, DAILOGUE
from src.helpers.enums import ActionType
from src.tools.base_contact_tool import BaseContactTool
from src.api.websocket_manager import WebSocketManager
from src.agent.session_manager import ChatSessionManager
from src.message_templates.websocket_message_template import (
    UserProfile,
    WebsocketMessageTemplate,
)
from langchain.tools import BaseTool

def load_documents()-> list:
    documents = []
    df = pd.read_excel(RAG_CONF["source_data"])
    for _, row in df.iterrows():
        documents.append(Document(page_content=f"Question: {row['Question']}\nAnswer: {row['Answer']}", metadata={"Category":row['Category']}))
    return documents

def create_chunks(documents):
    text_splitter = CharacterTextSplitter(chunk_size=MODELS_CONF["embedding"]["chunk_size"], chunk_overlap=MODELS_CONF["embedding"]["chunk_overlap"])
    split_docs = []
    for doc in documents:
        chunks = text_splitter.split_text(doc.page_content)
        for chunk in chunks:
            split_docs.append(Document(page_content=chunk, metadata=doc.metadata))
    return split_docs

def get_source_data_timestamp() -> str:
    """Get the last modified timestamp of the source data file."""
    return str(os.path.getmtime(RAG_CONF["source_data"]))

def is_source_data_updated() -> bool:
    """Check if the source data has been updated since last vector DB creation."""
    current_timestamp = get_source_data_timestamp()
    if not os.path.exists(RAG_CONF["track_file"]):
        return True
    with open(RAG_CONF["track_file"], "r") as f:
        saved_timestamp = f.read().strip()
    return saved_timestamp != current_timestamp

def save_source_data_timestamp():
    """Save the last modified timestamp of the source data file."""
    current_timestamp = get_source_data_timestamp()
    with open(RAG_CONF["track_file"], "w") as f:
        f.write(current_timestamp)

def create_retriever():
    # Check if vector DB already exists and source data is not updated
    embedding = OpenAIEmbeddings(model=MODELS_CONF["embedding"]["model_name"])

    if os.path.exists(RAG_CONF["vector_db"]) and not is_source_data_updated():
        print("Loading existing FAISS index...")
        faiss_store = FAISS.load_local(RAG_CONF["vector_db"], embedding,allow_dangerous_deserialization=True)
    else:
        print("Creating new FAISS index...")
        documents = load_documents()
        split_docs = create_chunks(documents)
        faiss_store = FAISS.from_documents(split_docs, embedding)
        faiss_store.save_local(RAG_CONF["vector_db"])
        
        save_source_data_timestamp()

    retriever = faiss_store.as_retriever()
    return retriever

class InformationInput(BaseModel):
    question: str = Field(description="The question for ryusenji related information")

class InformationTool(BaseContactTool):
    name: str = "information"
    description: str = (
        "龍泉寺に関する情報を取得するためのツールです。"
        "お花の購入、お金の両替、線香の購入、お焚き上げ、御朱印、お手洗いの案内等の情報を提供します。" 
    )
    args_schema: Type[BaseModel] = InformationInput  
    retriever : Optional[Any] = None
    ws_manager: Optional[WebSocketManager] = None
    message_manager: Optional[WebsocketMessageTemplate] = None
    session_manager: Optional[ChatSessionManager] = None
    user_profile: Optional[UserProfile] = None

    def _run(self, question: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        """Use the tool to retrieve information."""
        # Use the retriever to fetch relevant documents based on the question
        results = self.retriever.invoke(question)
        
        if results:
            # Combine the relevant document contents as the answer
            answer = "\n".join([result.page_content for result in results])
            return answer
        else:
            return DAILOGUE["rag_fallback_message"]

    async def _arun(self, question: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        """Asynchronous version of the tool."""
        # Use the async retriever to fetch relevant documents (if supported by the retriever)
        self.session_manager.context.last_tool_name = self.name
        results = await self.retriever.ainvoke(question)

        if results:
            # Extract only the first result’s answer part
            first = results[0].page_content
            if "Answer:" in first:
                return first.split("Answer:", 1)[1].strip()
            return first.strip()
        else:
            return DAILOGUE["rag_fallback_message"]