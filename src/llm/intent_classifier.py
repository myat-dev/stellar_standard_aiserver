from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.helpers.env_loader import OPENAI_API_KEY
from src.helpers.conf_loader import MODELS_CONF

# Define the prompt template
intent_prompt = PromptTemplate(
    input_variables=["response"],
    template="""
You are an intelligent assistant that classifies the intent of a user’s response.

Classify the user's intent into one of the following categories:
- confirmation: if the user agrees, confirms, or requests to proceed. 
  Examples: "はい", "大丈夫です", "承認します", "OKです", "いいですよ","その通りです".
- decline: if the user declines, refuses, or rejects the request. 
  Examples: "いいえ", "違います", "やめます", "だめです", "いらない", "ふようです".
- unknown: if the intent is unclear or cannot be classified.

User response: "{response}"

Return ONLY the category name.
"""
)

# Define the prompt template
correction_prompt = PromptTemplate(
    input_variables=["response"],
    template="""
You are an intelligent assistant that classifies the intent of a user’s response.

Classify the user's intent into one of the following categories:
- confirmation: if the user agrees, confirms, or requests to proceed. 
  Examples: "はい", "大丈夫です", "承認します", "OKです", "いいですよ","その通りです", "はい、正しいです", "はい、間違いありません".
- correction: if the user indicates they want to make a correction or change. 
  Examples: "修正したいです", "訂正します", "変更します", "いいえ、間違っています".
- unknown: if the intent is unclear or cannot be classified.

User response: "{response}"

Return ONLY the category name.
"""
)

# Initialize the LLM and Chain
llm = ChatOpenAI(api_key=OPENAI_API_KEY,
        temperature=0,
        model=MODELS_CONF["llm"]["version"])  
intent_chain = intent_prompt | llm
correction_chain = correction_prompt | llm