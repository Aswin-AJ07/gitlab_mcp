from fastmcp import Client
import time
import json

ALLOWED_TOOLS = {
    "filter_user": {
        "required_args": ["name"],
        # "timeout": 3
    },
    "list_user_issues": {
        "required_args": ["user_id", "milestones"],
        # "timeout": 3
    }
}


class ProductionMCPClient:
    def __init__(self, url: str):
        self.url = url

    async def list_prompts(self, client):
        prompts = await client.list_prompts()  # or similar API to get registered prompts
        return prompts
    
    async def fetch_tools(self, client):
        tools = await client.list_tools()  # or similar API to get registered tools
        # tools might be a list of dicts with tool metadata
        return tools
    
    
    async def llm(self, prompt: str) -> str:
        pass
        # Implement LLM call here, e.g., using OpenAI or another service

        
    def build_tools_prompt(tools):
        lines = []
        for tool in tools:
            name = tool.get("name")
            args = tool.get("args", [])
            arg_str = ", ".join(args)
            lines.append(f"- {name}({arg_str})")
        return "\n".join(lines)

    async def decide_tool(self, user_input, tools_prompt):
        prompt = f"""
            Available tools:
            {tools_prompt}

            Return JSON only:
            {{"tool": "...", "arguments": {{...}}}}

            User input:
            {user_input}
        """
        response = await self.llm(prompt)
        return json.loads(response)

    #works for single tool call , but what if we need to chain tools?.
    #  do we get response of one tool and then decide next tool based on that? 

    # anthropic code mode technique for tool calls chains?


    async def call_tool(self, tool: str, arguments: dict):
        # 1. Permission check
        if tool not in ALLOWED_TOOLS:
            return {"error": "tool_not_allowed", "tool": tool}

        # 2. Argument validation
        for arg in ALLOWED_TOOLS[tool]["required_args"]:
            if arg not in arguments:
                return {"error": "missing_argument", "arg": arg}

        start = time.time()

        # 3. Call MCP server
        try:
            async with Client(self.url) as client:
                result = await client.call_tool(
                    tool,
                    arguments=arguments
                )
                return result

        except Exception as e:
            return {"error": "tool_execution_failed", "detail": str(e)}

        finally:
            # 4. Logging / tracing
            duration = time.time() - start
            print(f"[MCP] tool={tool} duration={duration:.2f}s")
