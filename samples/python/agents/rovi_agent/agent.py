from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, ToolMessage
import os
from typing import Any, Dict, AsyncIterable, Literal, List, Optional
from pydantic import BaseModel, Field
# Import docx_reader functions
from agents.rovi_agent.docx_reader import get_concept_info, get_concepts_brief_overview

# Memory for conversation history
memory = MemorySaver()

# Define response format for the agent
class ResponseFormat(BaseModel):
    """Format for the agent's response."""
    require_user_input: bool = Field(
        description="Whether the agent requires more information from the user."
    )
    content: str = Field(
        description="The content of the agent's response."
    )

# Tool to get teambuilding concept information
@tool
def get_teambuilding_info(concept_name: Optional[str] = None) -> str:
    """
    Get information about teambuilding concepts.

    Args:
        concept_name: Optional name of the specific concept to retrieve information about.
                     If not provided, returns a list of available concepts.

    Returns:
        Information about the requested teambuilding concept or a list of available concepts.
    """
    # Use the docx_reader module to get concept information
    from agents.rovi_agent.docx_reader import get_concept_info
    return get_concept_info(concept_name)

# Tool to get pricing information
@tool
def get_pricing_info(concept_name: str, participants: int) -> str:
    """
    Get pricing information for a teambuilding concept.

    Args:
        concept_name: Name of the teambuilding concept.
        participants: Number of participants.

    Returns:
        Pricing information for the requested teambuilding concept.
    """
    # This is a simplified pricing model for demonstration purposes
    base_prices = {
        "HÀNH TRÌNH XANH": 500000,  # VND per person
        "Ngày hội gia đình": 400000,
        "Amazing 4.0": 600000,
        "Trekking": 700000,
        "Kick off": 550000,
        "Sức mạnh EKIP": 450000
    }

    # Find the closest matching concept
    matching_concept = None
    for concept in base_prices.keys():
        if concept_name.lower() in concept.lower():
            matching_concept = concept
            break

    if not matching_concept:
        return f"No pricing information found for '{concept_name}'. Please check the concept name and try again."

    # Calculate price based on number of participants
    base_price = base_prices[matching_concept]

    # Apply discount for larger groups
    discount = 0
    if participants >= 100:
        discount = 0.15  # 15% discount
    elif participants >= 50:
        discount = 0.10  # 10% discount
    elif participants >= 20:
        discount = 0.05  # 5% discount

    total_price = base_price * participants * (1 - discount)

    return f"Pricing information for '{matching_concept}':\n- Base price: {base_price:,} VND per person\n- Number of participants: {participants}\n- Discount: {discount*100:.0f}%\n- Total estimated price: {total_price:,.0f} VND\n\nNote: This is an estimate. Final pricing may vary based on specific requirements and customizations."

# Tool to check availability
@tool
def check_availability(date: str, concept_name: str) -> str:
    """
    Check availability for a teambuilding event on a specific date.

    Args:
        date: The date to check in format YYYY-MM-DD.
        concept_name: Name of the teambuilding concept.

    Returns:
        Availability information for the requested date and concept.
    """
    # This is a simplified availability check for demonstration purposes
    # In a real implementation, this would query a database or calendar system

    # Simulate some unavailable dates
    unavailable_dates = ["2024-05-15", "2024-05-16", "2024-05-22", "2024-05-23",
                         "2024-06-10", "2024-06-11", "2024-06-12"]

    if date in unavailable_dates:
        return f"Sorry, we are fully booked on {date}. Please consider alternative dates."

    return f"Good news! We are available to host your '{concept_name}' teambuilding event on {date}. Please contact us to make a reservation."

