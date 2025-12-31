import asyncio
import logging
from typing import TypeVar
from datetime import datetime, timezone
from agent_framework import ChatAgent

from backend.members.council_member import CouncilMember, TextResponse

T = TypeVar('T')
logger = logging.getLogger(__name__)


class AgentMember(CouncilMember):

    def __init__(self, name: str, agent: ChatAgent) -> None:
        self.name = name
        self.last_response_time = None
        self._agent = agent
        self._thread = None
        self._is_closed = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure cleanup."""
        await self.cleanup()
        return False
    
    async def cleanup(self) -> None:
        """Clean up Azure Foundry agent resources."""
        if self._is_closed:
            return
        
        logger.info("Cleaning up agent member %s", self.name)
    

    async def think_and_respond(self, context: str) -> TextResponse:
        if self._is_closed:
            logger.warning("Attempt to use closed agent member %s", self.name)
            return None
        
        if self._thread is None:
            self._thread = self._agent.get_new_thread()

        result = None
        try:
            result = await self._agent.run(
                context,
                thread=self._thread,
                response_format=TextResponse,
            )
        except asyncio.CancelledError:
            logger.info("think_and_respond cancelled for member %s", self.name) 
            raise
        except Exception as e:
            logger.exception("Error in think_and_respond for member %s. %s", self.name, e)
            raise

        if result is not None:
            self.last_response_time = datetime.now(timezone.utc)
            if isinstance(result.value, TextResponse):
                return result.value
            else:
                logger.error(
                    "Error in think_and_respond for member %s: result is not of type Response. Result: %s",
                    self.name,
                    result.value
                )
        return None
    
    async def think(self, context: str, response_type: T) -> T | None:
        if self._is_closed:
            logger.warning("Attempt to use closed agent member %s", self.name)
            return None
        
        if self._thread is None:
            self._thread = self._agent.get_new_thread()

        result = None
        try:
            result = await self._agent.run(
                context,
                thread=self._thread,
                response_format=response_type,
            )
        except asyncio.CancelledError:
            logger.info("think cancelled for member %s", self.name) 
            raise
        except Exception as e:
            logger.exception("Error in think for member %s. %s", self.name, e)
            raise

        if result is not None:
            self.last_response_time = datetime.now(timezone.utc)
            if isinstance(result.value, response_type):
                return result.value
            else:
                logger.error(
                    "Error in think for member %s: result is not of type %s. Result: %s",
                    self.name,
                    response_type.__name__,
                    result.value
                )

        return None