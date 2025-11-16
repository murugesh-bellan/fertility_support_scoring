"""LangGraph agent for emotional scoring."""

import json
import time
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from agent.prompts import (
    ACTION_ROUTING_PROMPT,
    DOMAIN_VALIDATION_PROMPT,
    EMOTIONAL_SCORING_PROMPT,
)
from models.bedrock import HolisticAIBedrockChat
from models.schemas import ActionType


class AgentState(TypedDict):
    """State for the scoring agent."""

    message: str
    domain_match: bool
    domain_reasoning: str
    score: int
    confidence: float
    reasoning: str
    key_indicators: list[str]
    recommended_action: ActionType
    action_rationale: str
    tokens_used: int
    start_time: float


class ScoringAgent:
    """Agent for scoring emotional distress in messages."""

    def __init__(self, llm: HolisticAIBedrockChat):
        """Initialize the agent with an LLM."""
        self.llm = llm
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("validate_domain", self._validate_domain)
        workflow.add_node("score_emotion", self._score_emotion)
        workflow.add_node("route_action", self._route_action)

        # Define edges
        workflow.set_entry_point("validate_domain")
        workflow.add_conditional_edges(
            "validate_domain",
            self._should_continue_scoring,
            {
                "score": "score_emotion",
                "end": END,
            },
        )
        workflow.add_edge("score_emotion", "route_action")
        workflow.add_edge("route_action", END)

        return workflow.compile()

    async def _validate_domain(self, state: AgentState) -> AgentState:
        """Validate if message is in domain."""
        prompt = DOMAIN_VALIDATION_PROMPT.format(message=state["message"])

        result = await self.llm.ainvoke([HumanMessage(content=prompt)])
        response_text = result.content

        # Parse JSON response
        try:
            parsed = json.loads(response_text)
            state["domain_match"] = parsed.get("domain_match", False)
            state["domain_reasoning"] = parsed.get("reasoning", "")
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            state["domain_match"] = False
            state["domain_reasoning"] = "Failed to parse domain validation response"

        # Estimate tokens (rough approximation)
        state["tokens_used"] = state.get("tokens_used", 0) + len(prompt.split()) + len(
            response_text.split()
        )

        return state

    async def _score_emotion(self, state: AgentState) -> AgentState:
        """Score emotional distress level."""
        prompt = EMOTIONAL_SCORING_PROMPT.format(message=state["message"])

        result = await self.llm.ainvoke([HumanMessage(content=prompt)])
        response_text = result.content

        # Parse JSON response
        try:
            parsed = json.loads(response_text)
            state["score"] = parsed.get("score", 5)
            state["confidence"] = parsed.get("confidence", 0.5)
            state["reasoning"] = parsed.get("reasoning", "")
            state["key_indicators"] = parsed.get("key_indicators", [])
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            state["score"] = 5
            state["confidence"] = 0.3
            state["reasoning"] = "Failed to parse scoring response"
            state["key_indicators"] = []

        # Estimate tokens
        state["tokens_used"] = state.get("tokens_used", 0) + len(prompt.split()) + len(
            response_text.split()
        )

        return state

    async def _route_action(self, state: AgentState) -> AgentState:
        """Determine recommended action based on score."""
        score = state["score"]

        # Simple rule-based routing (no LLM needed for this)
        if score == 10:
            action = ActionType.EMERGENCY_ALERT
            rationale = "Score 10 indicates crisis - immediate emergency intervention required"
        elif score >= 8:
            action = ActionType.BOOK_GP_APPOINTMENT
            rationale = f"Score {score} indicates high distress - GP appointment needed"
        elif score >= 6:
            action = ActionType.NOTIFY_CARETAKER
            rationale = f"Score {score} indicates moderate concern - caretaker notification"
        elif score >= 1:
            action = ActionType.LOG_ONLY
            rationale = f"Score {score} indicates low concern - monitoring only"
        else:
            action = ActionType.OUT_OF_DOMAIN
            rationale = "Message is out of domain"

        state["recommended_action"] = action
        state["action_rationale"] = rationale

        return state

    def _should_continue_scoring(self, state: AgentState) -> str:
        """Decide whether to continue with scoring or end."""
        if state["domain_match"]:
            return "score"
        else:
            # Set out-of-domain values
            state["score"] = -1
            state["confidence"] = 1.0
            state["reasoning"] = state["domain_reasoning"]
            state["key_indicators"] = []
            state["recommended_action"] = ActionType.OUT_OF_DOMAIN
            state["action_rationale"] = "Message is not related to fertility or emotional support"
            return "end"

    async def score_message(
        self,
        message: str,
        config: dict = None,
        langsmith_enabled: bool = False,
        run_id: str = None
    ) -> dict:
        """Score a message and return results."""
        initial_state: AgentState = {
            "message": message,
            "domain_match": False,
            "domain_reasoning": "",
            "score": 0,
            "confidence": 0.0,
            "reasoning": "",
            "key_indicators": [],
            "recommended_action": ActionType.LOG_ONLY,
            "action_rationale": "",
            "tokens_used": 0,
            "start_time": time.time(),
        }

        # Run the graph with optional config for LangSmith metadata
        final_state = await self.graph.ainvoke(initial_state, config=config)

        # Calculate latency
        latency_ms = int((time.time() - final_state["start_time"]) * 1000)

        result = {
            "score": final_state["score"],
            "confidence": final_state["confidence"],
            "domain_match": final_state["domain_match"],
            "reasoning": final_state["reasoning"],
            "key_indicators": final_state["key_indicators"],
            "recommended_action": final_state["recommended_action"],
            "action_rationale": final_state["action_rationale"],
            "tokens_used": final_state["tokens_used"],
            "latency_ms": latency_ms,
        }

        # Add run_id if LangSmith is enabled
        if langsmith_enabled and run_id:
            result["run_id"] = run_id

        return result
