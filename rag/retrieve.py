import json
import os
from collections import defaultdict
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_postgres import PGEngine, PGVectorStore

from sentence_transformers import CrossEncoder


# =========================================================
#   ENV
# =========================================================
if os.getenv("ENV") is None:
    load_dotenv()

POSTGRE_PASS = os.getenv("POSTGRE_PASS")


# =========================================================
#   MODELS
# =========================================================
embeddings = OllamaEmbeddings(model="nomic-embed-text")

llm = OllamaLLM(
    model="codellama:7b",
    temperature=0.2
)

reranker = CrossEncoder("BAAI/bge-reranker-base")


# =========================================================
#   RERANKER
# =========================================================
def rerank_docs(inputs: dict):
    query = inputs["question"]
    docs = inputs["context"]

    pairs = [(query, d.page_content) for d in docs]
    scores = reranker.predict(pairs)

    scored = list(zip(docs, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    top_docs = [d for d, _ in scored[:5]]

    context_text = "\n\n".join(d.page_content for d in top_docs)

    return {
        "context": context_text,
        "question": query
    }

rerank_runnable = RunnableLambda(rerank_docs)


# =========================================================
#   POSTGRES + PGVECTOR
# =========================================================
url = URL.create(
    "postgresql+psycopg2",
    username="postgres",
    password=POSTGRE_PASS,
    host="localhost",
    database="postgres",
)

engine = create_engine(url)

password = quote_plus(POSTGRE_PASS)
pgengine = PGEngine.from_connection_string(
    f"postgresql+asyncpg://postgres:{password}@localhost:5432/postgres"
)

vectorstore = PGVectorStore.create_sync(
    engine=pgengine,
    table_name="gitlab_api_rcts",
    embedding_service=embeddings,
)

retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 5,
        "fetch_k": 50,
        "lambda_mult": 0.7,
    },
)


# =========================================================
#   PROMPT
# =========================================================
prompt = ChatPromptTemplate.from_template("""
You are a helpful Gitlab API assistant. You retuen the API response based on the retrieved context. If the context does not contain the answer, say "Sorry, I don't know how to help with that."
The response should be a json object with API , api type and the parameters. Do not include any extra text, only the json object.
If the api has request params , replace the param in the api with the value provided in the question. If the value is not provided in the question, keep the param name as it is.                                          
If the api requires any json request body, include it in the parameters field as a json object. The keys of the json object should be the parameter names and the values should be the values provided in the question. If the value is not provided in the question, keep the parameter name as it is and value as empty string.
exampe response for question "Lists all issues for a specified group with id 12345." would be:
{{
    "api": "/groups/12345/issues",
    "api_type": "GET",
    "parameters": {{}}
}}
                                                                                   
Use ONLY the following context to answer the question.

Context:
{context}

Question:
{question}

Only return the json object, no explanation or extra text.
""")


# =========================================================
#   MULTI QUERY GENERATOR
# =========================================================
def generate_multi_queries(query: str, n=5):
    system_prompt = f"""
You are an AI search assistant.

Rephrase the user question into {n} different search queries.
Keep meaning same but vary wording.
Also include original question.

IMPORTANT RULES:
- Return ONLY a valid JSON list
- No numbering
- No explanation
- No extra text
- Only JSON

Example:
[
 "query1",
 "query2",
 "query3"
]
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    response = llm.invoke(messages)
    return json.loads(response)


# =========================================================
#   Calculate RRF
# =========================================================
def calculate_rrf_scores(docs,  rrf_scores, doc_map ,rrf_k=60):

    for rank, doc in enumerate(docs, start=1):
            doc_id = doc.id

            if doc_id not in doc_map:
                doc_map[doc_id] = doc
            score = 1 / (rrf_k + rank)
            rrf_scores[doc_id] += score


# =========================================================
# 🚀 FULL RAG PIPELINE
# =========================================================
def rag_search(user_query: str):
    print("\n🔵 User Query:", user_query)

    # 1. multi query generation
    queries = generate_multi_queries(user_query)
    print("\n🟢 Generated Queries:", queries)

    # 2. retrieve for each query
    doc_map = {}
    rrf_scores = defaultdict(float)

    for q in queries:
        docs = retriever.invoke(q)
        calculate_rrf_scores(docs, rrf_scores, doc_map)
    
    # fuse docs based on RRF scores
    sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    fused_docs = [doc_map[doc_id] for doc_id, _ in sorted_docs] 

    # 4. rerank
    reranked = rerank_docs({
        "question": user_query,
        "context": fused_docs[:5]
    })

    # 5. final answer
    final_prompt = prompt.invoke(reranked)
    answer = llm.invoke(final_prompt)

    return answer



"""
=========================================================
🧪 TEST
=========================================================
if __name__ == "__main__":
    query = "Lists all issues in a project 12546 with iteration title 'iteration 1' and label 'bug'."
    result = rag_search(query)
    print("\n🧠 FINAL ANSWER:\n", result)
    json_res = json.loads(result)
    print(json_res)

TO DO
1. multi query , generate multiple queries from the main query and do multiple retrievals. 
2. hybrid search - sparse search + vector search

Ensemble retriver vs manual rrf


Deploy the rag agent to google cloud vertex ai , wrap rag_chain in a class with predict method
deploy the rag agent to google cloud vertex ai , wrap rag_chain in a class with predict method
https://docs.cloud.google.com/agent-builder/agent-engine/develop/custom
https://github.com/googleapis/langchain-google-cloud-sql-pg-python/blob/main/samples/langchain_on_vertexai/retriever_agent_with_history_template.py

"""