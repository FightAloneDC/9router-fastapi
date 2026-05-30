"""Shared router instance for provider endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["providers"])
