"""HolisticAI Bedrock Proxy integration."""

import json
from typing import Any, AsyncIterator, Iterator, List, Optional

import httpx
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, SecretStr


class HolisticAIBedrockChat(BaseChatModel):
    """Chat model for Holistic AI Bedrock Proxy API."""

    api_endpoint: str = Field(
        default="https://ctwa92wg1b.execute-api.us-east-1.amazonaws.com/prod/invoke",
        description="API endpoint URL",
    )
    team_id: str = Field(description="Team ID for authentication")
    api_token: SecretStr = Field(description="API token for authentication")
    model: str = Field(
        default="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="Model identifier",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1)
    timeout: int = Field(default=60, description="Request timeout in seconds")

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "holistic-ai-bedrock"

    def _extract_system_prompt(self, messages: List[BaseMessage]) -> Optional[str]:
        """Extract system prompt from messages."""
        for msg in messages:
            if isinstance(msg, SystemMessage):
                return msg.content
        return None

    def _convert_messages_to_api_format(self, messages: List[BaseMessage]) -> List[dict]:
        """Convert LangChain messages to API format."""
        api_messages = []
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # System messages handled separately
                continue
            elif isinstance(msg, HumanMessage):
                api_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                api_messages.append({"role": "assistant", "content": msg.content})
            else:
                # Handle other message types
                api_messages.append({"role": "user", "content": str(msg.content)})
        
        return api_messages

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate response synchronously."""
        system_prompt = self._extract_system_prompt(messages)
        api_messages = self._convert_messages_to_api_format(messages)

        payload = {
            "team_id": self.team_id,
            "api_token": self.api_token.get_secret_value(),
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
        }

        if self.temperature is not None:
            payload["temperature"] = self.temperature

        if system_prompt:
            # Add system prompt as first user message
            payload["messages"].insert(0, {"role": "user", "content": f"System: {system_prompt}"})

        headers = {
            "Content-Type": "application/json",
            "X-Team-ID": self.team_id,
            "X-API-Token": self.api_token.get_secret_value(),
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            # Extract content from Bedrock response
            content = ""
            if "content" in result and len(result["content"]) > 0:
                for content_block in result["content"]:
                    if isinstance(content_block, dict):
                        if content_block.get("type") == "text":
                            text = content_block.get("text", "")
                            if text:
                                content += text + "\n" if content else text
                    elif isinstance(content_block, str):
                        content += content_block
                content = content.rstrip("\n")
            elif "text" in result:
                content = result["text"]
            else:
                content = str(result)

            message = AIMessage(content=content)
            generation = ChatGeneration(message=message)
            chat_result = ChatResult(generations=[generation])

            return chat_result

        except httpx.HTTPStatusError as e:
            error_msg = f"Error calling Holistic AI Bedrock API: {e}"
            if e.response:
                try:
                    error_detail = e.response.text
                    error_msg += f"\nResponse: {error_detail}"
                    try:
                        error_json = e.response.json()
                        error_msg += f"\nError details: {json.dumps(error_json, indent=2)}"
                    except:
                        pass
                except:
                    pass
            raise ValueError(error_msg)
        except Exception as e:
            raise ValueError(f"Error calling Holistic AI Bedrock API: {e}")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate response asynchronously."""
        system_prompt = self._extract_system_prompt(messages)
        api_messages = self._convert_messages_to_api_format(messages)

        payload = {
            "team_id": self.team_id,
            "api_token": self.api_token.get_secret_value(),
            "model": self.model,
            "messages": api_messages,
            "max_tokens": self.max_tokens,
        }

        if self.temperature is not None:
            payload["temperature"] = self.temperature

        if system_prompt:
            # Add system prompt as first user message
            payload["messages"].insert(0, {"role": "user", "content": f"System: {system_prompt}"})

        headers = {
            "Content-Type": "application/json",
            "X-Team-ID": self.team_id,
            "X-API-Token": self.api_token.get_secret_value(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            # Extract content from Bedrock response
            content = ""
            if "content" in result and len(result["content"]) > 0:
                for content_block in result["content"]:
                    if isinstance(content_block, dict):
                        if content_block.get("type") == "text":
                            text = content_block.get("text", "")
                            if text:
                                content += text + "\n" if content else text
                    elif isinstance(content_block, str):
                        content += content_block
                content = content.rstrip("\n")
            elif "text" in result:
                content = result["text"]
            else:
                content = str(result)

            message = AIMessage(content=content)
            generation = ChatGeneration(message=message)
            chat_result = ChatResult(generations=[generation])

            return chat_result

        except httpx.HTTPStatusError as e:
            error_msg = f"Error calling Holistic AI Bedrock API: {e}"
            if e.response:
                try:
                    error_detail = e.response.text
                    error_msg += f"\nResponse: {error_detail}"
                    try:
                        error_json = e.response.json()
                        error_msg += f"\nError details: {json.dumps(error_json, indent=2)}"
                    except:
                        pass
                except:
                    pass
            raise ValueError(error_msg)
        except Exception as e:
            raise ValueError(f"Error calling Holistic AI Bedrock API: {e}")

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGeneration]:
        """Stream not implemented for this proxy."""
        raise NotImplementedError("Streaming not supported by HolisticAI Bedrock Proxy")

    def _astream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGeneration]:
        """Async stream not implemented for this proxy."""
        raise NotImplementedError("Streaming not supported by HolisticAI Bedrock Proxy")
