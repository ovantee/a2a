## Tour Booking Agent

This sample uses the Agent Development Kit (ADK) to create a "Tour Booking" agent that is hosted as an A2A server.

This agent takes text requests from the client and, if any details are missing, returns a webform for the client (or its user) to fill out. After the client fills out the form, the agent will process the booking.

## Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to Google Gemini API and API Key

## Running the Sample

1. Navigate to the samples directory:
    ```bash
    cd samples/python/agents/booking_tour
    ```
2. Create an environment file with your API key:
    ```bash
    echo "GOOGLE_API_KEY=your_api_key_here" > .env
    ```
3. Run the agent:
    ```bash
    uv run .
    ```
4. Run one of the [client apps](/samples/python/hosts/README.md)

## Features

- Multi-turn conversations for collecting booking information
- Form-based data collection
- Streaming responses
- Booking confirmation and status updates