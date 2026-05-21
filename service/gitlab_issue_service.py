
import json
import os
from dotenv import load_dotenv
import httpx
import asyncio

from config.server_config import ServerConfig

#import rag
from rag.retrieve import rag_search

class GitlabIssueService():

    def __init__(self):
        """
        Initialize Gitlabl Issue Service
        """
        self.config = ServerConfig()
        self.headers = headers = {"Authorization": f"Bearer {self.config.pat}","Accept": "application/json"}

    async def fetch(self,client : httpx.AsyncClient , url):
        response = await client.get(url,headers = self.headers)
        return response.json()

    async def fetch_page(self,url , client : httpx.AsyncClient, page : int, per_page : int, semaphore, assignee):
        params = {
            "assignee_id": assignee,
            "per_page": per_page,
            "page": page,
            "scope": "all"   #without scope , by default only assigned/authored issues of PAT owner are returned
        }

        async with semaphore: #limits the concurrent requests in the batch
            response = await client.get(url, headers=self.headers, params=params)
            print(f"Requesting: {response.request.url}")
            response.raise_for_status()

            return response

    async def get_users(self):
        async with httpx.AsyncClient() as client:
            members = [self.fetch(client , f"https://gitlab.com/api/v4/projects/{proj}/members") for proj in self.config.project_list ]
            member_list = await asyncio.gather(*members)
        #   for future in asyncio.as_completed(member):
        #       result = await future   #if any one completes , it is returned
        #       print("Got result:", result)
        
        #project-wise user resource
        user_resource = dict(zip(map(str, self.config.project_list), member_list))
        return user_resource

    async def get_project_data(self):
        async with httpx.AsyncClient() as client:
            project_coroutines = [self.fetch(client , f"https://gitlab.com/api/v4/projects/{proj}/") for proj in self.config.project_list ]
            project_data = await asyncio.gather(*project_coroutines)
            return project_data

    async def get_issues_by_user(self,user_id : int):
        semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
        PER_PAGE = 20

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: fetch page 1
            resp = await self.fetch_page(
                f"https://gitlab.com/api/v4/issues", client, 1, PER_PAGE, semaphore, user_id
            )
            resp.raise_for_status()

            issues = resp.json()
            total_pages = int(resp.headers.get("X-Total-Pages", 1))
            # Step 3: parallel fetch
            print(f"Total pages: {total_pages}")

            tasks = [
                self.fetch_page(f"https://gitlab.com/api/v4/issues", client, page, PER_PAGE, semaphore, user_id)
                for page in range(2, total_pages + 1)
            ]

            results = await asyncio.gather(*tasks)

            for page_data in results:
                issues.extend(page_data.json())

            # Step 2: fallback if total pages missing
            # if not total_pages:
            #     page = 2
            #     while True:
            #         resp = await self.fetch_page(
            #         f"https://gitlab.com/api/v4/issues", client, page, PER_PAGE, semaphore, user_id
            #         )
            #         resp.raise_for_status()
            #         data = resp.json()
            #         if not data:
            #             break
            #         issues.extend(data)
            #         page += 1
            #     return issues


        return issues
    
    async def call_gitlab_api(self,query : str):

        url = "https://gitlab.com/api/v4"
        rag_search_result = rag_search(query)
        rag_result_json = json.loads(rag_search_result)

        async with httpx.AsyncClient() as client:
                api = rag_result_json['api']
                api_type = rag_result_json['api_type']
                parameters = rag_result_json.get('parameters', {})

                full_url = url + api
                print(f"Making {api_type} request to {full_url} with parameters {parameters}")

                if api_type.upper() == "GET":
                    response = await client.get(full_url, headers=self.headers, params=parameters)
                # elif api_type.upper() == "POST":
                #     response = await client.post(full_url, headers=self.headers, json=parameters)
                # elif api_type.upper() == "PUT":
                #     response = await client.put(full_url, headers=self.headers, json=parameters)
                # elif api_type.upper() == "DELETE":
                #     response = await client.delete(full_url, headers=self.headers, params=parameters)

                response.raise_for_status()
                return response.json()
                