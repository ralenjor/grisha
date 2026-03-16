"""
Database Persistence API Routes

Provides REST endpoints for:
- Game save/load operations
- Turn history retrieval
- Replay control
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.database import (
    get_session,
    DatabaseSession,
    GameStore,
    TurnHistoryStore,
    ReplayController,
)
from server.api.models.game import (
    GameState,
    TurnResult,
    ScenarioConfig,
)
from server.api.models.units import Faction


router = APIRouter(prefix="/api/persistence", tags=["persistence"])


# =============================================================================
# PYDANTIC MODELS FOR API
# =============================================================================


class GameListItem(BaseModel):
    """Summary of a saved game"""
    game_id: str
    scenario_name: str
    turn: int
    phase: str
    game_over: bool
    winner: Optional[str] = None
    created_at: str
    updated_at: str


class GameListResponse(BaseModel):
    """Response for game list"""
    games: list[GameListItem]
    count: int


class CreateGameRequest(BaseModel):
    """Request to create a new game"""
    scenario: ScenarioConfig
    game_id: Optional[str] = None


class CreateGameResponse(BaseModel):
    """Response for game creation"""
    game_id: str
    message: str


class SaveStateRequest(BaseModel):
    """Request to save game state"""
    game_state: GameState
    # Note: Full state save would include units, orders, contacts
    # This is a simplified version


class TurnHistoryResponse(BaseModel):
    """Response for turn history"""
    game_id: str
    turns: list[TurnResult]
    count: int


class ReplayStateResponse(BaseModel):
    """Response for replay state"""
    game_id: str
    current_turn: int
    max_turn: int
    is_at_start: bool
    is_at_end: bool
    turn_result: Optional[TurnResult] = None


class GameStatisticsResponse(BaseModel):
    """Response for game statistics"""
    game_id: str
    total_turns: int
    total_combats: int
    total_movements: int
    total_detections: int
    total_personnel_killed: int
    total_equipment_destroyed: int
    game_over: bool
    winner: Optional[str] = None


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


def get_game_store(session: Session = Depends(DatabaseSession())) -> GameStore:
    """Get GameStore instance"""
    store = GameStore(session)
    return store


def get_turn_history(
    game_store: GameStore = Depends(get_game_store),
) -> TurnHistoryStore:
    """Get TurnHistoryStore instance"""
    return TurnHistoryStore(game_store)


def get_replay_controller(
    game_store: GameStore = Depends(get_game_store),
    turn_history: TurnHistoryStore = Depends(get_turn_history),
) -> ReplayController:
    """Get ReplayController instance"""
    return ReplayController(game_store, turn_history)


# =============================================================================
# GAME MANAGEMENT ENDPOINTS
# =============================================================================


@router.get("/games", response_model=GameListResponse)
async def list_games(
    include_completed: bool = Query(True, description="Include completed games"),
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """List all saved games"""
    games = game_store.list_games(include_completed, session)
    return GameListResponse(
        games=[GameListItem(**g) for g in games],
        count=len(games),
    )


@router.post("/games", response_model=CreateGameResponse, status_code=201)
async def create_game(
    request: CreateGameRequest,
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """Create a new game from scenario"""
    try:
        game_id = game_store.create_game(
            request.scenario,
            request.game_id,
            session,
        )
        return CreateGameResponse(
            game_id=game_id,
            message=f"Game created: {game_id}",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/games/{game_id}")
async def get_game(
    game_id: str,
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """Get game details"""
    state = game_store.load_full_state(game_id, session)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return state


@router.delete("/games/{game_id}")
async def delete_game(
    game_id: str,
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """Delete a game"""
    success = game_store.delete_game(game_id, session)
    if not success:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return {"message": f"Game deleted: {game_id}"}


@router.get("/games/{game_id}/state", response_model=GameState)
async def get_game_state(
    game_id: str,
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """Get current game state"""
    state = game_store.load_game_state(game_id, session)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return state


@router.put("/games/{game_id}/state")
async def save_game_state(
    game_id: str,
    request: SaveStateRequest,
    game_store: GameStore = Depends(get_game_store),
    session: Session = Depends(DatabaseSession()),
):
    """Save game state"""
    try:
        game_store.save_game_state(game_id, request.game_state, session)
        return {"message": "State saved"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# TURN HISTORY ENDPOINTS
# =============================================================================


@router.get("/games/{game_id}/history", response_model=TurnHistoryResponse)
async def get_turn_history_endpoint(
    game_id: str,
    turn_history: TurnHistoryStore = Depends(get_turn_history),
    session: Session = Depends(DatabaseSession()),
):
    """Get all turn results for a game"""
    results = turn_history.get_all_turn_results(game_id, session)
    return TurnHistoryResponse(
        game_id=game_id,
        turns=results,
        count=len(results),
    )


@router.get("/games/{game_id}/history/{turn}", response_model=TurnResult)
async def get_turn_result(
    game_id: str,
    turn: int,
    turn_history: TurnHistoryStore = Depends(get_turn_history),
    session: Session = Depends(DatabaseSession()),
):
    """Get result for a specific turn"""
    result = turn_history.get_turn_result(game_id, turn, session)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Turn result not found: turn {turn}")
    return result


@router.get("/games/{game_id}/statistics", response_model=GameStatisticsResponse)
async def get_game_statistics(
    game_id: str,
    turn_history: TurnHistoryStore = Depends(get_turn_history),
    session: Session = Depends(DatabaseSession()),
):
    """Get aggregate statistics for a game"""
    stats = turn_history.get_game_statistics(game_id, session)
    if not stats:
        raise HTTPException(status_code=404, detail=f"Game not found: {game_id}")
    return GameStatisticsResponse(**stats)


@router.get("/games/{game_id}/units/{unit_id}/history")
async def get_unit_history(
    game_id: str,
    unit_id: str,
    turn_history: TurnHistoryStore = Depends(get_turn_history),
    session: Session = Depends(DatabaseSession()),
):
    """Get history for a specific unit"""
    history = turn_history.get_unit_history(game_id, unit_id, session)
    return history


# =============================================================================
# REPLAY ENDPOINTS
# =============================================================================


@router.post("/games/{game_id}/replay/start", response_model=ReplayStateResponse)
async def start_replay(
    game_id: str,
    start_turn: int = Query(0, ge=0, description="Starting turn"),
    replay: ReplayController = Depends(get_replay_controller),
    session: Session = Depends(DatabaseSession()),
):
    """Start a replay session"""
    try:
        state = replay.start_replay(game_id, start_turn, session)
        return ReplayStateResponse(
            game_id=state.game_id,
            current_turn=state.current_turn,
            max_turn=state.max_turn,
            is_at_start=state.is_at_start,
            is_at_end=state.is_at_end,
            turn_result=state.turn_result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/games/{game_id}/replay/forward", response_model=ReplayStateResponse)
async def replay_forward(
    game_id: str,
    replay: ReplayController = Depends(get_replay_controller),
    session: Session = Depends(DatabaseSession()),
):
    """Step forward one turn in replay"""
    try:
        # Start replay if not active
        if not replay.is_active() or replay._current_game_id != game_id:
            replay.start_replay(game_id, session=session)

        state = replay.step_forward(session)
        return ReplayStateResponse(
            game_id=state.game_id,
            current_turn=state.current_turn,
            max_turn=state.max_turn,
            is_at_start=state.is_at_start,
            is_at_end=state.is_at_end,
            turn_result=state.turn_result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/games/{game_id}/replay/backward", response_model=ReplayStateResponse)
async def replay_backward(
    game_id: str,
    replay: ReplayController = Depends(get_replay_controller),
    session: Session = Depends(DatabaseSession()),
):
    """Step backward one turn in replay"""
    try:
        if not replay.is_active() or replay._current_game_id != game_id:
            replay.start_replay(game_id, session=session)

        state = replay.step_backward(session)
        return ReplayStateResponse(
            game_id=state.game_id,
            current_turn=state.current_turn,
            max_turn=state.max_turn,
            is_at_start=state.is_at_start,
            is_at_end=state.is_at_end,
            turn_result=state.turn_result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/games/{game_id}/replay/jump", response_model=ReplayStateResponse)
async def replay_jump(
    game_id: str,
    turn: int = Query(..., ge=0, description="Target turn"),
    replay: ReplayController = Depends(get_replay_controller),
    session: Session = Depends(DatabaseSession()),
):
    """Jump to a specific turn in replay"""
    try:
        if not replay.is_active() or replay._current_game_id != game_id:
            replay.start_replay(game_id, session=session)

        state = replay.jump_to_turn(turn, session)
        return ReplayStateResponse(
            game_id=state.game_id,
            current_turn=state.current_turn,
            max_turn=state.max_turn,
            is_at_start=state.is_at_start,
            is_at_end=state.is_at_end,
            turn_result=state.turn_result,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/games/{game_id}/replay/export")
async def export_replay(
    game_id: str,
    replay: ReplayController = Depends(get_replay_controller),
    session: Session = Depends(DatabaseSession()),
):
    """Export complete replay data"""
    try:
        if not replay.is_active() or replay._current_game_id != game_id:
            replay.start_replay(game_id, session=session)

        return replay.export_replay(session)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
