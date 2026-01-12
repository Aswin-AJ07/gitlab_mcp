#activating uv venv is not setting the virtual enve python as the VS code interpreter automatically

# from mcp.server.fastmcp import FastMCP
from fastmcp import FastMCP
import asyncio

from tools.gitlabl_issue_handler import GitlabIssueHander
from resources.gitlab_resource import GitlabResource
from server_prompts.gitlab_issue_prompt import GitlabIssuePrompt

mcp = None


async def main():
    global mcp
    mcp = FastMCP("Gitlab Server")
    
    #Resource Registry
    GitlabResource(mcp=mcp)

    #prompt registry
    GitlabIssuePrompt(mcp=mcp)
    
    #Tool Registry
    GitlabIssueHander(mcp=mcp)
    res = await mcp.get_tools()
    print(f"tools are {res}")
    
    await mcp.run_async(transport='http')


if __name__ == '__main__':
   asyncio.run(main())

# TO DO 
# Next steps - MCP server prompts and MCP Client

# RAG
# Write a better crawler that can go multiple levels deep

# Better solution - 
#  Prompts and client in code mode style. make LLM generate a python code for you. then run the code in a local for now , later sandboxed environment.
 