class CustomerServiceAgent:
    """A customer service agent for teambuilding events."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    SYSTEM_INSTRUCTION = """You are a customer service agent for ROVI, a company that specializes in organizing teambuilding events for corporate clients.

    Your responsibilities include:
    1. Providing information about different teambuilding concepts and their content
    2. Helping clients choose the right teambuilding concept for their needs
    3. Collecting necessary information to process booking requests

    When interacting with clients:
    - Be professional, friendly, and helpful
    - Provide clear and concise information
    - Ask for clarification when needed
    - Recommend appropriate teambuilding concepts based on client needs
    - Collect all necessary information before processing a booking request

    Use the available tools to access information about teambuilding concepts.
    DO NOT provide pricing information as this is handled by a separate department.

    Always respond in Vietnamese unless the client specifically asks for English.
    """

    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
        self.tools = [get_teambuilding_info, check_availability]

        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    def invoke(self, query, sessionId) -> Dict[str, Any]:
        try:
            # Check for specific concept names in the query
            concept_names = ["Sức mạnh EKIP", "HÀNH TRÌNH XANH", "Ngày hội gia đình", "Amazing 4.0", "Trekking", "Kick off"]

            # Check if any concept name is mentioned in the query
            for concept in concept_names:
                if concept.lower() in query.lower() or (concept == "Sức mạnh EKIP" and ("EKIP" in query or "ekip" in query)):
                    info = get_teambuilding_info.invoke({"concept_name": concept})
                    return {
                        "is_task_complete": True,
                        "require_user_input": False,
                        "content": info,
                    }

            # Handle pricing queries with a standard response
            if "giá" in query.lower() or "chi phí" in query.lower() or "phí" in query.lower():
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "Xin lỗi, thông tin về giá cả được xử lý bởi bộ phận khác. Tôi chỉ có thể cung cấp thông tin về nội dung các gói teambuilding. Vui lòng liên hệ với bộ phận kinh doanh để biết thêm chi tiết về giá.",
                }
            elif "teambuilding" in query.lower() or "team building" in query.lower() or "tổ chức" in query.lower():
                info = get_teambuilding_info.invoke({})
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": info,
                }
            elif "tổ chức" in query.lower() or "sự kiện" in query.lower():
                # For event organization queries, provide available concepts
                info = get_teambuilding_info.invoke({})
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": f"{info}\n\nVui lòng cho biết bạn quan tâm đến gói teambuilding nào để tôi cung cấp thêm thông tin chi tiết.",
                }
            elif "thông tin" in query.lower() or "giới thiệu" in query.lower() or "hay" in query.lower():
                # For general information queries, provide a helpful response
                info = get_teambuilding_info.invoke({})
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": f"Chào mừng bạn đến với ROVI - đơn vị chuyên tổ chức các hoạt động teambuilding cho doanh nghiệp!\n\nChúng tôi cung cấp nhiều gói teambuilding đa dạng phù hợp với nhu cầu của từng doanh nghiệp:\n\n{info}\n\nBạn có thể hỏi tôi về bất kỳ gói teambuilding nào để biết thêm chi tiết về nội dung, giá cả và lịch trình.",
                }
            else:
                # Try to use LangGraph for other queries
                config = {"configurable": {"thread_id": sessionId}}
                try:
                    self.graph.invoke({"messages": [("user", query)]}, config)
                    return self.get_agent_response(config)
                except Exception as e:
                    # If there's an error, return a default response
                    print(f"Error using LangGraph: {str(e)}")
                    return {
                        "is_task_complete": True,
                        "require_user_input": True,
                        "content": f"Xin lỗi, tôi gặp vấn đề khi xử lý yêu cầu của bạn. Vui lòng cho tôi biết bạn cần thông tin gì về các gói teambuilding của chúng tôi?",
                    }
        except Exception as e:
            # If there's an error, return a default response
            return {
                "is_task_complete": True,
                "require_user_input": True,
                "content": f"Xin lỗi, tôi gặp vấn đề khi xử lý yêu cầu của bạn: {str(e)}",
            }

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:
        try:
            # Check for specific concept names in the query
            concept_names = ["Sức mạnh EKIP", "HÀNH TRÌNH XANH", "Ngày hội gia đình", "Amazing 4.0", "Trekking", "Kick off"]

            # Check if any concept name is mentioned in the query
            matched_concept = None
            for concept in concept_names:
                if concept.lower() in query.lower() or (concept == "Sức mạnh EKIP" and ("EKIP" in query or "ekip" in query)):
                    matched_concept = concept
                    break

            if matched_concept:
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": f"Đang tìm kiếm thông tin về gói {matched_concept}...",
                }
                info = get_teambuilding_info.invoke({"concept_name": matched_concept})

                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": info,
                }
            # Handle pricing queries with a standard response
            elif "giá" in query.lower() or "chi phí" in query.lower() or "phí" in query.lower():
                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": "Xin lỗi, thông tin về giá cả được xử lý bởi bộ phận khác. Tôi chỉ có thể cung cấp thông tin về nội dung các gói teambuilding. Vui lòng liên hệ với bộ phận kinh doanh để biết thêm chi tiết về giá.",
                }
            elif "teambuilding" in query.lower() or "team building" in query.lower() or "tổ chức" in query.lower():
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Đang tìm kiếm thông tin về các gói teambuilding...",
                }
                info = get_teambuilding_info.invoke({})

                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": info,
                }
            elif "tổ chức" in query.lower() or "sự kiện" in query.lower():
                # For event organization queries, provide available concepts
                yield {
                    "is_task_complete": False,
                    "require_user_input": False,
                    "content": "Đang tìm kiếm thông tin về các gói teambuilding phù hợp...",
                }
                info = get_teambuilding_info.invoke({})

                yield {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": f"{info}\n\nVui lòng cho biết bạn quan tâm đến gói teambuilding nào để tôi cung cấp thêm thông tin chi tiết.",
                }
            else:
                # Try to use LangGraph for other queries
                try:
                    inputs = {"messages": [("user", query)]}
                    config = {"configurable": {"thread_id": sessionId}}

                    for item in self.graph.stream(inputs, config, stream_mode="values"):
                        message = item["messages"][-1]
                        if (
                            isinstance(message, AIMessage)
                            and message.tool_calls
                            and len(message.tool_calls) > 0
                        ):
                            yield {
                                "is_task_complete": False,
                                "require_user_input": False,
                                "content": "Đang tìm kiếm thông tin cho bạn...",
                            }
                        elif isinstance(message, ToolMessage):
                            yield {
                                "is_task_complete": False,
                                "require_user_input": False,
                                "content": "Đang xử lý thông tin...",
                            }

                    yield self.get_agent_response(config)
                except Exception as e:
                    # If there's an error, return a default response
                    print(f"Error using LangGraph streaming: {str(e)}")
                    yield {
                        "is_task_complete": True,
                        "require_user_input": True,
                        "content": f"Xin lỗi, tôi gặp vấn đề khi xử lý yêu cầu của bạn. Vui lòng cho tôi biết bạn cần thông tin gì về các gói teambuilding của chúng tôi?",
                    }
        except Exception as e:
            # If there's an error, return a default response
            yield {
                "is_task_complete": True,
                "require_user_input": True,
                "content": f"Xin lỗi, tôi gặp vấn đề khi xử lý yêu cầu của bạn: {str(e)}",
            }

    def get_agent_response(self, config) -> Dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        try:
            messages = memory.get({"configurable": {"thread_id": thread_id}})["messages"]
        except (KeyError, TypeError):
            # If there's an issue with memory, return a helpful response with available information
            info = get_teambuilding_info.invoke({})
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"Chào mừng bạn đến với ROVI - đơn vị chuyên tổ chức các hoạt động teambuilding cho doanh nghiệp!\n\nChúng tôi cung cấp nhiều gói teambuilding đa dạng phù hợp với nhu cầu của từng doanh nghiệp:\n\n{info}\n\nBạn có thể hỏi tôi về bất kỳ gói teambuilding nào để biết thêm chi tiết về nội dung và hoạt động.",
            }

        # Get the last AI message
        for message in reversed(messages):
            if isinstance(message, AIMessage) and not message.tool_calls:
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": message.content,
                }

        # If no AI message found, return a default response
        return {
            "is_task_complete": True,
            "require_user_input": True,
            "content": "Xin lỗi, tôi không hiểu yêu cầu của bạn. Bạn có thể cung cấp thêm thông tin không?",
        }
