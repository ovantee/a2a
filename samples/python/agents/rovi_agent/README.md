# ROVI Customer Service Agent

This sample uses LangGraph to create a customer service agent for ROVI, a company specializing in teambuilding events. The agent is hosted as an A2A server and can provide information about teambuilding concepts, pricing, and availability.

## Features

- **Multi-turn Conversations**: Agent can request additional information when needed
- **Real-time Streaming**: Provides status updates during processing
- **Push Notifications**: Support for webhook-based notifications
- **Conversational Memory**: Maintains context across interactions
- **Vietnamese Language Support**: Responds in Vietnamese by default

## Prerequisites

- Python 3.12 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to Google Gemini API and API Key

## Running the Agent

1. Navigate to the agent directory:
   ```bash
   cd samples/python/agents/rovi_agent
   ```

2. Create an environment file with your API key:
   ```bash
   echo "GOOGLE_API_KEY=your_api_key_here" > .env
   ```

3. Install dependencies and run the agent:
   ```bash
   uv pip install -e .
   python -m agents.rovi_agent
   ```

4. The agent will start on http://localhost:10001 by default

## Interacting with the Agent

You can interact with the agent using the A2A CLI:

```bash
cd samples/python/hosts/cli
python -m hosts.cli --agent http://localhost:10007
```

## Teambuilding Concepts

The agent has knowledge about various teambuilding concepts:

1. **HÀNH TRÌNH XANH**: Environmental-focused teambuilding activities
2. **Ngày hội gia đình**: Family day events for companies
3. **Amazing 4.0**: Modern technology-integrated teambuilding
4. **Trekking**: Outdoor adventure and trekking activities
5. **Kick off**: Kickoff events for new projects or quarters
6. **Sức mạnh EKIP**: Team strength and collaboration focused activities

## Example Queries

- "Tôi muốn tổ chức một sự kiện teambuilding cho công ty"
- "Cho tôi biết thông tin về các gói teambuilding"
- "Giá của gói Sức mạnh EKIP là bao nhiêu?"
- "Ngày 15/6 có thể tổ chức sự kiện không?"
