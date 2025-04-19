import json
import random
import csv
import os
from datetime import datetime
from typing import Any, AsyncIterable, Dict, Optional
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Local cache of created booking_ids for demo purposes
booking_ids = set()

# Dictionary to store booking information
booking_info = {}

# CSV file path for storing booking information
CSV_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'booking.csv')
print(f"CSV file will be saved at: {CSV_FILE_PATH}")

# Function to test CSV writing
def test_csv_writing():
    """Test function to verify CSV writing functionality."""
    test_booking_id = "booking_test_" + str(random.randint(1000000, 9999999))
    booking_ids.add(test_booking_id)

    # Create a test booking
    booking_info[test_booking_id] = {
        "booking_id": test_booking_id,
        "destination": "Test Destination",
        "start_date": "01/01/2025",
        "end_date": "10/01/2025",
        "num_people": 2,
        "budget": "1000 USD",
        "status": "confirmed",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "confirmed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Save to CSV
    try:
        save_booking_to_csv(test_booking_id)
        print(f"Test booking {test_booking_id} saved successfully")

        # Verify the file exists and contains the test booking
        if os.path.isfile(CSV_FILE_PATH):
            with open(CSV_FILE_PATH, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                rows = list(reader)
                found = False
                for row in rows:
                    if row.get('booking_id') == test_booking_id:
                        found = True
                        break
                if found:
                    print(f"Test booking {test_booking_id} found in CSV file")
                else:
                    print(f"Test booking {test_booking_id} NOT found in CSV file")
        else:
            print(f"CSV file {CSV_FILE_PATH} does not exist after test")
    except Exception as e:
        print(f"Error during CSV test: {e}")

def create_booking_form(destination: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       num_people: Optional[int] = None,
                       budget: Optional[str] = None) -> dict[str, Any]:
    """Create a booking form with the given information.

    Args:
        destination: The destination for the tour
        start_date: Start date of the tour
        end_date: End date of the tour
        num_people: Number of people
        budget: Budget per person

    Returns:
        dict[str, Any]: A dictionary containing the booking form data.
    """
    # Check if we already have a booking in progress
    existing_booking_id = None
    for bid in booking_ids:
        if bid in booking_info and booking_info[bid]["status"] == "pending":
            # Check if this is for the same destination
            if destination and booking_info[bid]["destination"] == destination:
                existing_booking_id = bid
                break
            # Or if no destination was specified in the current call
            elif not destination:
                existing_booking_id = bid
                break

    if existing_booking_id:
        # Update existing booking with new information
        booking_id = existing_booking_id
        if destination:
            booking_info[booking_id]["destination"] = destination
        if start_date:
            booking_info[booking_id]["start_date"] = start_date
        if end_date:
            booking_info[booking_id]["end_date"] = end_date
        if num_people:
            booking_info[booking_id]["num_people"] = num_people
        if budget:
            booking_info[booking_id]["budget"] = budget

        print(f"Updated existing booking: {booking_id}")
    else:
        # Create a new booking
        booking_id = "booking_" + str(random.randint(1000000, 9999999))
        booking_ids.add(booking_id)

        # Store booking information in the dictionary
        booking_info[booking_id] = {
            "booking_id": booking_id,
            "destination": "<destination>" if not destination else destination,
            "start_date": "<start date>" if not start_date else start_date,
            "end_date": "<end date>" if not end_date else end_date,
            "num_people": "<number of people>" if not num_people else num_people,
            "budget": "<budget per person>" if not budget else budget,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        print(f"Created new booking: {booking_id}")

    # Save booking information to CSV file
    try:
        print(f"Saving booking form to CSV: {booking_id}")
        save_booking_to_csv(booking_id)
        print(f"Successfully saved booking form {booking_id} to CSV")
    except Exception as e:
        print(f"Error saving booking form to CSV: {e}")

    return {
        "booking_id": booking_id,
        "destination": booking_info[booking_id]["destination"],
        "start_date": booking_info[booking_id]["start_date"],
        "end_date": booking_info[booking_id]["end_date"],
        "num_people": booking_info[booking_id]["num_people"],
        "budget": booking_info[booking_id]["budget"],
    }

def process_booking(booking_id: Optional[str] = None,
                   destination: Optional[str] = None,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None,
                   num_people: Optional[int] = None,
                   budget: Optional[str] = None) -> dict[str, Any]:
    """Process the booking for a given booking_id or create a new booking.

    Args:
        booking_id: The ID of the booking to process
        destination: The destination for the tour (if creating a new booking)
        start_date: Start date of the tour (if creating a new booking)
        end_date: End date of the tour (if creating a new booking)
        num_people: Number of people (if creating a new booking)
        budget: Budget per person (if creating a new booking)

    Returns:
        dict[str, Any]: A dictionary containing the booking status
    """
    # Handle the case where LLM passes "booking_id" as a string literal
    if booking_id == "booking_id":
        if booking_ids:
            # Use the most recently created booking_id
            booking_id = list(booking_ids)[-1]
            print(f"Using most recent booking_id: {booking_id}")
        else:
            # No existing booking, create a new one
            booking_id = None

    # If no booking_id or invalid booking_id, create a new booking
    if booking_id is None or booking_id not in booking_ids:
        if destination or start_date or end_date or num_people or budget:
            # Create a new booking with provided information
            booking_form = create_booking_form(
                destination=destination,
                start_date=start_date,
                end_date=end_date,
                num_people=num_people,
                budget=budget
            )
            booking_id = booking_form["booking_id"]
            print(f"Created new booking during process: {booking_id}")
        elif booking_id is None:
            # Create a default booking if no information provided
            booking_form = create_booking_form(
                destination="Tokyo",
                start_date="10/8/2024",
                end_date="20/8/2024",
                num_people=3,
                budget="3000 USD"
            )
            booking_id = booking_form["booking_id"]
            print(f"Created default booking: {booking_id}")
        else:
            return {"booking_id": booking_id, "status": "Error: Invalid booking_id."}

    # Update booking status
    if booking_id in booking_info:
        print(f"Updating booking status for {booking_id}")
        booking_info[booking_id]["status"] = "confirmed"
        booking_info[booking_id]["confirmed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Ensure all required fields are present
        for field in ["destination", "start_date", "end_date", "num_people", "budget"]:
            if field not in booking_info[booking_id] or not booking_info[booking_id][field]:
                print(f"Warning: Field '{field}' is missing or empty in booking {booking_id}")
                booking_info[booking_id][field] = f"<{field}>"

        print(f"Attempting to save booking {booking_id} to CSV")
        # Save booking information to CSV file
        try:
            save_booking_to_csv(booking_id)
            print(f"Successfully saved booking {booking_id} to CSV")
        except Exception as e:
            print(f"Error saving booking to CSV: {e}")

        # Run a test to verify CSV functionality
        try:
            test_csv_writing()
        except Exception as e:
            print(f"CSV test failed: {e}")

    return {
        "booking_id": booking_id,
        "status": "confirmed",
        "next_steps": "Our travel agent will contact you shortly with detailed itinerary."
    }

def save_booking_to_csv(booking_id: str) -> None:
    """Save booking information to CSV file.

    Args:
        booking_id: The ID of the booking to save
    """
    if booking_id not in booking_info:
        print(f"Warning: Booking ID {booking_id} not found in booking_info")
        return

    booking = booking_info[booking_id]
    print(f"Preparing to save booking: {booking}")

    # Ensure all required fields are present
    required_fields = ["booking_id", "destination", "start_date", "end_date",
                      "num_people", "budget", "status", "created_at"]

    for field in required_fields:
        if field not in booking or not booking[field]:
            print(f"Warning: Required field '{field}' is missing or empty in booking {booking_id}")
            # Set a default value for missing fields
            if field == "confirmed_at" and booking["status"] == "confirmed":
                booking[field] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif field not in booking:
                booking[field] = f"<{field}>"

    # Make sure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(CSV_FILE_PATH)), exist_ok=True)

    # Check if file exists
    file_exists = os.path.isfile(CSV_FILE_PATH)
    print(f"CSV file exists: {file_exists}, path: {CSV_FILE_PATH}")

    try:
        # Create a copy of the booking data to avoid modifying the original
        booking_data = booking.copy()

        # Convert any non-string values to strings for CSV compatibility
        for key, value in booking_data.items():
            if not isinstance(value, str):
                booking_data[key] = str(value)

        with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as file:
            fieldnames = ["booking_id", "destination", "start_date", "end_date",
                         "num_people", "budget", "status", "created_at", "confirmed_at"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            # Write header if file doesn't exist
            if not file_exists:
                writer.writeheader()
                print("Wrote CSV header")

            # Write booking information
            writer.writerow(booking_data)
            print(f"Wrote booking row for {booking_id} with data: {booking_data}")

        print(f"Booking {booking_id} saved to {CSV_FILE_PATH}")
    except Exception as e:
        import traceback
        print(f"Error saving booking to CSV: {e}")
        print(f"Error details: {traceback.format_exc()}")

class TourBookingAgent:
    """An agent that handles tour booking requests."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = "remote_agent"
        self._runner = Runner(
            app_name=self._agent.name,
            agent=self._agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
            memory_service=InMemoryMemoryService(),
        )

    def invoke(self, query, session_id) -> str:
        session = self._runner.session_service.get_session(
            app_name=self._agent.name, user_id=self._user_id, session_id=session_id
        )
        content = types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        )
        if session is None:
            session = self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )
        events = list(self._runner.run(
            user_id=self._user_id, session_id=session.id, new_message=content
        ))
        if not events or not events[-1].content or not events[-1].content.parts:
            return ""
        return "\n".join([p.text for p in events[-1].content.parts if p.text])

    async def stream(self, query, session_id) -> AsyncIterable[Dict[str, Any]]:
        session = self._runner.session_service.get_session(
            app_name=self._agent.name, user_id=self._user_id, session_id=session_id
        )
        content = types.Content(
            role="user", parts=[types.Part.from_text(text=query)]
        )
        if session is None:
            session = self._runner.session_service.create_session(
                app_name=self._agent.name,
                user_id=self._user_id,
                state={},
                session_id=session_id,
            )
        async for event in self._runner.run_async(
            user_id=self._user_id, session_id=session.id, new_message=content
        ):
            if event.is_final_response():
                response = ""
                if (event.content and event.content.parts
                    and event.content.parts[0].text):
                    response = "\n".join([p.text for p in event.content.parts if p.text])
                elif (event.content and event.content.parts
                      and any([True for p in event.content.parts if p.function_response])):
                    response = next((p.function_response.model_dump()
                                  for p in event.content.parts))
                yield {
                    "is_task_complete": True,
                    "content": response,
                }
            else:
                yield {
                    "is_task_complete": False,
                    "updates": "Processing your tour booking request...",
                }

    def _build_agent(self) -> LlmAgent:
        """Builds the LLM agent for the tour booking agent."""
        return LlmAgent(
            model="gemini-2.0-flash-001",
            name="tour_booking_agent",
            description=(
                "This agent handles the tour booking process by collecting necessary "
                "information and processing booking requests."
            ),
            instruction="""
            You are an agent who handles tour booking requests.

            When a user wants to book a tour, you need to collect:
            - Destination
            - Start date
            - End date
            - Number of people
            - Budget per person

            If any information is missing, ask for it using the booking form.
            Once all information is collected, process the booking.

            Use the following functions:
            - create_booking_form: Creates a form with the booking information
            - process_booking: Processes the booking with a given booking_id

            Example conversation:
            User: I want to book a tour to Paris
            Assistant: I'll help you book a tour to Paris. I need some additional information.
            {create_booking_form(destination="Paris")}

            User: The start date is 2024-07-01, end date is 2024-07-07, for 2 people with a budget of $2000 per person
            Assistant: Thank you for providing the details. I'll process your booking now.
            {process_booking("booking_id")}
            """,
            tools=[
                create_booking_form,
                process_booking,
            ],
        )