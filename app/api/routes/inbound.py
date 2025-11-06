from fastapi import APIRouter, Depends, status

from app.api.deps import get_orchestrator
from app.schemas.inbound import ChatbotMessage
from app.schemas.questions import QuestionRequest, QuestionResponse
from app.schemas.responses import AgentReply
from app.services.orchestrator import LLMOrchestrator

router = APIRouter()


@router.post(
    "/turn",
    status_code=status.HTTP_200_OK,
    response_model=AgentReply,
    summary="Process a user message forwarded by the chatbot backend",
)
async def process_turn(
    payload: ChatbotMessage,
    orchestrator: LLMOrchestrator = Depends(get_orchestrator),
) -> AgentReply:
    """
    Primary ingress for the legacy chatbot.

    The chatbot posts user messages to this endpoint. The orchestrator evaluates
    the intent, interacts with external tools if needed, and returns
    a structured AgentReply that the chatbot can render.
    """
    return await orchestrator.handle_turn(payload)


@router.post(
    "/direct-answer",
    status_code=status.HTTP_200_OK,
    response_model=QuestionResponse,
    summary="Call the LLM directly with a plain question.",
)
async def direct_answer(
    request: QuestionRequest,
    orchestrator: LLMOrchestrator = Depends(get_orchestrator),
) -> QuestionResponse:
    """
    Convenience endpoint for services that only need a question → answer interaction.
    """
    result = await orchestrator.answer_direct(
        question=request.question, language=request.language
    )
    return QuestionResponse(**result)
