from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from common.utils.push_notification_auth import PushNotificationSenderAuth
from agents.rovi_agent.task_manager import AgentTaskManager
from agents.rovi_agent.agent import CustomerServiceAgent
import click
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10007)
def main(host, port):
    """Starts the ROVI Customer Service Agent server."""
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")

        capabilities = AgentCapabilities(streaming=True, pushNotifications=True)
        skill = AgentSkill(
            id="customer_service",
            name="Customer Service for Teambuilding Events",
            description="Provides information about teambuilding events, pricing, and availability",
            tags=["teambuilding", "customer service", "events"],
            examples=[
                "Tôi muốn tổ chức một sự kiện teambuilding cho công ty",
                "Cho tôi biết thông tin về các gói teambuilding",
                "Giá của gói Sức mạnh EKIP là bao nhiêu?",
                "Ngày 15/6 có thể tổ chức sự kiện không?",
            ],
        )
        agent_card = AgentCard(
            name="ROVI Customer Service Agent",
            description="Hỗ trợ khách hàng với thông tin về các sự kiện teambuilding, giá cả và lịch trình",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=CustomerServiceAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=CustomerServiceAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(agent=CustomerServiceAgent(), notification_sender_auth=notification_sender_auth),
            host=host,
            port=port,
        )

        server.app.add_route(
            "/.well-known/jwks.json", notification_sender_auth.handle_jwks_endpoint, methods=["GET"]
        )

        logger.info(f"Starting the ROVI Customer Service Agent server on {host}:{port}")
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
