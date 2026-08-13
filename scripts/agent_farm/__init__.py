"""Modular agent farm tester for 9Router custom OpenAI providers.

Add/edit one file under ``agents/`` per CLI. Runner stays generic.
"""

from .registry import list_agents, get_agent

__all__ = ["list_agents", "get_agent"]
