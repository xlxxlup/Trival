from langgraph.graph import StateGraph, START,END
from .amusement_agent import get_graph as get_amusement_graph
from .ticket_agent import get_graph as get_ticket_graph

async def start():
    pass
async def conclusion():
    ...
async def get_graph() -> StateGraph:
    """
    Get the state graph for the agent.

    Returns:
        StateGraph: The state graph for the agent.
    """
    get_amusement_graph()
    graph = StateGraph()
    amusement_agent = await get_amusement_graph()
    ticket_agent = await get_ticket_graph()

    graph.add_node("start",start )
    graph.add_node("amusement_agent", amusement_agent)
    graph.add_node("ticket_agent", ticket_agent)
    graph.add_edge("conclusion", "conclusion")
    graph.add_edge("start", "amusement_agent")
    graph.add_edge("start", "ticket_agent")
    graph.add_edge("amusement_agent", "conclusion")
    graph.add_edge("ticket_agent", "conclusion")
    graph.add_edge("conclusion", END)


    graph.add_node()