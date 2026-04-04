from typing import List, Optional
from loguru import logger
from langchain_community.agent_toolkits.openapi.toolkit import OpenAPIToolkit
from langchain_community.utilities.openapi import OpenAPISpec
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.language_models import BaseLanguageModel
from langchain_core.tools import BaseTool

def build_openapi_tools(
    llm: BaseLanguageModel, 
    openapi_yaml_path: str,
    api_key: Optional[str] = None
) -> List[BaseTool]:
    """
    Parses the Datasets OpenAPI spec and returns a list of LangChain tools
    capable of interacting with the REST API endpoints.
    """
    try:
        # Load the local YAML specification
        spec = OpenAPISpec.from_file(openapi_yaml_path)
        
        # Prepare headers
        headers = {"Accept": "application/json"}
        if api_key:
            headers["api-key"] = api_key
            
        # Wrapper for executing HTTP requests
        requests_wrapper = TextRequestsWrapper(headers=headers)
        
        # Build the toolkit. 
        # allow_dangerous_requests=True is required to allow the agent to execute real HTTP calls.
        toolkit = OpenAPIToolkit.from_llm(
            llm=llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            # allow_dangerous_requests=True 
        )
        
        tools = toolkit.get_tools()
        logger.info(f"Successfully loaded {len(tools)} OpenAPI tools from {openapi_yaml_path}")
        return tools
        
    except Exception as e:
        logger.error(f"Failed to load OpenAPI spec from {openapi_yaml_path}: {e}")
        return []