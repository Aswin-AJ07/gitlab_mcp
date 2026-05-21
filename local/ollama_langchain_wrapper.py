from langchain_core.runnables import Runnable
import requests

#The below code is a LangChain Runnable wrapper for Ollama API , this can be used in LangChain pipelines wherever a Runnable is accepted.
#This is how langchain_ollama is implemented but making our own here for better understanding and customization if needed.


class OllamaRunnable(Runnable):
    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")

    def invoke(self, input_text: str) -> str:
        # Prepare the payload as Ollama expects
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": input_text},
            ],
        }
        # Call Ollama API
        response = requests.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract the assistant's message content
        return data["choices"][0]["message"]["content"]

    async def ainvoke(self, input_text: str) -> str:
        # If you want async support, you'd need httpx or aiohttp here.
        raise NotImplementedError("Async invoke not implemented.")


#The below code is an example of creating a custom LLM by extending the LLM base class in LangChain Core.


from langchain_core.language_models.llms import LLM
from typing import Optional, List, Mapping, Any

class CustomLLM(LLM):
    """
    A custom LLM wrapper that returns only the first 'n' characters 
    of the prompt for demonstration purposes.
    """
    n: int

    @property
    def _llm_type(self) -> str:
        """Returns the type of LLM."""
        return "custom"

    def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs: Any) -> str:
        """
        The main method to call the LLM.
        
        Args:
            prompt: The prompt to pass to the LLM.
            stop: A list of strings to stop the generation at.
            **kwargs: Arbitrary keyword arguments.
        """
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")
        return prompt[:self.n]
    
    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {"n": self.n}

# # Usage:
# llm = CustomLLM(n=10)
# result = llm.invoke("This is a test prompt for the custom LLM.")  , this calls base class invoke which calls the overriden _call method
# print(result) 
# # Output: This is a 


# the LLM base case inherits the runnable class

# Exactly! In LangChain Core’s design, the LLM base class does inherit from the Runnable interface (or abstract base class).

# What that means in practice:

# The Runnable interface defines the core contract — primarily the .invoke() and .ainvoke() methods, plus batch variants.

# LLM is a specialized subclass of Runnable designed specifically for language models.

# Because LLM inherits from Runnable, it gains the runnable interface, meaning it can be used anywhere a runnable is expected.

# This inheritance allows LLMs to fit into LangChain’s execution ecosystem, enabling:

# composition,

# chaining,

# batching,

# async calls,

# etc.