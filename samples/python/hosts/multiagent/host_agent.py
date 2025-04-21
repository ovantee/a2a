import sys
import asyncio
import functools
import json
import uuid
import threading
from typing import List, Optional, Callable

from google.genai import types
import base64

from google.adk import Agent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from .remote_agent_connection import (
    RemoteAgentConnections,
    TaskUpdateCallback
)
from common.client import A2ACardResolver
from common.types import (
    AgentCard,
    Message,
    TaskState,
    Task,
    TaskSendParams,
    TextPart,
    DataPart,
    Part,
    TaskStatusUpdateEvent,
)


class HostAgent:
  """The host agent.

  This is the agent responsible for choosing which remote agents to send
  tasks to and coordinate their work.
  """

  def __init__(
      self,
      remote_agent_addresses: List[str],
      task_callback: TaskUpdateCallback | None = None
  ):
    self.task_callback = task_callback
    self.remote_agent_connections: dict[str, RemoteAgentConnections] = {}
    self.cards: dict[str, AgentCard] = {}
    for address in remote_agent_addresses:
      card_resolver = A2ACardResolver(address)
      card = card_resolver.get_agent_card()
      remote_connection = RemoteAgentConnections(card)
      self.remote_agent_connections[card.name] = remote_connection
      self.cards[card.name] = card
    agent_info = []
    for ra in self.list_remote_agents():
      agent_info.append(json.dumps(ra))
    self.agents = '\n'.join(agent_info)

  def register_agent_card(self, card: AgentCard):
    remote_connection = RemoteAgentConnections(card)
    self.remote_agent_connections[card.name] = remote_connection
    self.cards[card.name] = card
    agent_info = []
    for ra in self.list_remote_agents():
      agent_info.append(json.dumps(ra))
    self.agents = '\n'.join(agent_info)

  def create_agent(self) -> Agent:
    return Agent(
        model="gemini-2.0-flash-001",
        name="host_agent",
        instruction=self.root_instruction,
        before_model_callback=self.before_model_callback,
        description=(
            "This agent orchestrates the decomposition of the user request into"
            " tasks that can be performed by the child agents."
        ),
        tools=[
            self.list_remote_agents,
            self.send_task,
        ],
    )

  def root_instruction(self, context: ReadonlyContext) -> str:
    current_agent = self.check_state(context)
    return f"""Bạn là Tebbi, một trợ lý AI thông minh, chuyên viên tư vấn dịch vụ du lịch chuyên nghiệp của Rovi Travel – ứng dụng du lịch AI hàng đầu dành cho người Việt, mang đến trải nghiệm cá nhân hóa và tuyệt vời cho khách hàng. Nhiệm vụ của bạn là hỗ trợ khách hàng lập kế hoạch du lịch, tư vấn dịch vụ (vé máy bay, khách sạn, tour trọn gói, MICE, eSIM, v.v.), thiết kế lịch trình tự túc hoặc tour trọn gói, khuyến khích sử dụng ứng dụng Rovi Travel và chốt được lead cho Bộ phận Dịch vụ của Rovi Travel.

**Hướng dẫn hoạt động:**
1. Vai trò và giọng điệu:**
   - Xưng hô là "Tebbi" (VD: "Tebbi rất vui được giúp anh/chị!"), giữ giọng điệu thân thiện, vui vẻ, gần gũi nhưng vẫn chuyên nghiệp.
   - Gọi khách là "anh/chị" (hoặc điều chỉnh linh hoạt nếu khách yêu cầu, như "bạn" với người trẻ hoặc "cô/chú" với người lớn tuổi).
   - Nếu khách cung cấp tên, cá nhân hóa bằng cách thêm tên vào câu trả lời (VD: "Anh Nam thấy sao ạ? Tebbi gợi ý thêm nhé!").

Discovery:
- Bạn có thể sử dụng `list_remote_agents` để liệt kê các agent từ xa có sẵn mà bạn có thể sử dụng để ủy thác nhiệm vụ.

Execution:
- Đối với các nhiệm vụ có thể thực hiện được, bạn có thể sử dụng `create_task` để giao nhiệm vụ cho các agent từ xa thực hiện.
Hãy đảm bảo bao gồm tên agent từ xa khi bạn trả lời người dùng.

Bạn có thể sử dụng `check_pending_task_states` để kiểm tra trạng thái của các nhiệm vụ đang chờ xử lý.

Vui lòng dựa vào các công cụ để giải quyết yêu cầu, đừng bịa ra câu trả lời. Nếu bạn không chắc chắn, hãy hỏi người dùng để biết thêm chi tiết.
Tập trung chủ yếu vào các phần gần đây nhất của cuộc trò chuyện.

Nếu có một agent đang hoạt động, hãy gửi yêu cầu đến agent đó bằng công cụ update task.

Agents:
{self.agents}

Current agent: {current_agent['active_agent']}
"""

  def check_state(self, context: ReadonlyContext):
    state = context.state
    if ('session_id' in state and
        'session_active' in state and
        state['session_active'] and
        'agent' in state):
      return {"active_agent": f'{state["agent"]}'}
    return {"active_agent": "None"}

  def before_model_callback(self, callback_context: CallbackContext, llm_request):
    state = callback_context.state
    if 'session_active' not in state or not state['session_active']:
      if 'session_id' not in state:
        state['session_id'] = str(uuid.uuid4())
      state['session_active'] = True

  def list_remote_agents(self):
    """List the available remote agents you can use to delegate the task."""
    if not self.remote_agent_connections:
      return []

    remote_agent_info = []
    for card in self.cards.values():
      remote_agent_info.append(
          {"name": card.name, "description": card.description}
      )
    return remote_agent_info

  async def send_task(
      self,
      agent_name: str,
      message: str,
      tool_context: ToolContext):
    """Sends a task either streaming (if supported) or non-streaming.

    This will send a message to the remote agent named agent_name.

    Args:
      agent_name: The name of the agent to send the task to.
      message: The message to send to the agent for the task.
      tool_context: The tool context this method runs in.

    Yields:
      A dictionary of JSON data.
    """
    if agent_name not in self.remote_agent_connections:
      raise ValueError(f"Agent {agent_name} not found")
    state = tool_context.state
    state['agent'] = agent_name
    card = self.cards[agent_name]
    client = self.remote_agent_connections[agent_name]
    if not client:
      raise ValueError(f"Client not available for {agent_name}")
    if 'task_id' in state:
      taskId = state['task_id']
    else:
      taskId = str(uuid.uuid4())
    sessionId = state['session_id']
    task: Task
    messageId = ""
    metadata = {}
    if 'input_message_metadata' in state:
      metadata.update(**state['input_message_metadata'])
      if 'message_id' in state['input_message_metadata']:
        messageId = state['input_message_metadata']['message_id']
    if not messageId:
      messageId = str(uuid.uuid4())
    metadata.update(**{'conversation_id': sessionId, 'message_id': messageId})
    request: TaskSendParams = TaskSendParams(
        id=taskId,
        sessionId=sessionId,
        message=Message(
            role="user",
            parts=[TextPart(text=message)],
            metadata=metadata,
        ),
        acceptedOutputModes=["text", "text/plain", "image/png"],
        # pushNotification=None,
        metadata={'conversation_id': sessionId},
    )
    task = await client.send_task(request, self.task_callback)
    # Assume completion unless a state returns that isn't complete
    state['session_active'] = task.status.state not in [
        TaskState.COMPLETED,
        TaskState.CANCELED,
        TaskState.FAILED,
        TaskState.UNKNOWN,
    ]
    if task.status.state == TaskState.INPUT_REQUIRED:
      # Force user input back
      tool_context.actions.skip_summarization = True
      tool_context.actions.escalate = True
    elif task.status.state == TaskState.CANCELED:
      # Open question, should we return some info for cancellation instead
      raise ValueError(f"Agent {agent_name} task {task.id} is cancelled")
    elif task.status.state == TaskState.FAILED:
      # Raise error for failure
      raise ValueError(f"Agent {agent_name} task {task.id} failed")
    response = []
    if task.status.message:
      # Assume the information is in the task message.
      response.extend(convert_parts(task.status.message.parts, tool_context))
    if task.artifacts:
      for artifact in task.artifacts:
        response.extend(convert_parts(artifact.parts, tool_context))
    return response

def convert_parts(parts: list[Part], tool_context: ToolContext):
  rval = []
  for p in parts:
    rval.append(convert_part(p, tool_context))
  return rval

def convert_part(part: Part, tool_context: ToolContext):
  if part.type == "text":
    return part.text
  elif part.type == "data":
    return part.data
  elif part.type == "file":
    # Repackage A2A FilePart to google.genai Blob
    # Currently not considering plain text as files
    file_id = part.file.name
    file_bytes = base64.b64decode(part.file.bytes)
    file_part = types.Part(
      inline_data=types.Blob(
        mime_type=part.file.mimeType,
        data=file_bytes))
    tool_context.save_artifact(file_id, file_part)
    tool_context.actions.skip_summarization = True
    tool_context.actions.escalate = True
    return DataPart(data = {"artifact-file-id": file_id})
  return f"Unknown type: {p.type}"

