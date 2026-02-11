from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.tools.genome_tool import list_genome_files
from app.core.tools.post_tool import create_post, get_user_posts
from app.schemas.agent.agent_request import AgentRequest

class AgentService:
    # Abstract t
    def __init__(self, model: ChatGoogleGenerativeAI) -> None:
        self.model = model
    
    AVAILABLE_TOOLS = {
        "create_post": create_post,
        "get_user_posts": get_user_posts,
        "genome_files": list_genome_files
    }

    def process_query(self, request: AgentRequest):
        # Currently, only handle the query request
        response = self.model.invoke(request.query)

        final_answer = ""
        tool_executions = []

        if response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in self.AVAILABLE_TOOLS:
                    tool_instance = self.AVAILABLE_TOOLS[tool_name]
                    try:
                        print(f"Executing tool: {tool_name} with args: {tool_args}")

                        result_data = tool_instance.invoke(tool_args)

                        tool_executions.append({
                            "tool_name": tool_name,
                            "arguments": tool_args,
                            "result": result_data
                        })
                    except Exception as e:
                        tool_executions.append({
                            "tool_name": tool_name,
                            "arguments": tool_args,
                            "result": str(e)
                        })
            
            final_answer = "Invoke related tool successfully."
        else:
            # Xử lý an toàn cho content của Gemini
            if isinstance(response.content, str):
                final_answer = response.content
            elif isinstance(response.content, list):
                # Nếu là mảng, lọc lấy nội dung 'text' từ các dictionary bên trong
                text_blocks = [
                    block.get("text", "") 
                    for block in response.content 
                    if isinstance(block, dict) and "text" in block
                ]
                final_answer = "\n".join(text_blocks)
            else:
                # Fallback an toàn cho các kiểu dữ liệu dị biệt khác
                final_answer = str(response.content)

        return {
            "answer": final_answer,
            "tool_executions": tool_executions
        }


