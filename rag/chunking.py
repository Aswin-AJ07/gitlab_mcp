from urllib.parse import quote

import hashlib
import uuid
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from dotenv import load_dotenv
import sys
import asyncio
import aiohttp
from urllib.parse import urlparse
# from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import URL
import tiktoken
from langchain_postgres import PGVector , PGEngine , PGVectorStore
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class AsyncWebsite:
    def __init__(self, url, html):
        self.url = url
        self.body = html
        soup = BeautifulSoup(self.body, "html.parser")
        self.title = soup.title.string if soup.title else "No title found"
        main_content = soup.find("div", class_="main-content")

        if not main_content:
            # Fail-safe fallback (optional)
            main_content = soup.body

        # ----------------------------
        # Remove unwanted tags
        # ----------------------------
        for irrelevant in main_content([
            "script",
            "style",
            "img",
            "input",
            "nav",
            "footer",
            "aside"
        ]):
            irrelevant.decompose()

        # ----------------------------
        # Extract text
        # ----------------------------
        self.text = main_content.get_text(separator="\n", strip=True)

        # ----------------------------
        # Extract links (main-content only)
        # ----------------------------
        links = [a.get("href") for a in main_content.find_all("a")]
        self.links = [urljoin(self.url, link) for link in links if link]

        # ----------------------------
        # Create heading-based blocks
        # ----------------------------
        self.sections = []
        current_section = {
            "heading": "Introduction",
            "content": []
        }

        for tag in main_content.find_all(
            ["h1", "h2", "h3", "h4", "h5", "p", "li", "pre", "code", "table"]
        ):
            if tag.name in ["h1", "h2", "h3"]:
                # push old section
                if current_section["content"]:
                    self.sections.append({
                        "heading": current_section["heading"],
                        "text": "\n".join(current_section["content"])
                    })

                # start new section
                current_section = {
                    "heading": tag.get_text(strip=True),
                    "content": []
                }

            else:
                text = tag.get_text(" ", strip=True)
                if text:
                    current_section["content"].append(text)

        # append last
        if current_section["content"]:
            self.sections.append({
                "heading": current_section["heading"],
                "text": "\n".join(current_section["content"])
            })
    
    def get_contents(self):
        return f"Webpage Title:\n{self.title}\nWebpage Contents:\n{self.text}\n\n"
    
        

class AsyncCrawler:
    def __init__(self, base_url, max_depth=2, max_concurrency=10, tokenizer=None, store : PGVectorStore =None):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.visited = set()
        self.max_depth = max_depth
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.db_semaphore = asyncio.Semaphore(12)  #to limit db writes
        self.tokenizer = tokenizer
        self.store = store

    async def fetch(self, session, url):
        async with self.semaphore:
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200 and 'text/html' in response.headers.get('Content-Type', ''):
                        return await response.text()
                    else:
                        print(f"Skipped (status {response.status}/content-type): {url}")
                        return None
            except Exception as e:
                print(f"Failed to fetch {url}: {repr(e)}")
                return None 
    

    def manual_chunk_text(self, text, max_tokens=1000, overlap=100):
        tokens = self.tokenizer.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + max_tokens
            chunk = self.tokenizer.decode(tokens[start:end])
            chunks.append(chunk)
            start += max_tokens - overlap

        return chunks

    def langchain_chunk_text(self, texts, chunk_size=500, chunk_overlap=50):
        

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        chunks = text_splitter.split_text(texts)
        return chunks    
    

    async def crawl(self, url=None, depth=0, session=None):
        if depth > self.max_depth:
            return
        if url is None:
            url = self.base_url
        if url in self.visited:
            return
        if urlparse(url).netloc != self.domain:
            return

        self.visited.add(url)
        html = await self.fetch(session, url)
        if not html:
            return

        page = AsyncWebsite(url, html)
        print(f"Crawled (depth {depth}): {url}")
        docs = []

        for section_index, section in enumerate(page.sections):
            section_text = f"{section['heading']}\n{section['text']}"

            # only split if very large
            if len(section_text) > 1200:
                chunks = self.langchain_chunk_text(
                    texts=section_text,
                    chunk_size=800,
                    chunk_overlap=100
                )
            else:
                chunks = [section_text]

            for chunk_index, chunk in enumerate(chunks):
                content_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                # create a UUID from first 32 chars of hash_hex (hex string)
                doc_id = str(uuid.UUID(content_hash[:32]))
                docs.append(
                    Document(
                        page_content=chunk,
                        metadata={
                            "source": url,             
                            "page_title": page.title,
                            "section_heading": section["heading"],
                            "section_index": section_index,
                            "chunk_index": chunk_index,
                        },
                        id=f"{doc_id}",
                    )
                )

        print('Prepared', len(docs), 'documents for', url)
        #insert to postgres using langchain document format
        if docs:
            async with self.db_semaphore:
                await self.store.aadd_documents(docs)
            print('Inserted', len(docs), 'documents for', url)

        tasks = []
        for link in page.links:
            if link not in self.visited:
                tasks.append(self.crawl(link, depth + 1, session))
        await asyncio.gather(*tasks)

    async def run(self):        
        async with aiohttp.ClientSession() as session:
            await self.crawl(session=session)



async def setup_vectorstore(pg_engine : PGEngine, table_name, embeddings):
    #add condtion to check if table exists
    await pg_engine.ainit_vectorstore_table(table_name=table_name, vector_size=768)
    vectorstore = await PGVectorStore.create(engine=pg_engine, table_name=table_name, embedding_service=embeddings)
    return vectorstore



async def main():
    # if sys.platform.startswith("win"):
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if os.getenv("ENV") is None:
        load_dotenv()

    POSTGRE_PASS = os.getenv("POSTGRE_PASS")

    tokenizer = tiktoken.get_encoding("cl100k_base")
    embeddings = OllamaEmbeddings(model="nomic-embed-text")


    # legacy code
    # url = URL.create(
    #     "postgresql+psycopg2",
    #     username="postgres",
    #     password=POSTGRE_PASS,
    #     host="localhost",
    #     database="postgres",
    # )

    # engine = create_engine(url)

    #uses langchain_pg_collection and langchain_pg_embedding tables
    # vectorstore = PGVector(
    #     connection=engine,
    #     collection_name="gitlab_docs",
    #     embeddings=embeddings,
    # )



    engine = create_async_engine(
            URL.create(
                drivername="postgresql+asyncpg",
                username="postgres",
                password=POSTGRE_PASS,
                host="localhost",
                port=5432,
                database="postgres",
            )#, echo=True
        )

    pgengine = PGEngine.from_engine(engine)
    
    pg_vectorestore =  await setup_vectorstore(pgengine, "gitlab_api_rcts", embeddings)
    
    crawler = AsyncCrawler(
        base_url=  "https://docs.gitlab.com/api/api_resources/",
        max_depth=1,
        max_concurrency=5,
        tokenizer=tokenizer,
        store=pg_vectorestore
    )

    await crawler.run()


if __name__ == "__main__":
    asyncio.run(main())
    # AsyncCrawler()


# gitlab had added copy llm button to their docs, so we can use that to get more structured data for api endpoints, parameters, and descriptions. This will be more efficient than crawling and chunking the entire docs.
#  We can use the copy button data to directly create structured documents for each API endpoint, which will be more useful for answering user queries about GitLab's API.

# example: https://docs.gitlab.com/api/plan_limits/index.md. You can directly fetch this and chunk it based on the API endpoints and parameters, rather than crawling the entire page. This will give you more relevant and concise information for each API endpoint, which will be more efficient for answering user queries about GitLab's API.