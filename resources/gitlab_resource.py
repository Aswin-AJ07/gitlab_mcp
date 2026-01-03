import json
from fastmcp import Context 
from fastmcp import FastMCP

from service.gitlab_issue_service import GitlabIssueService

"""
resources - 
Lazy Loading:  The decorated function (get_users) is only executed when a client specifically requests that resource URI via resources/read.

Return Response -  
FastMCP automatically converts your function's return value into the appropriate MCP resource content:
dict, list, pydantic.BaseModel: Automatically serialized to a JSON string and sent as TextResourceContents (with mime_type="application/json" by default).

Notifications -  events like add , disable/enable etc of resource triggers thid
are sent to connected clients ,  Clients can handle these notifications using a message handler to automatically refresh their resource lists or update their interfaces.
notifications/resources/list_changed - client should handle this event sent by server

Annotations -
@mcp.resource(    "data://config",annotations={"readOnlyHint": True,"idempotentHint": True}) - extra hints to the client about the resource 
These annotations communicate how resources behave to client applications without consuming token context in LLM prompt

Resource Template - 
@mcp.resource("repo://{owner}/{path*}/template.py")
query params - @mcp.resource("api://{endpoint}{?version,limit,offset}"

multi template for 1 fn
Manually apply multiple decorators to the same function
mcp.resource("users://email/{email}")(lookup_user)
mcp.resource("users://name/{name}")(lookup_user
Define a user lookup function that can be accessed by different identifiers
def lookup_user(name: str | None = None, email: str | None = None) -> dict:

Error Handling
By default, all exceptions (including their details) are logged and converted into an MCP error response to be sent back to the client LLM. This helps the LLM understand failures and react appropriately.
When mask_error_details=True, only error messages from ResourceError will include details, other exceptions will be converted to a generic message

mcp = FastMCP(name="ResourceServer",on_duplicate_resources="error" # Raise error on duplicates)


for static content like file using resource classes like fastmcp.resources.FileResource
mcp.add_resource()
mcp.add_resource(special_resource, key="internal://data-v2")  -- custom resource keys allowed

"""

class GitlabResource():
    def __init__(self,mcp : FastMCP):
        """Initialize Gitlab Resource

        Args:
            mcp: The MCP server instance
        """
        self.mcp = mcp
        self.gitlab_service = GitlabIssueService()

        #add resources , deprecated
        # self.mcp.add_resource_fn(self.get_project_users,"resource://users")
        # self.mcp.add_resource_fn(self.get_project,"resource://projects")

        #add resource as decorator
        self.mcp.resource("resource://users",mime_type="application/json")(self.get_project_users)
        self.mcp.resource("resource://projects",mime_type="application/json")(self.get_project)


    #For dynamic content
    # @mcp.resource("resource://users")  #({uri=resource://users,name="ApplicationStatus"})
    async def get_project_users(self,ctx: Context) -> list :   #ctx.request_id , ctx has additional mcp information
        """This resource gets the users available on a each project in gitlab
        
        Args:
            ctx: The MCP context

        Returns:
            Returns a list of python dict with key as project id  which is an integer and value as a list of user dict which contains user information
        """
        return await self.gitlab_service.get_users()
        
    # @mcp.resource("resource://projects")  #({uri=resource://users,name="ApplicationStatus"})
    async def get_project(self,ctx: Context) -> list :   #ctx.request_id , ctx has additional mcp information
        """This resource gets all information related to gitlabl projects
        
        Args:
            ctx: The MCP context
        
        Returns:
            Returns a list of python dict containing project information
        """
        return await self.gitlab_service.get_project_data()