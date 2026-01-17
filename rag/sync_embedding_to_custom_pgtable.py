#synchronize embeddings from Ollama to Postgres PGVector store.
#Custom postgres table 'documents' is used here.

import ollama
import psycopg2
import tiktoken
import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
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
tokenizer = tiktoken.get_encoding("cl100k_base")

link_system_prompt = "You are provided with a list of links found on a webpage. \
You are able to decide which of the links would be most relevant to learn Gitlab\n"
link_system_prompt += "You should respond in JSON as in this example:"
link_system_prompt += """
{
    "links": [
        {"type": "about page", "url": "https://full.url/goes/here/about"},
        {"type": "careers page", "url": "https://another.full.url/careers"}
    ]
}
"""

class Website():
    def __init__(self,url):
        self.url = url
        response = requests.get(self.url)
        self.body = response.content
        soup = BeautifulSoup(self.body, "html.parser")
        self.title = soup.title.string if soup.title else "No title found"
        if soup.body:
            for irrelevant in soup.body(["script", "style", "img", "input"]):
                irrelevant.decompose()
            self.text = soup.body.get_text(separator="\n", strip=True)
        else:
            self.text = ""
        links = [link.get('href') for link in soup.find_all('a')]
        self.links = [urljoin(self.url, link) for link in links if link]

    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"

def get_links_user_prompt(website):
    user_prompt = f"Here is the list of links on the website of {website.url} - "
    user_prompt += "please decide which of these are relevant web links for a Gitlab, respond with the full https URL and type in JSON format.\n"
    user_prompt += "Do not include Terms of Service, Privacy, email links.\n"
    user_prompt += "Links (some might be relative links):\n"
    user_prompt += "\n".join(website.links)
    return user_prompt


# def web_crawler_and_store(url):

#     website = Website(url)
#     result = "Landing page:\n"
#     result += website.get_contents()
#     print("Found links:", website.links)
#     for link in website.links["links"]:
#         result += f"\n\n{link['type']}\n"
#         result += Website(link["url"]).get_contents()
#     return result

def get_links(website : Website, model: str = "qwen2.5:7b") -> str:
    """Query an Ollama model with the given prompt.

    Args:
        prompt: The input prompt to send to the model.
        model: The name of the Ollama model to use.

    Returns:
        The response from the model as a string.
    """

    response = ollama.chat(
        model=model,  # e.g. "llama3.1:8b"
        messages=[
            {"role": "system", "content": link_system_prompt},
            {"role": "user", "content": get_links_user_prompt(website)},
        ],
        format="json"
    )

    result = response["message"]["content"]
    return json.loads(result)


def ollama_embed(text: str, model: str = "nomic-embed-text") -> list:
    """Generate embeddings for the given text using an Ollama model.

    Args:
        text: The input text to generate embeddings for.
        model: The name of the Ollama model to use. 
    Returns:
        A list of floats representing the embeddings.

    response = ollama.embed(model=model, input=text)
    return response['embeddings']

    """
    response = ollama.embed(model=model, input=text)
    return response['embeddings'][0]  # Adjusted to return the first embedding , only 1 text input



def chunk_text(text, max_tokens=1000, overlap=100):
    tokens = tokenizer.encode(text)
    chunks = []

    start = 0
    while start < len(tokens):
        end = start + max_tokens
        chunk = tokenizer.decode(tokens[start:end])
        chunks.append(chunk)
        start += max_tokens - overlap

    return chunks

def insert_chunk(source: str, content: str, embedding: list, chunk_index: int):
    cur.execute(
        """
        INSERT INTO documents (source, content, embedding, chunk_index)
        VALUES (%s, %s, %s, %s)
        """,
        (source, content, embedding, chunk_index)
    )

# crawl is limited to depth 1 for simplicity
def crawl_and_store(url):
    website = Website(url)

    # 1. Ask Ollama which links matter
    links_json = get_links(website)
    links = links_json.get("links", [])

    print("Relevant links:", links)
    pass

    # 2. Always include landing page
    pages = [(url, website.text)]

    # 3. Crawl selected links
    for link in links:
        try:
            page = Website(link["url"])
            pages.append((link["url"], page.text))
        except Exception as e:
            print(f"Failed to load {link['url']}: {e}")

    # 4. Chunk, embed, insert
    for source, text in pages:
        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            embedding = ollama_embed(chunk)

            insert_chunk(
                source=source,
                content=chunk,
                embedding=embedding,
                chunk_index=i
            )

    conn.commit()
    print("✅ Stored documents in PostgreSQL")
