from common.server import A2AServer
from common.types import AgentCard, AgentCapabilities, AgentSkill, MissingAPIKeyError
from task_manager import AgentTaskManager
from agent import TourBookingAgent
import click
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=10003)
def main(host, port):
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")
        
        capabilities = AgentCapabilities(streaming=True)
        skill = AgentSkill(
            id="book_tour",
            name="Tour Booking Tool",
            description="Helps users book tours by collecting necessary information and processing bookings.",
            tags=["travel", "booking", "tour"],
            examples=[
                "I want to book a tour to Paris",
                "Book a vacation package to Japan",
            ],
        )
        agent_card = AgentCard(
            name="Tour Booking Agent",
            description="This agent handles the tour booking process by collecting necessary information and processing booking requests.",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=TourBookingAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=TourBookingAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(agent=TourBookingAgent()),
            host=host,
            port=port,
        )
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)

if __name__ == "__main__":
    main()