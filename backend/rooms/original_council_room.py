"""Original council room implementation using the 3-stage process."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from backend.members.council_member import CouncilMember, TextResponse
from backend.primitives.deliverable import Deliverable
from backend.primitives.problem_definition import ProblemDefinition
from backend.primitives.problem_metadata import Metadata
from backend.rooms.base_room import BaseRoom
from backend.rooms.room import RoomStatus

class OriginalCouncilRoom(BaseRoom):
	"""Room that orchestrates the original council workflow.
	Stage 1 - Collect individual responses from all council models.
	Stage 2 - Each model ranks the anonymized responses.
	Stage 3 - Synthesize a final response based on rankings."""

	def __init__(self, problem: ProblemDefinition, name: str = None, members: List[CouncilMember] = None) -> None:
		super().__init__(problem, name=name or "Council Session Room", members=members)

		# Internal state for stages
		self._stage1_results: Optional[List[Dict[str, Any]]] = None
		self._stage2_results: Optional[List[Dict[str, Any]]] = None
		self._stage3_result: Optional[Dict[str, Any]] = None
		self._label_to_member: Optional[Dict[str, str]] = None

	async def kickoff(self) -> None:
		self._ensure_state_valid(RoomStatus.INACTIVE, RoomStatus.ACTIVE)

		user_query = self.problem.to_problem_string().strip()
		
		if not user_query:
			raise RuntimeError("Problem text must be non-empty for kickoff")
		
		await self._publish_event(
			"original.stage1",
			{"timestamp": datetime.now(timezone.utc).isoformat()},
		)
		
		self._stage1_results = await self._stage1_collect_responses(user_query)

		await self._publish_event(
			"original.stage2",
			{"timestamp": datetime.now(timezone.utc).isoformat()},
		)
		
		self._stage2_results, self._label_to_member = await self._stage2_collect_rankings(
			user_query,
			self._stage1_results)
		
		await self._publish_event(
			"original.stage3",
			{"timestamp": datetime.now(timezone.utc).isoformat()},
		)

		self._stage3_result = await self._stage3_synthesize_final(
			user_query,
			self._stage1_results,
			self._stage2_results,
		)

	async def close(self) -> Deliverable:
		self._ensure_state_valid(RoomStatus.ACTIVE, RoomStatus.CLOSING)

		if self._stage3_result is None:
			raise RuntimeError("Final synthesis missing; run kickoff first")

		aggregate_rankings: List[dict] = []

		if self._stage2_results is not None and self._label_to_member is not None:
			aggregate_rankings = self._calculate_aggregate_rankings(
				self._stage2_results,
				self._label_to_member,
			)

		metadata_entries: List[Metadata] = []
		if self._label_to_member is not None:
			metadata_entries.append(
				Metadata(
					key="label_to_member",
					value=json.dumps(self._label_to_member),
				)
			)

		if aggregate_rankings:
			metadata_entries.append(
				Metadata(
					key="aggregate_rankings",
					value=json.dumps(aggregate_rankings),
				)
			)

		deliverable_text_lines = ["## Final Synthesis", ""]
		deliverable_text_lines.append(self._stage3_result.get("response", "").strip())
		deliverable_text_lines.append("")

		if self._stage1_results is not None:
			deliverable_text_lines.append("## Stage 1 Responses")
			deliverable_text_lines.append("")
			for response in self._stage1_results:
				member_name = response.get("member", "unknown")
				content = response.get("response", "").strip()
				deliverable_text_lines.append(f"### {member_name}")
				deliverable_text_lines.append(content)
				deliverable_text_lines.append("")

		if self._stage2_results is not None:
			deliverable_text_lines.append("## Stage 2 Rankings")
			deliverable_text_lines.append("")
			for ranking in self._stage2_results:
				member_name = ranking.get("member", "unknown")
				ranking_text = ranking.get("ranking", "").strip()
				deliverable_text_lines.append(f"### {member_name}")
				deliverable_text_lines.append(ranking_text)
				deliverable_text_lines.append("")

		content = "\n".join(deliverable_text_lines).rstrip()

		deliverable = Deliverable(
			problem=self.problem,
			content=content,
			metadata=metadata_entries,
		)

		return deliverable

	async def _stage1_collect_responses(self, user_query: str) -> List[Dict[str, Any]]:
		"""
		Stage 1: Collect individual responses from all council models.

		Args:
			user_query: The user's question

		Returns:
			List of dicts with 'member' and 'response' keys
		"""
		# Ask all members in parallel
		tasks = [self._ask_member(member, user_query) for member in self._members]

		# Wait for all to complete
		responses = await asyncio.gather(*tasks)

		# Store results
		result = []

		for member, response in zip(self._members, responses):
			if response is not None:
				result.append({
					"member": member.name,
					"response": response.response
				})
		
		return result


	async def _stage2_collect_rankings(
		self,
		user_query: str,
		stage1_results: List[Dict[str, Any]],
	) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
		"""
		Stage 2: Each model ranks the anonymized responses.

		Args:
			user_query: The original user query

		Returns:
			Tuple of (rankings list, label_to_member mapping)
		"""
		# Create anonymized labels for responses (Response A, Response B, etc.)
		labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

		# Create mapping from label to member name
		label_to_member = {
			f"Response {label}": result['member']
			for label, result in zip(labels, stage1_results)
		}

		# Build the ranking prompt
		responses_text = "\n\n".join([
			f"Response {label}:\n{result['response']}"
			for label, result in zip(labels, stage1_results)
		])

		ranking_prompt = f"""You are evaluating different responses to the following question:

	Question: {user_query}

	Here are the responses from different members (anonymized):

	{responses_text}

	Your task:
	1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
	2. Then, at the very end of your response, provide a final ranking.

	IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
	- Start with the line "FINAL RANKING:" (all caps, with colon)
	- Then list the responses from best to worst as a numbered list
	- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
	- Do not add any other text or explanations in the ranking section

	Example of the correct format for your ENTIRE response:

	Response A provides good detail on X but misses Y...
	Response B is accurate but lacks depth on Z...
	Response C offers the most comprehensive answer...

	FINAL RANKING:
	1. Response C
	2. Response A
	3. Response B

	Now provide your evaluation and ranking:"""

		# Ask all members in parallel
		tasks = [self._ask_member(member, ranking_prompt)  for member in self._members]

		# Wait for all to complete
		responses = await asyncio.gather(*tasks)

		# Format results
		results: List[Dict[str, Any]] = []
		for member, response in zip(self._members, responses):
			if response is None:
				continue
			ranking_text = response.response
			parsed = self._parse_ranking_from_text(ranking_text)
			results.append(
				{
					"member": member.name,
					"ranking": ranking_text,
					"parsed_ranking": parsed,
				}
			)

		return results, label_to_member


	async def _stage3_synthesize_final(
		self,
		user_query: str,
		stage1_results: List[Dict[str, Any]],
		stage2_results: List[Dict[str, Any]],
	) -> Dict[str, Any]:
		"""
		Stage 3: Chairman synthesizes final response.

		Args:
			user_query: The original user query
			stage1_results: Individual member responses from Stage 1
			stage2_results: Rankings from Stage 2

		Returns:
			Dict with 'member' and 'response' keys
		"""
		# Build comprehensive context for chairman
		stage1_text = "\n\n".join([
			f"Member: {result['member']}\nResponse: {result['response']}"
			for result in stage1_results
		])

		stage2_text = "\n\n".join([
			f"Member: {result['member']}\nRanking: {result['ranking']}"
			for result in stage2_results
		])

		chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple members have provided responses to a user's question, and then ranked each other's responses.

	Original Question: {user_query}

	STAGE 1 - Individual Responses:
	{stage1_text}

	STAGE 2 - Peer Rankings:
	{stage2_text}

	Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
	- The individual responses and their insights
	- The peer rankings and what they reveal about response quality
	- Any patterns of agreement or disagreement

	Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

		# Ask one member (the chairman)
		if not self._members:
			raise RuntimeError("Room must have members before synthesis")
		chairman = self._members[0]
		response = await self._ask_member(chairman, chairman_prompt)

		if response is None:
			return {
				"member": chairman.name,
				"response": "Error: Unable to generate final synthesis.",
			}

		return {
			"member": chairman.name,
			"response": response.response,
		}
	
	async def _ask_member(self, member: CouncilMember, prompt: str) -> TextResponse:
		"""
		Ask all council member

		Args:
			member: The council member to ask
			prompt: The prompt to send to each member
		"""
		# Ask the specified member
		response = await member.think_and_respond(prompt)

		if response is None:
			return None
		
		await self._publish_event(
			"original.member_contribution",
			{
				"member": member.name,
				"timestamp": datetime.now(timezone.utc).isoformat(),
				"response": response.response,
				"reasoning": response.reasoning,
			},
			)
		
		return response

	@classmethod
	def _calculate_aggregate_rankings(
		cls,
		stage2_results: List[Dict[str, Any]],
		label_to_member: Dict[str, str]
	) -> List[Dict[str, Any]]:
		"""
		Calculate aggregate rankings across all members.

		Args:
			stage2_results: Rankings from each member
			label_to_member: Mapping from anonymous labels to member names

		Returns:
			List of dicts with member name and average rank, sorted best to worst
		"""
		from collections import defaultdict

		# Track positions for each member
		member_positions = defaultdict(list)

		for ranking in stage2_results:
			ranking_text = ranking['ranking']

			# Parse the ranking from the structured format
			parsed_ranking = cls._parse_ranking_from_text(ranking_text)

			for position, label in enumerate(parsed_ranking, start=1):
				if label in label_to_member:
					member_name = label_to_member[label]
					member_positions[member_name].append(position)

		# Calculate average position for each member
		aggregate = []
		for member, positions in member_positions.items():
			if positions:
				avg_rank = sum(positions) / len(positions)
				aggregate.append({
					"member": member,
					"average_rank": round(avg_rank, 2),
					"rankings_count": len(positions)
				})

		# Sort by average rank (lower is better)
		aggregate.sort(key=lambda x: x['average_rank'])

		return aggregate
	
	@staticmethod
	def _parse_ranking_from_text(ranking_text: str) -> List[str]:
		"""
		Parse the FINAL RANKING section from the model's response.

		Args:
			ranking_text: The full text response from the model

		Returns:
			List of response labels in ranked order
		"""
		import re

		# Look for "FINAL RANKING:" section
		if "FINAL RANKING:" in ranking_text:
			# Extract everything after "FINAL RANKING:"
			parts = ranking_text.split("FINAL RANKING:")
			if len(parts) >= 2:
				ranking_section = parts[1]
				# Try to extract numbered list format (e.g., "1. Response A")
				# This pattern looks for: number, period, optional space, "Response X"
				numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
				if numbered_matches:
					# Extract just the "Response X" part
					return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

				# Fallback: Extract all "Response X" patterns in order
				matches = re.findall(r'Response [A-Z]', ranking_section)
				return matches

		# Fallback: try to find any "Response X" patterns in order
		matches = re.findall(r'Response [A-Z]', ranking_text)
		return matches

    