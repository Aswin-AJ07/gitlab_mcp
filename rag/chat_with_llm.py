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

    prompt = f"""You are an expert assistant helping answer questions about GitLab.

                Use the following context to answer the question. If the answer is not contained in the context, say "I don't know".

                Context:
                {context}

                Question:
                {question}
    """

    response = ollama.chat(
        model=llm_model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
    )
    return response["message"]["content"]

# Usage example
query = "View token usage information"

# 1. Embed query
embedding = ollama.embed(model="nomic-embed-text", input=query)["embeddings"][0]

# 2. Search relevant chunks
matches = similarity_search(conn, embedding, top_k=5)

# 3. Generate answer using retrieved context
answer = generate_answer_with_context(query, matches)
print("=== Final Answer ===")
print(answer)
