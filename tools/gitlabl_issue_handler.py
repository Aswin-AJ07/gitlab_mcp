
from fastmcp import FastMCP , Context
from typing import Annotated
import re
from fastmcp.tools.tool import ToolResult
import json

from service.gitlab_issue_service import GitlabIssueService
"""

**Exclude args: to avoid runtime args to be sent to LLM -  
@mcp.tool(name="get_user_details",exclude_args=["user_id"])
def get_user_details(user_id: str = None) -> str:

**Strunctured Response - 
@dataclass
class User:
    id: int
    name: str
    role: str
Tools can return User and it is handled properly in mcp response


**For complete control over tool responses, return a ToolResult object. 
@mcp.tool
def advanced_tool() -> ToolResult:
    Tool with full control over output
    return ToolResult(
        content=[TextContent(type="text", text="Human-readable summary")],
        structured_content={"data": "value", "count": 42},
        meta={"execution_time_ms": 145}
    )

    
"""



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
        self.mcp.tool(name="add_tool")(self.add_tool)   
        self.mcp.tool(name="filter_user")(self.filter_user)
        self.mcp.tool(name="list_user_issues")(self.list_user_issues)

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