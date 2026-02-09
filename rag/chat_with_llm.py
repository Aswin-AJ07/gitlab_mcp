import os
from dotenv import load_dotenv

if os.getenv('ENV') is None:  #only in local run the below
    load_dotenv()
POSTGRE_PASS = os.getenv('POSTGRE_PASS')


#Using Langchain vector search on the langchain table instead of manual postgres queries

from langchain_ollama import OllamaEmbeddings , OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_postgres import PGEngine, PGVector , PGVectorStore
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import URL


from sentence_transformers import CrossEncoder
from langchain_core.runnables import RunnableLambda

reranker = CrossEncoder("BAAI/bge-reranker-base")

def rerank_docs(inputs: dict):
    query = inputs["question"]
    docs = inputs["context"]

    pairs = [(query, d.page_content) for d in docs]
    scores = reranker.predict(pairs)

    scored = list(zip(docs, scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    top_docs = [d for d, s in scored[:5]]  # keep top 5

    # join as context string for prompt
    context_text = "\n\n".join(d.page_content for d in top_docs)

    return {
        "context": context_text,
        "question": query
    }

rerank_runnable = RunnableLambda(rerank_docs)


url = URL.create("postgresql+psycopg2", username="postgres", password=POSTGRE_PASS, host="localhost", database="postgres")
engine = create_engine(url)
pg_engine = create_engine(url)


embeddings = OllamaEmbeddings(model="nomic-embed-text")

# vectorstore = PGVector(
#     connection=pg_engine,
#     collection_name="gitlab_docs",
#     embeddings=embeddings,
# )

engine = create_engine(
            URL.create(
                drivername="postgresql+psycopg2",
                username="postgres",
                password=POSTGRE_PASS,
                host="localhost",
                port=5432,
                database="postgres",
            )#, echo=True
        )
from urllib.parse import quote_plus

password = quote_plus(POSTGRE_PASS)
pgengine = PGEngine.from_connection_string(
    "postgresql+asyncpg://postgres:" + password + "@localhost:5432/postgres"
)

vectorstore_pg = PGVectorStore.create_sync(
        engine=pgengine,
        table_name='gitlab_api_rcts',
        embedding_service=embeddings
    )

retriever = vectorstore_pg.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 8,
        "fetch_k": 50,
        "lambda_mult": 0.7
    }
)


prompt = ChatPromptTemplate.from_template("""
            You are a helpful assistant.
            Use ONLY the following context to answer the question.

            Context:
            {context}

            Question:
            {question}

            Answer:
            """)

llm = OllamaLLM(
                model="codellama:7b",
                temperature=0.2
            )

rag_chain = (
    {
        "context": retriever,          # step 1: retrieve
        "question": RunnablePassthrough()
    }
    | rerank_runnable                 # ⭐ step 2: rerank here
    | prompt                          # step 3: send best docs
    | llm
    | StrOutputParser()
)

res = rag_chain.invoke("Lists all issues for a specified group.")
print(res)



#how to make it better ?
# 1. Along with vector search , include parse Keyword Search - metadata filtering to narrow down the search space first before retrieval. for example filter by source or section heading based on the question. this can be a separate runnable before retrieval step.
# 2. Reranking step with cross encoder to improve relevance of retrieved documents. implemented above.


#Deploy the rag agent to google cloud vertex ai , wrap rag_chain in a class with predict method
# deploy the rag agent to google cloud vertex ai , wrap rag_chain in a class with predict method
# https://docs.cloud.google.com/agent-builder/agent-engine/develop/custom
# https://github.com/googleapis/langchain-google-cloud-sql-pg-python/blob/main/samples/langchain_on_vertexai/retriever_agent_with_history_template.py