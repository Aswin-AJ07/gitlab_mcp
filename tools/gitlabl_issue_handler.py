
from fastmcp import FastMCP , Context
from typing import Annotated
import re
from fastmcp.tools.tool import ToolResult
import json

from service.gitlab_issue_service import GitlabIssueService

class GitlabIssueHander():

    def __init__(self, mcp: FastMCP):
        
        """Initialize the Gitlab Issues Handler.

        Args:
            mcp: The MCP server instance
        """
        
        self.mcp = mcp
        self.gitlab_service = GitlabIssueService()

        #registers tool
#       @self.mcp.tool("resource://users")
        # def get_project_users(...):
            #     ...
        # self.mcp.tool(name="add_tool")(self.add_tool)   
        # self.mcp.tool(name="filter_user")(self.filter_user)
        # self.mcp.tool(name="list_user_issues")(self.list_user_issues)
        self.mcp.tool(name="get_gitlab_data")(self.get_gitlab_data)
        # self.mcp.tool(name="code_runner_tool")(self.code_runner_tool)

    def add_tool(self,a: Annotated[int, "input a"], b: int) -> int:
        """Adds two integer numbers together.
        Args:
        a : int
        b : int

        """
        return a + b
    
    async def filter_user(self,name : str , ctx: Context) -> dict:
        """Retuns users information and the projects he/she belongs to as a list.

        Args:
        name : string

        Returns :
        a json with user_info and project_list as two keys.
        {
        user_info : all user related informastion as a dict
        project_list: a list of project names he is part of
        }
        """

        # mime type is set as text for this by default
        #returns list of ReadResourceContent and content in it is a string 
        project_user_map = await ctx.read_resource("resource://users")
        
        query = re.escape(name.strip())
        pattern = re.compile(query, re.IGNORECASE)
        project_user_map = json.loads(project_user_map[0].content)
        res = {}
        for proj , user_list in project_user_map.items():
            for user in user_list:
                if pattern.search(user['name'].strip()):
                    res[proj] = user
                    break
        return {"user_info" : list(res.values())[0] , "project_list" : list(res.keys())}  #tool retuns CallToolResults

    async def list_user_issues(self, user_id: int, milestones : list, ctx: Context) -> list:
        """Lists all issues assigned to a specific user in the mile with the time spent on each.

        Args:
            user_id: The ID of the user.
            milestones: A list of milestone titles to filter issues.

        Returns:
            A list of issues assigned to the user.
        """


        # get user_id from mcp resource users


        #call gitlab api to get issues assigned to user id
        issues = await self.gitlab_service.get_issues_by_user(user_id)
        
        #create a json list with user info , issue title and time spent on each issue on the milestone provided
        issue_list = []
        for issue in issues:
            if issue['milestone'] and issue['milestone']['title'] in milestones:
                issue_list.append({
                    "issue_title": issue['title'],
                    "time_spent": issue['time_stats']['total_time_spent']
                })

        return issue_list
    
    def get_gitlab_data(self, query: str) -> list:
        """
        Tool for ANY GitLab-related queries.

        MUST be used when the user asks about:
        - GitLab issues
        - GitLab projects
        - GitLab merge requests
        - GitLab pipelines
        - Filtering by project id, user id, iteration, or dates

        DO NOT answer from memory.
        ALWAYS call this tool for GitLab data.

        Input:
        {
            "query": "<FULL user query as string>"
        }

        INPUT FORMAT:
        - Pass the FULL user query as a plain string
        - Do NOT wrap it inside another object
        - Do NOT extract fields

        Correct example:
        { "query": "List issues in project 123" }
        """
        return self.gitlab_service.call_gitlab_api(query)


    
    #Below is test code , checking on code runner kind of python tool
    async def code_runner_tool(self, code: str) -> str:
        """Executes the provided Python code and returns the output.

        Args:
            code: A string containing the Python code to execute.
        Returns:
            The status  of the executed code as a string.
        """
        #create a python file with the code string
        import tempfile
        import os
        import subprocess

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        env = {
            "GITLAB_TOKEN": os.environ.get("GITLAB_ACCESS_TOKEN", ""),
        }

        try:
            result = subprocess.run(['python3', temp_file], capture_output=True, text=True, timeout=10 , env=env)
            if result.returncode == 0:
                return f"Code executed successfully. Output:\n{result.stdout}"
            else:
                return f"Code execution failed. Error:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return "Code execution timed out."
        finally:
            os.unlink(temp_file)
