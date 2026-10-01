from typing import TypedDict, Annotated, List, Any, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import settings
from agents.tools.ucp_tools import COMMERCE_TOOLS

class CommerceState(TypedDict):
    messages: Annotated[List[Any], add_messages]

# 1. Initialize Gemini LLM with bound UCP tools
llm = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL,
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.1
).bind_tools(COMMERCE_TOOLS)

# 2. Agent Node
async def shopping_agent_node(state: CommerceState) -> dict:
    messages = state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}

# 3. Router Condition
def should_continue(state: CommerceState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# 4. Graph Construction
builder = StateGraph(CommerceState)
builder.add_node("agent", shopping_agent_node)
builder.add_node("tools", ToolNode(COMMERCE_TOOLS))

builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", should_continue, ["tools", END])
builder.add_edge("tools", "agent")

# Sanitize connection string to standard libpq URI format
db_conninfo = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

# Connection pool for PostgreSQL Checkpointer
pg_pool = AsyncConnectionPool(
    conninfo=db_conninfo,
    max_size=10,
    open=False,
    kwargs={"autocommit": True}
)

async def get_compiled_graph():
    if pg_pool.closed:
        await pg_pool.open()
    checkpointer = AsyncPostgresSaver(pg_pool)
    # Automatically creates checkpoints table if it doesn't exist
    await checkpointer.setup()
    return builder.compile(checkpointer=checkpointer)