"""KARKAS Server - Main FastAPI Application"""
import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Unit, UnitCreate, UnitUpdate,
    Order, OrderCreate, OrderBatch,
    GameState, TurnResult, PerceptionState, ScenarioConfig,
    Faction, TurnPhase,
)
from .routes import units, orders, game, scenarios, persistence

from server.logging_config import (
    setup_logging, get_logger, RequestLoggingMiddleware,
    log_turn_execution, log_order_submission, LOGGER_API
)

# Initialize logging
logger = get_logger(LOGGER_API)


# Simulation state (in production, this would be more sophisticated)
class SimulationManager:
    """Manages simulation state and connected clients"""

    def __init__(self):
        self.active_scenario: Optional[str] = None
        self.turn: int = 0
        self.phase: TurnPhase = TurnPhase.PLANNING

        self.units: dict[str, dict] = {}
        self.pending_orders: dict[str, list[dict]] = {"red": [], "blue": []}
        self.orders_submitted: dict[str, bool] = {"red": False, "blue": False}

        self.websocket_clients: list[WebSocket] = []

        # Grisha AI instances
        self.red_ai_enabled: bool = False
        self.blue_ai_enabled: bool = False

    async def broadcast(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        for client in self.websocket_clients:
            try:
                await client.send_json(message)
            except Exception:
                pass

    def reset(self):
        """Reset simulation state"""
        self.turn = 0
        self.phase = TurnPhase.PLANNING
        self.units.clear()
        self.pending_orders = {"red": [], "blue": []}
        self.orders_submitted = {"red": False, "blue": False}


sim = SimulationManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Initialize logging first
    setup_logging()
    logger.info("KARKAS Server starting...")

    # Initialize database if enabled
    if os.getenv("KARKAS_DB_ENABLED", "").lower() in ("true", "1", "yes"):
        try:
            from server.database import init_database
            logger.info("Initializing database...")
            init_database(create_tables=True)
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}", exc_info=True)
            logger.warning("Running without database persistence")

    yield

    # Shutdown
    logger.info("KARKAS Server shutting down...")
    for ws in sim.websocket_clients:
        try:
            await ws.close()
        except Exception as e:
            logger.debug(f"Error closing WebSocket: {e}")

    # Close database connections
    if os.getenv("KARKAS_DB_ENABLED", "").lower() in ("true", "1", "yes"):
        try:
            from server.database import close_database
            close_database()
            logger.info("Database connections closed")
        except Exception as e:
            logger.warning(f"Error closing database: {e}")


