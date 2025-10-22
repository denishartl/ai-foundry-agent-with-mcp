# Import necessary libraries

import os, time
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import (
    ListSortOrder,
    McpTool,
    RunStepActivityDetails,
)

from dotenv import load_dotenv

load_dotenv()

# Define agent name and instructions
agent_name = 'agent-noauth'
# Inital instructions ("system prompt") for the agent
agent_instructions = 'You are an agent which helps users access information from Microsoft Learn using the MCP tool. Use the MCP tool to get information from Microsoft Learn when relevant.'
# Agent message to be sent
agent_message = 'Which Azure Datacenter Locations exist in Europe?'


# MCP server information
mcp_server_url = 'https://learn.microsoft.com/api/mcp'
mcp_server_label = 'MicrosoftLearn'

project_client = AIProjectClient(
    endpoint=os.environ["PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# Initialize agent MCP tool
mcp_tool = McpTool(
    server_label=mcp_server_label,
    server_url=mcp_server_url
)

# Create agent with MCP tool and process agent run
with project_client:
    agents_client = project_client.agents

    # Create a new agent
    agent = agents_client.create_agent(
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        name=agent_name,
        instructions=agent_instructions,
        tools=mcp_tool.definitions
    )

    print(f"Created agent, ID: {agent.id}")
    print(f"MCP Server: {mcp_tool.server_label} at {mcp_tool.server_url}")

    # Create thread for communication
    thread = agents_client.threads.create()
    print(f"Created thread, ID: {thread.id}")

    # Create message to thread
    message = agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=agent_message,
    )
    print(f"Created message, ID: {message.id}")
    
    # Don't require approval for tool calls
    mcp_tool.set_approval_mode("never")

    run = agents_client.runs.create(thread_id=thread.id, agent_id=agent.id, tool_resources=mcp_tool.resources)
    print(f"Created run, ID: {run.id}")

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

        print(f"Current run status: {run.status}")

    print(f"Run completed with status: {run.status}")
    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    # Display run steps and tool calls
    run_steps = agents_client.run_steps.list(thread_id=thread.id, run_id=run.id)

    # Loop through each step
    for step in run_steps:
        print(f"Step {step['id']} status: {step['status']}")

        # Check if there are tool calls in the step details
        step_details = step.get("step_details", {})
        tool_calls = step_details.get("tool_calls", [])

        if tool_calls:
            print("  MCP Tool calls:")
            for call in tool_calls:
                print(f"    Tool Call ID: {call.get('id')}")
                print(f"    Type: {call.get('type')}")

        if isinstance(step_details, RunStepActivityDetails):
            for activity in step_details.activities:
                for function_name, function_definition in activity.tools.items():
                    print(
                        f'  The function {function_name} with description "{function_definition.description}" will be called.:'
                    )
                    if len(function_definition.parameters) > 0:
                        print("  Function parameters:")
                        for argument, func_argument in function_definition.parameters.properties.items():
                            print(f"      {argument}")
                            print(f"      Type: {func_argument.type}")
                            print(f"      Description: {func_argument.description}")
                    else:
                        print("This function has no parameters")

        print()  # add an extra newline between steps

    # Fetch and log all messages
    messages = agents_client.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    print("\nConversation:")
    print("-" * 50)
    for msg in messages:
        if msg.text_messages:
            last_text = msg.text_messages[-1]
            print(f"{msg.role.upper()}: {last_text.text.value}")
            print("-" * 50)