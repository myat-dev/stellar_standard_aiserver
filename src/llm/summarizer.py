from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from src.helpers.conf_loader import MODELS_CONF
from src.helpers.env_loader import OPENAI_API_KEY

summarizer_prompt = PromptTemplate(
    template=(
        "You are an assistant helping optimize search queries.\n"
        "User question: {question}\n"
        "Summarize and rewrite the question into a short, clear, effective web search query."
    ),
    input_variables=["question"],
)


llm = ChatOpenAI(
    api_key=OPENAI_API_KEY, temperature=0, model=MODELS_CONF["llm"]["version"]
)
search_query_chain = summarizer_prompt | llm
