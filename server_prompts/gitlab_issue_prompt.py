from fastmcp import FastMCP



class GitlabIssuePrompt:
    PROMPT_TEMPLATE = """You are an expert in GitLab issue management. Your task is to help users query and manage issues in GitLab repositories."""
    def __init__(self,mcp : FastMCP):
        self.mcp = mcp


        # self.mcp.prompt()

    def get_user_info_prompt(self,user_name: str) -> str:
        """Generate a prompt to get user information from GitLab.

        Args:
            user_name: The name of the user to query.

        Returns:
            A formatted prompt string.
        """
        prompt = f"""
        {self.PROMPT_TEMPLATE}

        Please provide detailed information about the user '{user_name}' including their associated projects and roles.
        """
        return prompt
    
    def filter_user_issues_prompt(self,user_id: int,milestones: list) -> str:
        """Generate a prompt to filter issues for a specific user based on milestones.

        Args:
            user_id: The ID of the user whose issues are to be filtered.
            milestones: A list of milestones to filter the issues.
        """
        prompt = f"""
        {self.PROMPT_TEMPLATE}

        Please provide a list of issues assigned to the user with ID {user_id}
        that are associated with the following milestones: {milestones} and the time spent on each issue.
        """
        return prompt