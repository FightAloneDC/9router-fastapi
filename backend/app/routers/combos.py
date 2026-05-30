"""Combo management endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.combo import Combo
from app.routers.auth import get_current_user
from app.schemas.combo import ComboCreate, ComboOut, ComboUpdate

router = APIRouter(tags=["combos"])


def _combo_to_out(combo: Combo) -> dict:
    """Convert a Combo model to ComboOut dict, parsing the JSON models field."""
    parsed_models: list[str] = []
    try:
        parsed_models = json.loads(combo.models) if combo.models else []
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "id": combo.id,
        "name": combo.name,
        "kind": combo.kind,
        "models": parsed_models,
        "created_at": combo.created_at,
        "updated_at": combo.updated_at,
    }


@router.get("/combos", response_model=list[ComboOut])
async def list_combos(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """List all combos ordered by name."""
    result = await db.execute(select(Combo).order_by(Combo.name))
    combos = result.scalars().all()
    return [_combo_to_out(c) for c in combos]


@router.post(
    "/combos",
    response_model=ComboOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_combo(
    body: ComboCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Create a new combo. Name must be unique."""
    # Check uniqueness
    existing = await db.execute(select(Combo).where(Combo.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Combo with name '{body.name}' already exists",
        )

    combo = Combo(
        name=body.name,
        kind=body.kind,
        models=json.dumps(body.models),
    )
    db.add(combo)
    await db.flush()
    await db.refresh(combo)
    return _combo_to_out(combo)


@router.get("/combos/{combo_id}", response_model=ComboOut)
async def get_combo(
    combo_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Get a single combo by ID."""
    result = await db.execute(select(Combo).where(Combo.id == combo_id))
    combo = result.scalar_one_or_none()
    if combo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combo not found",
        )
    return _combo_to_out(combo)


@router.put("/combos/{combo_id}", response_model=ComboOut)
async def update_combo(
    combo_id: str,
    body: ComboUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Update a combo (name, models, kind). Validates name uniqueness if changed."""
    result = await db.execute(select(Combo).where(Combo.id == combo_id))
    combo = result.scalar_one_or_none()
    if combo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combo not found",
        )

    update_data = body.model_dump(exclude_unset=True)

    # Validate name uniqueness if name is being changed
    if "name" in update_data and update_data["name"] != combo.name:
        dup = await db.execute(
            select(Combo).where(Combo.name == update_data["name"])
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Combo with name '{update_data['name']}' already exists",
            )

    # Serialize models list to JSON if provided
    if "models" in update_data:
        update_data["models"] = json.dumps(update_data["models"])

    for field, value in update_data.items():
        setattr(combo, field, value)

    await db.flush()
    await db.refresh(combo)
    return _combo_to_out(combo)


@router.delete("/combos/{combo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_combo(
    combo_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Delete a combo."""
    result = await db.execute(select(Combo).where(Combo.id == combo_id))
    combo = result.scalar_one_or_none()
    if combo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Combo not found",
        )
    await db.delete(combo)
