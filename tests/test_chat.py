"""Tests du chat agent et de la route /chat."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from sub_agents.chat_agent.agent import ChatAgent


client = TestClient(app)


def test_chat_agent_returns_response():
    agent = ChatAgent()
    result = agent.run("hello")
    assert "chat_response" in result
    assert isinstance(result["chat_response"], str)
    assert result["chat_response"]


def test_chat_agent_with_history():
    agent = ChatAgent()
    result = agent.run(
        "what can you do?",
        history=[{"role": "user", "content": "hi"}],
    )
    assert "chat_response" in result
    assert isinstance(result["chat_response"], str)


def test_chat_endpoint():
    with patch(
        "sub_agents.chat_agent.agent.ChatAgent.run",
        return_value={"chat_response": "I am here to help!"},
    ):
        response = client.post("/chat/", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["chat_response"] == "I am here to help!"


def test_chat_endpoint_with_history():
    with patch(
        "sub_agents.chat_agent.agent.ChatAgent.run",
        return_value={"chat_response": "You asked about CCU."},
    ):
        response = client.post(
            "/chat/",
            json={
                "message": "tell me more",
                "history": [{"role": "user", "content": "hello"}],
            },
        )
    assert response.status_code == 200
    assert response.json()["chat_response"] == "You asked about CCU."


def test_chat_endpoint_returns_retrieval_info():
    fake_result = {
        "chat_response": "Customer acc-12345 has an active subscription.",
        "retrieval_used": True,
        "retrieved_context": {
            "parsed": {"customer_id": "acc-12345", "service_id": "svc-fiber-12345"},
            "logs": {"summary": "1 log found"},
        },
    }
    with patch(
        "sub_agents.chat_agent.agent.ChatAgent.run",
        return_value=fake_result,
    ):
        response = client.post("/chat/", json={"message": "what about acc-12345?"})
    data = response.json()
    assert response.status_code == 200
    assert data["chat_response"] == "Customer acc-12345 has an active subscription."
    assert data["retrieval_used"] is True
    assert data["retrieved_context"]["parsed"]["customer_id"] == "acc-12345"
