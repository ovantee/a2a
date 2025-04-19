import json
from typing import AsyncIterable, List, Optional
from common.types import (
    SendTaskRequest,
    TaskSendParams,
    Message,
    TaskStatus,
    Artifact,
    TaskStatusUpdateEvent,
    TextPart,
    TaskState,
    Task,
    SendTaskResponse,
    JSONRPCResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
)
from common.server.task_manager import InMemoryTaskManager
from agent import TourBookingAgent
import logging

logger = logging.getLogger(__name__)

class AgentTaskManager(InMemoryTaskManager):
    def __init__(self, agent: TourBookingAgent):
        super().__init__()
        self.agent = agent

    def _validate_request(self, request):
        # Simple validation to check if the request has params
        if not hasattr(request, 'params') or not request.params:
            return JSONRPCResponse(id=request.id, error={"code": -32602, "message": "Missing params"})
        return None

    async def _update_store(self, task_id: str, status: TaskStatus, artifacts: Optional[List[Artifact]] = None) -> Task:
        async with self.lock:
            try:
                task = self.tasks[task_id]
            except KeyError:
                task = Task(id=task_id, status=status, artifacts=[])
                self.tasks[task_id] = task
            task.status = status
            if artifacts:
                if not hasattr(task, 'artifacts') or task.artifacts is None:
                    task.artifacts = []
                task.artifacts.extend(artifacts)
            return task

    async def _stream_generator(
        self, request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)
        try:
            async for item in self.agent.stream(query, task_send_params.sessionId):
                is_task_complete = item["is_task_complete"]
                artifacts = None
                if not is_task_complete:
                    task_state = TaskState.WORKING
                    parts = [{"type": "text", "text": item["updates"]}]
                else:
                    if isinstance(item["content"], dict):
                        if ("response" in item["content"]
                            and "result" in item["content"]["response"]):
                            data = json.loads(item["content"]["response"]["result"])
                            task_state = TaskState.INPUT_REQUIRED
                        else:
                            data = item["content"]
                            task_state = TaskState.COMPLETED
                        parts = [{"type": "data", "data": data}]
                    else:
                        task_state = TaskState.COMPLETED
                        parts = [{"type": "text", "text": item["content"]}]
                    artifacts = [Artifact(parts=parts, index=0, append=False)]
                message = Message(role="agent", parts=parts)
                task_status = TaskStatus(state=task_state, message=message)
                await self._update_store(task_send_params.id, task_status, artifacts)
                task_update_event = TaskStatusUpdateEvent(
                    id=task_send_params.id,
                    status=task_status,
                    final=False,
                )
                yield SendTaskStreamingResponse(
                    id=request.id, result=task_update_event
                )
        except Exception as e:
            logger.error(f"Error in stream generator: {e}")
            yield SendTaskStreamingResponse(
                id=request.id, error={"code": -32603, "message": f"Error processing stream: {str(e)}"}
            )
            return
        # Final response to indicate completion
        task_status = TaskStatus(
            state=TaskState.COMPLETED,
            message=Message(role="agent", parts=[{"type": "text", "text": "Booking process completed."}])
        )
        await self._update_store(task_send_params.id, task_status, None)
        task_update_event = TaskStatusUpdateEvent(
            id=task_send_params.id,
            status=task_status,
            final=True,
        )
        yield SendTaskStreamingResponse(
            id=request.id, result=task_update_event
        )

    async def _invoke(self, request: SendTaskRequest) -> SendTaskResponse:
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)
        try:
            response = self.agent.invoke(query, task_send_params.sessionId)
            task_status = TaskStatus(
                state=TaskState.COMPLETED,
                message=Message(role="agent", parts=[{"type": "text", "text": response}])
            )
            await self._update_store(task_send_params.id, task_status, None)
            return SendTaskResponse(
                id=request.id,
                result=TaskStatusUpdateEvent(
                    id=task_send_params.id,
                    status=task_status,
                    final=True
                )
            )
        except Exception as e:
            logger.error(f"Error in invoke: {e}")
            return SendTaskResponse(id=request.id, error={"code": -32603, "message": f"Error processing request: {str(e)}"})

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        error = self._validate_request(request)
        if error:
            return error
        await self.upsert_task(request.params)
        return await self._invoke(request)

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        error = self._validate_request(request)
        if error:
            return error
        await self.upsert_task(request.params)
        return self._stream_generator(request)

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        part = task_send_params.message.parts[0]
        if not isinstance(part, TextPart):
            raise ValueError("Only text parts are supported")
        return part.text