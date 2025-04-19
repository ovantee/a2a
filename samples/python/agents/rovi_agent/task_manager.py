from common.server.task_manager import InMemoryTaskManager
from agents.rovi_agent.agent import CustomerServiceAgent
from common.utils.push_notification_auth import PushNotificationSenderAuth
from common.types import (
    SendTaskRequest,
    TaskSendParams,
    Message,
    TaskStatus,
    Artifact,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TextPart,
    TaskState,
    Task,
    SendTaskResponse,
    InternalError,
    JSONRPCResponse,
    SendTaskStreamingRequest,
    SendTaskStreamingResponse,
    InvalidParamsError,
)
import common.server.utils as utils
from typing import Union, AsyncIterable
import asyncio
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentTaskManager(InMemoryTaskManager):
    def __init__(self, agent: CustomerServiceAgent, notification_sender_auth: PushNotificationSenderAuth):
        super().__init__()
        self.agent = agent
        self.notification_sender_auth = notification_sender_auth
        self.lock = asyncio.Lock()
        self.tasks = {}
        self.sse_queues = {}
        self.push_notification_info = {}

    async def _run_streaming_agent(self, request: SendTaskStreamingRequest):
        task_send_params: TaskSendParams = request.params
        query = self._get_user_query(task_send_params)

        try:
            async for agent_response in self.agent.stream(query, task_send_params.id):
                task_status = None
                artifact = None

                parts = [{"type": "text", "text": agent_response["content"]}]

                if agent_response["require_user_input"]:
                    task_status = TaskStatus(
                        state="input-required",
                        message=Message(role="agent", parts=parts),
                    )
                    await self.update_store(task_send_params.id, task_status, None)
                    await self.send_task_notification(
                        await self.get_task(task_send_params.id)
                    )
                elif agent_response["is_task_complete"]:
                    task_status = TaskStatus(state="completed")
                    artifact = Artifact(parts=parts)
                    await self.update_store(
                        task_send_params.id, task_status, None if artifact is None else [artifact]
                    )
                    await self.send_task_notification(
                        await self.get_task(task_send_params.id)
                    )
                else:
                    task_status = TaskStatus(
                        state="working",
                        message=Message(role="agent", parts=parts),
                    )
                    await self.update_store(task_send_params.id, task_status, None)
                    await self.send_task_notification(
                        await self.get_task(task_send_params.id)
                    )
        except Exception as e:
            logger.error(f"Error in streaming agent: {e}")
            logger.error(traceback.format_exc())

            task_status = TaskStatus(
                state="failed",
                message=Message(
                    role="agent",
                    parts=[
                        {
                            "type": "text",
                            "text": f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn: {str(e)}",
                        }
                    ],
                ),
            )
            await self.update_store(task_send_params.id, task_status, None)
            await self.send_task_notification(await self.get_task(task_send_params.id))

    async def _run_streaming_agent_direct(self, _request_id: str, task_id: str):
        """Run the streaming agent directly without SSE events."""
        try:
            # Get the task
            task = await self.get_task(task_id)
            query = self._get_user_query_from_history(task)

            # Set task to working state
            working_status = TaskStatus(
                state="working",
                message=Message(
                    role="agent",
                    parts=[{"type": "text", "text": "Đang xử lý yêu cầu của bạn..."}]
                )
            )
            task = await self.update_store(task_id, working_status, None)

            # Create a status update event and send it to the queue
            status_event = TaskStatusUpdateEvent(id=task_id, status=working_status, final=False)
            await self.send_sse_event(task_id, status_event)

            # Process the request
            async for agent_response in self.agent.stream(query, task_id):
                if agent_response["is_task_complete"]:
                    # Final response
                    parts = [{"type": "text", "text": agent_response["content"]}]
                    task_status = TaskStatus(state="completed")
                    artifact = Artifact(parts=parts)
                    task = await self.update_store(task_id, task_status, [artifact])

                    # Create an artifact update event and send it to the queue
                    artifact_event = TaskArtifactUpdateEvent(id=task_id, artifact=artifact)
                    await self.send_sse_event(task_id, artifact_event)

                    # Create a status update event with final=True and send it to the queue
                    status_event = TaskStatusUpdateEvent(id=task_id, status=task_status, final=True)
                    await self.send_sse_event(task_id, status_event)

                    # Send notification
                    await self.send_task_notification(task)
                    break

                elif agent_response["require_user_input"]:
                    # Need more input
                    parts = [{"type": "text", "text": agent_response["content"]}]
                    task_status = TaskStatus(
                        state="input-required",
                        message=Message(role="agent", parts=parts),
                    )
                    task = await self.update_store(task_id, task_status, None)

                    # Create a status update event with final=True and send it to the queue
                    status_event = TaskStatusUpdateEvent(id=task_id, status=task_status, final=True)
                    await self.send_sse_event(task_id, status_event)

                    # Send notification
                    await self.send_task_notification(task)
                    break

                else:
                    # Intermediate response
                    parts = [{"type": "text", "text": agent_response["content"]}]
                    task_status = TaskStatus(
                        state="working",
                        message=Message(role="agent", parts=parts),
                    )
                    task = await self.update_store(task_id, task_status, None)

                    # Create a status update event with final=False and send it to the queue
                    status_event = TaskStatusUpdateEvent(id=task_id, status=task_status, final=False)
                    await self.send_sse_event(task_id, status_event)

                    # Send notification
                    await self.send_task_notification(task)
        except Exception as e:
            logger.error(f"Error in direct streaming agent: {e}")
            logger.error(traceback.format_exc())

            # Create error message
            error_message = Message(
                role="agent",
                parts=[
                    {
                        "type": "text",
                        "text": f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn: {str(e)}",
                    }
                ],
            )

            # Update task status to failed
            task_status = TaskStatus(state="failed", message=error_message)
            task = await self.update_store(task_id, task_status, None)

            # Create a status update event with final=True and send it to the queue
            status_event = TaskStatusUpdateEvent(id=task_id, status=task_status, final=True)
            await self.send_sse_event(task_id, status_event)

            # Send notification
            await self.send_task_notification(task)

    def _get_user_query(self, task_send_params: TaskSendParams) -> str:
        """Extract the user query from the task parameters."""
        if not task_send_params.message or not task_send_params.message.parts:
            return ""

        for part in task_send_params.message.parts:
            if part.type == "text" and hasattr(part, "text"):
                return part.text

        return ""

    def _get_user_query_from_history(self, task) -> str:
        """Extract the user query from the task history."""
        if not task.history or len(task.history) == 0:
            return ""

        # Get the last user message
        for message in reversed(task.history):
            if message.role == "user" and message.parts:
                for part in message.parts:
                    if part.type == "text" and hasattr(part, "text"):
                        return part.text

        return ""

    async def upsert_task(self, task_params: TaskSendParams) -> None:
        """Upsert a task."""
        logger.info(f"Upserting task {task_params.id}")
        async with self.lock:
            if task_params.id not in self.tasks:
                self.tasks[task_params.id] = Task(
                    id=task_params.id,
                    sessionId=task_params.sessionId,
                    status=TaskStatus(state="submitted"),
                    history=[task_params.message] if task_params.message else [],
                )
            else:
                # Update the task history
                if task_params.message:
                    self.tasks[task_params.id].history.append(task_params.message)

    async def get_task(self, task_id: str) -> Task:
        """Get a task by ID."""
        async with self.lock:
            try:
                return self.tasks[task_id]
            except KeyError:
                raise ValueError(f"Task {task_id} not found")

    async def update_store(
        self, task_id: str, status: TaskStatus, artifacts: list[Artifact] = None
    ) -> Task:
        """Update the task store."""
        async with self.lock:
            if task_id not in self.tasks:
                raise ValueError(f"Task {task_id} not found")

            task = self.tasks[task_id]
            task.status = status

            if artifacts:
                if not hasattr(task, "artifacts") or task.artifacts is None:
                    task.artifacts = []
                task.artifacts.extend(artifacts)

            return task

    async def setup_sse_consumer(self, task_id: str) -> asyncio.Queue:
        """Set up an SSE consumer for a task."""
        async with self.lock:
            # Always create the queue for the task
            if task_id not in self.sse_queues:
                self.sse_queues[task_id] = []

            queue = asyncio.Queue()
            self.sse_queues[task_id].append(queue)
            return queue

    async def send_sse_event(self, task_id: str, event: Union[TaskStatusUpdateEvent, TaskArtifactUpdateEvent]) -> None:
        """Send an SSE event for a task."""
        try:
            if task_id in self.sse_queues:
                for queue in self.sse_queues[task_id]:
                    await queue.put(event)
        except Exception as e:
            logger.error(f"Error sending SSE event: {e}")

    async def dequeue_events_for_sse(
        self, request_id: str, task_id: str, queue: asyncio.Queue
    ) -> AsyncIterable[SendTaskStreamingResponse]:
        """Dequeue events for SSE."""
        try:
            # Send initial response with the task
            task = await self.get_task(task_id)
            task_dict = task.dict()
            # Add final flag to indicate this is not the final response
            task_dict["final"] = False
            yield SendTaskStreamingResponse(id=request_id, result=task_dict)

            # Start the streaming agent in a separate task
            asyncio.create_task(self._run_streaming_agent_direct(request_id, task_id))

            # Wait for events from the streaming agent
            while True:
                try:
                    # Use a timeout to periodically check if the task is still active
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield SendTaskStreamingResponse(id=request_id, result=event)

                    # Check if this is the final event
                    if hasattr(event, "final") and event.final:
                        break
                except asyncio.TimeoutError:
                    # Send a ping to keep the connection alive
                    task = await self.get_task(task_id)
                    task_dict = task.dict()
                    # Add final flag to indicate this is not the final response
                    task_dict["final"] = False
                    yield SendTaskStreamingResponse(id=request_id, result=task_dict)
        except Exception as e:
            logger.error(f"Error in dequeue_events_for_sse: {e}")
            logger.error(traceback.format_exc())
            # Remove the queue from the list
            if task_id in self.sse_queues and queue in self.sse_queues[task_id]:
                self.sse_queues[task_id].remove(queue)

    async def get_push_notification_info(self, task_id: str):
        """Get push notification info for a task."""
        async with self.lock:
            return self.push_notification_info.get(task_id)

    async def set_push_notification_info(self, task_id: str, push_notification_info) -> bool:
        """Set push notification info for a task."""
        try:
            async with self.lock:
                self.push_notification_info[task_id] = push_notification_info
            return True
        except Exception as e:
            logger.error(f"Error setting push notification info: {e}")
            return False

    async def send_task_notification(self, task: Task) -> None:
        """Send a push notification for a task if configured."""
        if not hasattr(self, "notification_sender_auth") or not self.notification_sender_auth:
            return

        try:
            task_id = task.id
            push_notification_info = await self.get_push_notification_info(task_id)
            if push_notification_info:
                await utils.send_push_notification(
                    push_notification_info.url,
                    task,
                    self.notification_sender_auth,
                )
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")

    async def on_send_task(self, request: SendTaskRequest) -> SendTaskResponse:
        """Handles the 'send task' request."""
        validation_error = self._validate_request(request)
        if validation_error:
            return SendTaskResponse(id=request.id, error=validation_error.error)

        if request.params.pushNotification:
            if not await self.set_push_notification_info(request.params.id, request.params.pushNotification):
                return SendTaskResponse(id=request.id, error=InvalidParamsError(message="Push notification URL is invalid"))

        await self.upsert_task(request.params)
        task = await self.update_store(
            request.params.id, TaskStatus(state="working"), None
        )
        await self.send_task_notification(task)

        query = self._get_user_query(request.params)
        try:
            agent_response = self.agent.invoke(query, request.params.id)
        except Exception as e:
            logger.error(f"Error in agent: {e}")
            logger.error(traceback.format_exc())
            task = await self.update_store(
                request.params.id,
                TaskStatus(
                    state="failed",
                    message=Message(
                        role="agent",
                        parts=[
                            {
                                "type": "text",
                                "text": f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn: {str(e)}",
                            }
                        ],
                    ),
                ),
                None,
            )
            await self.send_task_notification(task)
            return SendTaskResponse(
                id=request.id,
                result=task,
            )

        return await self._process_agent_response(request, agent_response)

    async def on_send_task_subscribe(
        self, request: SendTaskStreamingRequest
    ) -> AsyncIterable[SendTaskStreamingResponse] | JSONRPCResponse:
        try:
            error = self._validate_request(request)
            if error:
                return error

            await self.upsert_task(request.params)

            if request.params.pushNotification:
                if not await self.set_push_notification_info(request.params.id, request.params.pushNotification):
                    return JSONRPCResponse(id=request.id, error=InvalidParamsError(message="Push notification URL is invalid"))

            task_send_params: TaskSendParams = request.params
            sse_event_queue = await self.setup_sse_consumer(task_send_params.id)

            # Return the streaming response directly
            return self.dequeue_events_for_sse(
                request.id, task_send_params.id, sse_event_queue
            )
        except Exception as e:
            logger.error(f"Error in on_send_task_subscribe: {e}")
            logger.error(traceback.format_exc())
            return JSONRPCResponse(
                id=request.id, error=InternalError(message=f"Internal error: {str(e)}")
            )

    async def _process_agent_response(
        self, request: SendTaskRequest, agent_response: dict
    ) -> SendTaskResponse:
        """Processes the agent's response and updates the task store."""
        task_send_params: TaskSendParams = request.params
        task_id = task_send_params.id
        task_status = None

        parts = [{"type": "text", "text": agent_response["content"]}]
        artifact = None
        if agent_response["require_user_input"]:
            task_status = TaskStatus(
                state="input-required",
                message=Message(role="agent", parts=parts),
            )
        else:
            task_status = TaskStatus(state="completed")
            artifact = Artifact(parts=parts)
        task = await self.update_store(
            task_id, task_status, None if artifact is None else [artifact]
        )
        await self.send_task_notification(task)
        return SendTaskResponse(
            id=request.id,
            result=task,
        )

    def _validate_request(
        self, request: Union[SendTaskRequest, SendTaskStreamingRequest]
    ) -> Union[None, SendTaskResponse, JSONRPCResponse]:
        """Validates the request parameters."""
        if not request.params.message or not request.params.message.parts:
            return utils.new_invalid_params_error(
                request.id, "Message or message parts are missing"
            )

        for part in request.params.message.parts:
            if part.type not in self.agent.SUPPORTED_CONTENT_TYPES:
                return utils.new_incompatible_types_error(request.id)
