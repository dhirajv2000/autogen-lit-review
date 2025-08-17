import arxiv
import os
import asyncio
from typing import AsyncGenerator, Dict, List

from autogen_core.tools import FunctionTool
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage

"""
Defining a custom tool that searches the arXiv database
Returns a dict containing title, authors, summary and the URL to the paper.
"""
def arxiv_query(query:str, result_count: int = 10) -> List[dict]:
    arxiv_client = arxiv.Client()
    search = arxiv.Search(query = query, max_results = result_count, sort_by = arxiv.SortCriterion.Relevance)
    response = []
    
    for result in arxiv_client.results(search):
        response.append(
            {
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "published_date": result.published.strftime("%Y-%m-%d"),
                "summary": result.summary,
                "pdf_url": result.pdf_url
            }
        )
    
    return response

arxiv_tool = FunctionTool(
    func = arxiv_query,
    description = (
        "Query arXiv and return `result_count` entries. Each entry in the result contains title, authors, publication date, abstract summary and pdf_url "
    )
)

"""
Here we define a multi agent team that searches the arxiv database and summarises the research papers in a human readable form
This will be a multi agent RoundRobinGroup chat that will be used to perform the literature review
"""

def create_team(model = "gpt-4o"):
    api_key = os.getenv('OPENAI_API_KEY'))
    llm_model = OpenAIChatCompletionClient(model = model, api_key = api_key)
    
    search_agent = AssistantAgent(
        name = "search_agent",
        description = "Generates an arXiv query and retrieves relevant papers via the tool",
        system_message = (
            "You are responsible for turning the requested topic into an usable arXiv search"
            "Call the attached tool and fetch upto 30 papers"
            "From these, pick the best subset and return the exact number of papers requested as JSON to the summarizer agent"),
        tools = [arxiv_tool],
        model_client  = llm_model,
        reflect_on_tool_use = True,
    )
    
    summarizer_agent = AssistantAgent(
        name="summarizer",
        description="Writes a short literature review of the chose papers",
        system_message=(
            "Act as an expert acadmeic researcher. You are provided with a json list of papers"
            "Provide a Markdown literature review with:"
            "  1) A 4 sentence introduction to the topic.\n"
            "  2) One bullet per paper containing: title (Markdown link), authors, the "
            "specific problem addressed, and the main contribution.\n"
            "  3) A one-sentence takeaway conclusion."
        ),
        model_client=llm_model,
    )

    return RoundRobinGroupChat(participants=[search_agent, summarizer_agent], max_turns=2)
    
"""
API for future front end

"""      
async def generate_lit_review(topic: str, num_papers: int = 5, model: str = "gpt-4o") -> AsyncGenerator[str, None]:
    team = create_team(model=model)
    task_prompt = f"Your a research assitant for a professor. Perform a literature review on  the **{topic}** and return exactly {num_papers} relevant papers."
    async for msg in team.run_stream(task=task_prompt):
        if isinstance(msg, TextMessage):
            yield f"{msg.source}: {msg.content}"


"""
CLI Test
"""
if __name__ == "__main__":
    async def _demo() -> None:
        # Require a non-empty topic (keep prompting until provided)
        while True:
            topic = input("Enter topic for literature review (required): ").strip()
            if topic:
                break
            print("Topic cannot be empty. Please enter a topic.")

        # Ask for number of papers (validate integer; default to 5 if left blank)
        num_input = input("How many papers do you want? [default 5]: ").strip()
        try:
            num_papers = int(num_input) if num_input else 5
        except ValueError:
            print("Invalid number entered, defaulting to 5 papers.")
            num_papers = 5

        print(f"\nStarting literature review for topic: '{topic}' (num_papers={num_papers})\n")

        async for line in generate_lit_review(topic, num_papers=num_papers):
            print(line)

    asyncio.run(_demo())
        