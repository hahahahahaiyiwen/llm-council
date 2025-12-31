from azure.identity import DefaultAzureCredential
from agent_framework.azure import AzureOpenAIChatClient
from dotenv import load_dotenv
from prompt_template import PromptTemplate
from typing import List
import random

from backend.config import COUNCIL_MODELS, AGENT_NAMES
from backend.members.agent_member import AgentMember
from backend.members.tools.vote import vote_box

load_dotenv()

class AgentMemberFactory:
    _credential = DefaultAzureCredential()
    _template = PromptTemplate(
"""
You are council member ${name} in a collaborative problem-solving council meeting.

	# Collaboration Rhythm
	- **Clarify the objective:** Confirm the shared goal if no one has done so or if you think the current discussion is drifted.
	- **Share concise insights:** Be clear and to the point with less than 200 words.
	- **Agree, but refine:** Consider using “I agree, but…”.
	- **Challenge constructively:** Be critical, voice doubts with reasons and sketch a repair.
	- **Converge and capture:** Push the discussion toward a recommendation or answer.
""")

    def create_agent_member(self, model: str = None, name: str = None) -> AgentMember:
        if model is None:
            model = random.choice(COUNCIL_MODELS)
        
        if name is None:
            name = random.choice(AGENT_NAMES)
        
        # Chat only, no foundry agent created
        client = AzureOpenAIChatClient(
            credential=self._credential,
            deployment_name=model,
        )

        agent = client.create_agent(
            name=name,
            instructions=self._template.to_string(name=name),
            allow_multiple_tool_calls=True,
            tools=[vote_box.vote],)

        return AgentMember(name=name, agent=agent)
    
    def create_multiple_agent_members(self, count: int) -> List[AgentMember]:
        members = []
        while len(members) < count:
            model = random.choice(COUNCIL_MODELS)
            name = random.choice(AGENT_NAMES)
            if name in [member.name for member in members]:
                continue  # ensure unique names
            member = self.create_agent_member(model=model, name=name)
            members.append(member)
        return members