import ollama
import psycopg2     
import os

from dotenv import load_dotenv

if os.getenv('ENV') is None:  #only in local run the below
    load_dotenv()
POSTGRE_PASS = os.getenv('POSTGRE_PASS')


# Database connection setup
conn = psycopg2.connect(
    dbname="postgres",
    user="postgres",
    password=POSTGRE_PASS,
    host="localhost",
    port=5432
)
cur = conn.cursor()

def similarity_search(conn, query_embedding, top_k=5):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT source, content, chunk_index,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM documents
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """, (query_embedding, query_embedding, top_k))
        results = cur.fetchall()
    return results

def generate_answer_with_context(question, retrieved_chunks, llm_model="qwen2.5:7b"):
    # Combine the retrieved chunks as context for the LLM
    context = "\n\n".join([chunk[1] for chunk in retrieved_chunks])  # chunk[1] is content

    system_prompt = """You are an expert python programmer that writes simple, concise code and explanations.

    You MUST respond ONLY with runnable Python code to call GitLab APIs based on the user question, parameters, and context.
    The environment variable for the GitLab token is GITLAB_ACCESS_TOKEN.
    Only respond ONLY with the code between <output> tags and nothing else
      """
    prompt = f"""
                write python code for below question using gitlab api and make use of the context provided.

                Use the context only to find the relevant API endpoints and parameters.
                Context:
                {context}

                Question:
                {question}

                Remember to respond ONLY with python code.
                DO NOT include any explanations or text.
    """

    response = ollama.chat(
        model=llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
    )
    return response["message"]["content"]

def using_ollama_chat():
    # Usage example
    query = "Configuring GitLab Pages without GDK"

    # 1. Embed query
    embedding = ollama.embed(model="nomic-embed-text", input=query)["embeddings"][0]

    # 2. Search relevant chunks from manual postgres table
    matches = similarity_search(conn, embedding, top_k=5)
    print("=== Retrieved contexts ===")
    for match in matches:
        print(f"Source: {match[0]}, Chunk Index: {match[2]}")
        print(f"Content: {match[1]}")
        print("-----")

    # 3. Generate answer using retrieved context
    answer = generate_answer_with_context(query, matches)
    print("=== Final Answer ===")
    print(answer)


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


# Reranker to improve the retrieved contexts using a cross encoder model. This is an optional step and can be skipped if the initial retrieval quality is good.
# reranked_docs = rerank("Lists all issues for a specified group.", docs)
# print(f"Reranked docs - {reranked_docs}")

# from langchain_core.runnables import RunnableLambda

# rerank_runnable = RunnableLambda(rerank_docs)



# deploy the rag agent to google cloud vertex ai , wrap rag_chain in a class with predict method
# https://docs.cloud.google.com/agent-builder/agent-engine/develop/custom
# https://github.com/googleapis/langchain-google-cloud-sql-pg-python/blob/main/samples/langchain_on_vertexai/retriever_agent_with_history_template.py