app = FastAPI(
    title="KARKAS",
    description="Theater-Level Military Simulation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Request logging middleware (must be added before CORS)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware for client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(units.router, prefix="/api/units", tags=["Units"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(game.router, prefix="/api/game", tags=["Game"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["Scenarios"])

# Include persistence router if database is enabled
if os.getenv("KARKAS_DB_ENABLED", "").lower() in ("true", "1", "yes"):
    app.include_router(persistence.router)


@app.get("/")
async def root():
    """Root endpoint - server info"""
    return {
        "name": "KARKAS",
        "version": "0.1.0",
        "description": "Theater-Level Military Simulation Platform",
        "status": "running",
        "active_scenario": sim.active_scenario,
        "turn": sim.turn,
        "phase": sim.phase.value,
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    client_id = str(uuid.uuid4())[:8]
    await websocket.accept()
    sim.websocket_clients.append(websocket)
    logger.info(f"WebSocket client connected: {client_id}")

    try:
        # Send current state on connect
        await websocket.send_json({
            "type": "connected",
            "turn": sim.turn,
            "phase": sim.phase.value,
        })

        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "subscribe":
                # Client subscribing to faction updates
                faction = data.get("faction")
                logger.debug(f"WebSocket client {client_id} subscribed to {faction}")
                await websocket.send_json({
                    "type": "subscribed",
                    "faction": faction,
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
        if websocket in sim.websocket_clients:
            sim.websocket_clients.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
        if websocket in sim.websocket_clients:
            sim.websocket_clients.remove(websocket)


@app.post("/api/game/submit-orders/{faction}")
async def submit_orders(faction: str, batch: OrderBatch):
    """Submit orders for a faction"""
    if faction not in ["red", "blue"]:
        logger.warning(f"Invalid faction in order submission: {faction}")
        raise HTTPException(400, "Invalid faction")

    if sim.phase != TurnPhase.PLANNING:
        logger.warning(f"Order submission rejected: not in planning phase (current: {sim.phase})")
        raise HTTPException(400, "Not in planning phase")

    if sim.orders_submitted[faction]:
        logger.warning(f"Order submission rejected: {faction} already submitted")
        raise HTTPException(400, "Orders already submitted")

    # Store orders
    sim.pending_orders[faction] = [order.model_dump() for order in batch.orders]
    sim.orders_submitted[faction] = True

    # Log the submission
    unit_ids = [order.unit_id for order in batch.orders]
    log_order_submission(faction, len(batch.orders), unit_ids)

    # Broadcast update
    await sim.broadcast({
        "type": "orders_submitted",
        "faction": faction,
    })

    # Check if both sides ready
    if sim.orders_submitted["red"] and sim.orders_submitted["blue"]:
        # Execute turn
        logger.info(f"Both factions ready, executing turn {sim.turn}")
        result = await execute_turn()
        return {"message": "Orders submitted, turn executed", "result": result}

    logger.debug(f"Faction {faction} submitted orders, waiting for opponent")
    return {"message": "Orders submitted, waiting for opponent"}


async def execute_turn() -> dict:
    """Execute a game turn"""
    import time
    start_time = time.perf_counter()

    logger.info(f"Turn {sim.turn} execution started")
    sim.phase = TurnPhase.EXECUTION

    await sim.broadcast({
        "type": "phase_change",
        "phase": "execution",
        "turn": sim.turn,
    })

    # Simulate execution (in production, this calls the C++ core)
    await asyncio.sleep(0.5)  # Simulate processing

    # Generate results
    result = {
        "turn": sim.turn,
        "movements": [],
        "combats": [],
        "detections": [],
        "red_summary": f"Turn {sim.turn} completed. Awaiting orders.",
        "blue_summary": f"Turn {sim.turn} completed. Awaiting orders.",
        "game_over": False,
    }

    sim.phase = TurnPhase.REPORTING

    await sim.broadcast({
        "type": "turn_result",
        "turn": sim.turn,
        "result": result,
    })

    # Log turn execution metrics
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    log_turn_execution(
        turn_number=sim.turn,
        phase="execution",
        duration_ms=elapsed_ms,
        events={
            "movements": len(result["movements"]),
            "combats": len(result["combats"]),
            "detections": len(result["detections"]),
        }
    )

    # Advance turn
    sim.turn += 1
    sim.phase = TurnPhase.PLANNING
    sim.orders_submitted = {"red": False, "blue": False}
    sim.pending_orders = {"red": [], "blue": []}

    await sim.broadcast({
        "type": "new_turn",
        "turn": sim.turn,
        "phase": "planning",
    })

    logger.info(f"Turn {sim.turn - 1} completed, advancing to turn {sim.turn}")
    return result


@app.get("/api/perception/{faction}")
async def get_perception(faction: str) -> dict:
    """Get perception state for a faction"""
    if faction not in ["red", "blue"]:
        raise HTTPException(400, "Invalid faction")

    # Build perception state from units
    own_units = [
        unit for unit in sim.units.values()
        if unit.get("faction") == faction
    ]

    # Simplified contact detection
    enemy_faction = "blue" if faction == "red" else "red"
    contacts = []

    for unit in sim.units.values():
        if unit.get("faction") == enemy_faction:
            # Simplified: all enemy units are detected
            contacts.append({
                "contact_id": unit["id"] + "_contact",
                "position": unit["position"],
                "last_known_position": unit["position"],
                "last_observed": datetime.now().isoformat(),
                "confidence": "probable",
                "estimated_type": unit.get("type"),
                "estimated_echelon": unit.get("echelon"),
                "faction": enemy_faction,
                "source": "reconnaissance",
            })

    return {
        "faction": faction,
        "own_units": own_units,
        "contacts": contacts,
        "control_zones": [],
    }


@app.get("/api/grisha/status")
async def grisha_status():
    """Get Grisha AI status"""
    return {
        "red_ai_enabled": sim.red_ai_enabled,
        "blue_ai_enabled": sim.blue_ai_enabled,
    }


@app.post("/api/grisha/enable/{faction}")
async def enable_grisha(faction: str):
    """Enable Grisha AI for a faction"""
    if faction not in ["red", "blue"]:
        logger.warning(f"Invalid faction for Grisha enable: {faction}")
        raise HTTPException(400, "Invalid faction")

    if faction == "red":
        sim.red_ai_enabled = True
    else:
        sim.blue_ai_enabled = True

    logger.info(f"Grisha AI enabled for {faction}")
    return {"message": f"Grisha AI enabled for {faction}"}


@app.post("/api/grisha/disable/{faction}")
async def disable_grisha(faction: str):
    """Disable Grisha AI for a faction"""
    if faction not in ["red", "blue"]:
        logger.warning(f"Invalid faction for Grisha disable: {faction}")
        raise HTTPException(400, "Invalid faction")

    if faction == "red":
        sim.red_ai_enabled = False
    else:
        sim.blue_ai_enabled = False

    logger.info(f"Grisha AI disabled for {faction}")
    return {"message": f"Grisha AI disabled for {faction}"}


def main():
    """Entry point for running the server"""
    import uvicorn

    # Get configuration from environment
    host = os.getenv("KARKAS_HOST", "0.0.0.0")
    port = int(os.getenv("KARKAS_PORT", "8080"))
    log_level = os.getenv("KARKAS_LOG_LEVEL", "info").lower()

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
