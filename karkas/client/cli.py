"""KARKAS Command-Line Client with WebSocket real-time updates, history, and map display"""
import asyncio
import json
import math
import sys
import threading
from datetime import datetime
from queue import Queue
from typing import Optional

import httpx
import websockets


class TerminalColors:
    """ANSI color codes for terminal output"""
    RED = "\033[91m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


class TurnResultFormatter:
    """Format turn results for display"""

    @staticmethod
    def format_movements(movements: list[dict], faction: str) -> list[str]:
        """Format movement events"""
        lines = []
        for mv in movements:
            unit = mv.get("unit", "Unknown")
            from_pos = mv.get("from_position", {})
            to_pos = mv.get("to_position", {})
            dist = mv.get("distance_km", 0)
            completed = mv.get("completed", False)

            status = f"{TerminalColors.GREEN}complete{TerminalColors.RESET}" if completed else f"{TerminalColors.YELLOW}in progress{TerminalColors.RESET}"
            lines.append(
                f"  {unit}: ({from_pos.get('latitude', 0):.3f}, {from_pos.get('longitude', 0):.3f}) -> "
                f"({to_pos.get('latitude', 0):.3f}, {to_pos.get('longitude', 0):.3f}) "
                f"[{dist:.1f} km, {status}]"
            )
        return lines

    @staticmethod
    def format_combats(combats: list[dict], faction: str) -> list[str]:
        """Format combat events"""
        lines = []
        for combat in combats:
            attacker = combat.get("attacker", "Unknown")
            defender = combat.get("defender", "Unknown")
            loc = combat.get("location", {})

            atk_cas = combat.get("attacker_casualties", {})
            def_cas = combat.get("defender_casualties", {})

            atk_killed = atk_cas.get("personnel_killed", 0)
            def_killed = def_cas.get("personnel_killed", 0)

            atk_retreat = combat.get("attacker_retreated", False)
            def_retreat = combat.get("defender_retreated", False)

            result = ""
            if def_retreat:
                result = f" {TerminalColors.GREEN}[defender withdrew]{TerminalColors.RESET}"
            elif atk_retreat:
                result = f" {TerminalColors.YELLOW}[attacker withdrew]{TerminalColors.RESET}"

            lines.append(
                f"  {TerminalColors.RED}{attacker}{TerminalColors.RESET} vs "
                f"{TerminalColors.BLUE}{defender}{TerminalColors.RESET} "
                f"at ({loc.get('latitude', 0):.3f}, {loc.get('longitude', 0):.3f})"
            )
            lines.append(
                f"    Casualties: {attacker} lost {atk_killed}, {defender} lost {def_killed}{result}"
            )
        return lines

    @staticmethod
    def format_detections(detections: list[dict], faction: str) -> list[str]:
        """Format detection events"""
        lines = []
        for det in detections:
            observer = det.get("observer", "Unknown")
            observed = det.get("observed", "Unknown")
            loc = det.get("location", {})
            conf = det.get("confidence", "unknown")

            conf_color = {
                "confirmed": TerminalColors.GREEN,
                "probable": TerminalColors.CYAN,
                "suspected": TerminalColors.YELLOW,
                "unknown": TerminalColors.DIM
            }.get(conf, TerminalColors.WHITE)

            lines.append(
                f"  {observer} detected {conf_color}[{conf}]{TerminalColors.RESET} {observed} "
                f"at ({loc.get('latitude', 0):.3f}, {loc.get('longitude', 0):.3f})"
            )
        return lines

    @staticmethod
    def format_turn_result(result: dict, faction: str) -> str:
        """Format a complete turn result for display"""
        lines = [
            "",
            f"{TerminalColors.BOLD}{'=' * 60}{TerminalColors.RESET}",
            f"{TerminalColors.BOLD}TURN {result.get('turn', '?')} RESULTS{TerminalColors.RESET}",
            f"{'=' * 60}",
        ]

        # Movements
        movements = result.get("movements", [])
        if movements:
            lines.append(f"\n{TerminalColors.CYAN}MOVEMENTS ({len(movements)}):{TerminalColors.RESET}")
            lines.extend(TurnResultFormatter.format_movements(movements, faction))

        # Combats
        combats = result.get("combats", [])
        if combats:
            lines.append(f"\n{TerminalColors.RED}ENGAGEMENTS ({len(combats)}):{TerminalColors.RESET}")
            lines.extend(TurnResultFormatter.format_combats(combats, faction))

        # Detections
        detections = result.get("detections", [])
        if detections:
            lines.append(f"\n{TerminalColors.MAGENTA}INTELLIGENCE ({len(detections)}):{TerminalColors.RESET}")
            lines.extend(TurnResultFormatter.format_detections(detections, faction))

        # Summary
        summary_key = f"{faction.lower()}_summary"
        if result.get(summary_key):
            lines.append(f"\n{TerminalColors.BOLD}SUMMARY:{TerminalColors.RESET}")
            lines.append(f"  {result[summary_key]}")

        # Victory check
        if result.get("game_over"):
            winner = result.get("winner", "Unknown")
            reason = result.get("victory_reason", "")
            lines.append("")
            lines.append(f"{TerminalColors.BOLD}*** GAME OVER ***{TerminalColors.RESET}")
            lines.append(f"Winner: {TerminalColors.GREEN}{winner}{TerminalColors.RESET}")
            if reason:
                lines.append(f"Reason: {reason}")

        lines.append(f"{'=' * 60}\n")
        return "\n".join(lines)


class ASCIIMapRenderer:
    """Render ASCII battlefield maps"""

    # Map characters
    EMPTY = "."
    FRIENDLY = "@"
    ENEMY = "X"
    CONTACT_CONFIRMED = "!"
    CONTACT_PROBABLE = "?"
    CONTACT_SUSPECTED = "~"
    BORDER_H = "-"
    BORDER_V = "|"
    CORNER = "+"

    def __init__(self, width: int = 60, height: int = 20):
        self.width = width
        self.height = height

    def render(
        self,
        own_units: list[dict],
        contacts: list[dict],
        bounds: Optional[dict] = None
    ) -> str:
        """Render battlefield map as ASCII

        Args:
            own_units: List of friendly units with position
            contacts: List of enemy contacts with position and confidence
            bounds: Optional bounding box {sw: {lat, lon}, ne: {lat, lon}}

        Returns:
            ASCII map string
        """
        # Calculate bounds if not provided
        if bounds is None:
            bounds = self._calculate_bounds(own_units, contacts)

        if bounds is None:
            return "No units to display on map"

        sw = bounds["sw"]
        ne = bounds["ne"]

        # Add padding
        lat_range = ne["lat"] - sw["lat"]
        lon_range = ne["lon"] - sw["lon"]
        if lat_range == 0:
            lat_range = 0.1
        if lon_range == 0:
            lon_range = 0.1

        padding = 0.1
        sw["lat"] -= lat_range * padding
        sw["lon"] -= lon_range * padding
        ne["lat"] += lat_range * padding
        ne["lon"] += lon_range * padding

        # Recalculate ranges
        lat_range = ne["lat"] - sw["lat"]
        lon_range = ne["lon"] - sw["lon"]

        # Initialize map grid
        grid = [[self.EMPTY for _ in range(self.width)] for _ in range(self.height)]

        # Place contacts first (so friendlies overlay)
        for contact in contacts:
            pos = contact.get("position", contact.get("last_known_position", {}))
            if not pos:
                continue

            x, y = self._coord_to_grid(
                pos.get("latitude", 0),
                pos.get("longitude", 0),
                sw, ne, lat_range, lon_range
            )

            if 0 <= x < self.width and 0 <= y < self.height:
                conf = contact.get("confidence", "unknown")
                if conf == "confirmed":
                    grid[y][x] = self.CONTACT_CONFIRMED
                elif conf == "probable":
                    grid[y][x] = self.CONTACT_PROBABLE
                else:
                    grid[y][x] = self.CONTACT_SUSPECTED

        # Place friendly units
        for unit in own_units:
            pos = unit.get("position", {})
            if not pos:
                continue

            x, y = self._coord_to_grid(
                pos.get("latitude", 0),
                pos.get("longitude", 0),
                sw, ne, lat_range, lon_range
            )

            if 0 <= x < self.width and 0 <= y < self.height:
                grid[y][x] = self.FRIENDLY

        # Build output
        lines = []

        # Header with longitude markers
        lon_markers = f"  {sw['lon']:.2f}"
        lon_markers += " " * (self.width - len(lon_markers) - 6)
        lon_markers += f"{ne['lon']:.2f}"
        lines.append(lon_markers)

        # Top border
        lines.append("  " + self.CORNER + self.BORDER_H * self.width + self.CORNER)

        # Map rows with latitude markers
        for i, row in enumerate(grid):
            lat_marker = ""
            if i == 0:
                lat_marker = f"{ne['lat']:.2f}"
            elif i == self.height - 1:
                lat_marker = f"{sw['lat']:.2f}"

            row_str = "".join(row)
            # Color the row
            colored_row = ""
            for char in row_str:
                if char == self.FRIENDLY:
                    colored_row += f"{TerminalColors.BLUE}{char}{TerminalColors.RESET}"
                elif char in (self.CONTACT_CONFIRMED, self.ENEMY):
                    colored_row += f"{TerminalColors.RED}{char}{TerminalColors.RESET}"
                elif char == self.CONTACT_PROBABLE:
                    colored_row += f"{TerminalColors.YELLOW}{char}{TerminalColors.RESET}"
                elif char == self.CONTACT_SUSPECTED:
                    colored_row += f"{TerminalColors.DIM}{char}{TerminalColors.RESET}"
                else:
                    colored_row += char

            lines.append(f"{lat_marker:>6}{self.BORDER_V}{colored_row}{self.BORDER_V}")

        # Bottom border
        lines.append("  " + self.CORNER + self.BORDER_H * self.width + self.CORNER)

        # Legend
        lines.append("")
        lines.append("Legend:")
        lines.append(f"  {TerminalColors.BLUE}@{TerminalColors.RESET} = Friendly unit  "
                    f"{TerminalColors.RED}!{TerminalColors.RESET} = Confirmed enemy  "
                    f"{TerminalColors.YELLOW}?{TerminalColors.RESET} = Probable enemy  "
                    f"{TerminalColors.DIM}~{TerminalColors.RESET} = Suspected")

        return "\n".join(lines)

    def _coord_to_grid(
        self,
        lat: float,
        lon: float,
        sw: dict,
        ne: dict,
        lat_range: float,
        lon_range: float
    ) -> tuple[int, int]:
        """Convert lat/lon to grid coordinates"""
        x = int((lon - sw["lon"]) / lon_range * (self.width - 1))
        # Y is inverted (higher lat = lower row index)
        y = int((ne["lat"] - lat) / lat_range * (self.height - 1))
        return x, y

    def _calculate_bounds(
        self,
        own_units: list[dict],
        contacts: list[dict]
    ) -> Optional[dict]:
        """Calculate bounding box from units and contacts"""
        all_positions = []

        for unit in own_units:
            pos = unit.get("position", {})
            if pos and "latitude" in pos and "longitude" in pos:
                all_positions.append(pos)

        for contact in contacts:
            pos = contact.get("position", contact.get("last_known_position", {}))
            if pos and "latitude" in pos and "longitude" in pos:
                all_positions.append(pos)

        if not all_positions:
            return None

        lats = [p["latitude"] for p in all_positions]
        lons = [p["longitude"] for p in all_positions]

        return {
            "sw": {"lat": min(lats), "lon": min(lons)},
            "ne": {"lat": max(lats), "lon": max(lons)}
        }


class KarkasClient:
    """Command-line client for KARKAS server with real-time WebSocket updates"""

    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url.rstrip("/")
        self.ws_url = server_url.replace("http", "ws") + "/ws"
        self.http = httpx.AsyncClient(base_url=self.server_url, timeout=30.0)
        self.faction: Optional[str] = None
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.ws_connected = False
        self.ws_task: Optional[asyncio.Task] = None
        self.input_queue: Queue = Queue()
        self.running = True
        self.result_formatter = TurnResultFormatter()
        self.map_renderer = ASCIIMapRenderer()
        # Track pending orders for history display
        self.submitted_orders: list[dict] = []

    async def close(self):
        """Close connections"""
        self.running = False
        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass
        await self.http.aclose()
        if self.ws:
            await self.ws.close()

    async def connect_websocket(self) -> bool:
        """Connect to WebSocket for real-time updates"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.ws_connected = True

            # Wait for connected message
            msg = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            data = json.loads(msg)
            if data.get("type") == "connected":
                print(f"{TerminalColors.GREEN}WebSocket connected - Turn {data.get('turn')}, "
                      f"Phase: {data.get('phase')}{TerminalColors.RESET}")

            # Send subscription
            if self.faction:
                await self.ws.send(json.dumps({
                    "type": "subscribe",
                    "faction": self.faction
                }))
                # Wait for confirmation
                msg = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "subscribed":
                    print(f"{TerminalColors.GREEN}Subscribed to {self.faction} faction updates{TerminalColors.RESET}")

            return True
        except Exception as e:
            print(f"{TerminalColors.YELLOW}WebSocket connection failed: {e}{TerminalColors.RESET}")
            print("Continuing with HTTP-only mode")
            self.ws_connected = False
            return False

    async def websocket_listener(self):
        """Listen for WebSocket messages in background"""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                if not self.running:
                    break

                try:
                    data = json.loads(message)
                    await self._handle_ws_message(data)
                except json.JSONDecodeError:
                    print(f"\n{TerminalColors.YELLOW}Invalid WebSocket message{TerminalColors.RESET}")
                except Exception as e:
                    print(f"\n{TerminalColors.YELLOW}WebSocket handler error: {e}{TerminalColors.RESET}")

                # Re-display prompt
                if self.faction:
                    print(f"\n[{self.faction}]> ", end="", flush=True)

        except websockets.exceptions.ConnectionClosed:
            print(f"\n{TerminalColors.YELLOW}WebSocket connection closed{TerminalColors.RESET}")
            self.ws_connected = False
        except asyncio.CancelledError:
            pass

    async def _handle_ws_message(self, data: dict):
        """Handle incoming WebSocket message"""
        msg_type = data.get("type", "")

        if msg_type == "pong":
            # Heartbeat response - ignore
            pass

        elif msg_type == "phase_change":
            phase = data.get("phase", "?")
            turn = data.get("turn", "?")
            print(f"\n{TerminalColors.CYAN}>>> Phase changed to {phase.upper()} "
                  f"(Turn {turn}){TerminalColors.RESET}")

        elif msg_type == "orders_submitted":
            faction = data.get("faction", "?")
            color = TerminalColors.RED if faction.lower() == "red" else TerminalColors.BLUE
            print(f"\n{color}>>> {faction.upper()} has submitted orders{TerminalColors.RESET}")

        elif msg_type == "turn_result":
            turn = data.get("turn", "?")
            result = data.get("result", {})
            print(self.result_formatter.format_turn_result(result, self.faction or "blue"))

        elif msg_type == "new_turn":
            turn = data.get("turn", "?")
            phase = data.get("phase", "?")
            print(f"\n{TerminalColors.GREEN}>>> NEW TURN {turn} - {phase.upper()} PHASE{TerminalColors.RESET}")

        else:
            # Unknown message type
            print(f"\n{TerminalColors.DIM}[WS] {msg_type}: {json.dumps(data)}{TerminalColors.RESET}")

    async def get_status(self) -> dict:
        """Get server status"""
        response = await self.http.get("/")
        return response.json()

    async def list_scenarios(self) -> list:
        """List available scenarios"""
        response = await self.http.get("/api/scenarios")
        return response.json()["scenarios"]

    async def load_scenario(self, scenario_id: str) -> dict:
        """Load a scenario"""
        response = await self.http.post(f"/api/scenarios/{scenario_id}/load")
        return response.json()

    async def get_game_state(self) -> dict:
        """Get current game state"""
        response = await self.http.get("/api/game/state")
        return response.json()

    async def get_perception(self, faction: str) -> dict:
        """Get perception state for faction"""
        response = await self.http.get(f"/api/perception/{faction}")
        return response.json()

    async def submit_orders(self, faction: str, orders: list) -> dict:
        """Submit orders for a faction"""
        response = await self.http.post(
            f"/api/game/submit-orders/{faction}",
            json={"faction": faction, "orders": orders}
        )
        return response.json()

    async def mark_ready(self, faction: str) -> dict:
        """Mark faction ready for turn execution"""
        response = await self.http.post(f"/api/game/ready/{faction}")
        return response.json()

    async def create_order(self, order_data: dict) -> dict:
        """Create an order"""
        response = await self.http.post("/api/orders", json=order_data)
        return response.json()

    async def parse_natural_language_order(self, text: str, faction: str) -> dict:
        """Parse natural language order"""
        response = await self.http.post(
            "/api/orders/parse-natural-language",
            json={"text": text, "faction": faction}
        )
        return response.json()

    async def get_turn_history(self, start_turn: int = 0, end_turn: Optional[int] = None) -> dict:
        """Get turn history"""
        params = {"start_turn": start_turn}
        if end_turn is not None:
            params["end_turn"] = end_turn
        response = await self.http.get("/api/game/history", params=params)
        return response.json()

    async def get_orders(self) -> list:
        """Get all orders"""
        response = await self.http.get("/api/orders")
        return response.json().get("orders", [])


def input_thread(queue: Queue, running_flag):
    """Thread to read user input without blocking async loop"""
    while running_flag():
        try:
            line = input()
            queue.put(line)
        except EOFError:
            queue.put(None)
            break
        except KeyboardInterrupt:
            queue.put(None)
            break


async def interactive_session(client: KarkasClient, faction: str):
    """Run interactive command session with WebSocket support"""
    print(f"\n{TerminalColors.BOLD}KARKAS Interactive Session - Playing as {faction.upper()}{TerminalColors.RESET}")
    print("=" * 60)
    print("Commands:")
    print("  status    - Show server status")
    print("  state     - Show game state")
    print("  units     - Show your units")
    print("  contacts  - Show enemy contacts")
    print("  map       - Display ASCII battlefield map")
    print("  order     - Issue an order (natural language)")
    print("  orders    - Show submitted orders")
    print("  history   - Show turn history")
    print("  ready     - Mark ready for turn execution")
    print("  help      - Show this help")
    print("  quit      - Exit")
    print("=" * 60)

    client.faction = faction

    # Connect WebSocket
    await client.connect_websocket()

    # Start WebSocket listener if connected
    if client.ws_connected:
        client.ws_task = asyncio.create_task(client.websocket_listener())

    # Start input thread
    input_q = client.input_queue
    running = lambda: client.running
    thread = threading.Thread(target=input_thread, args=(input_q, running), daemon=True)
    thread.start()

    print(f"\n[{faction}]> ", end="", flush=True)

    while client.running:
        try:
            # Check for input with timeout (allows WebSocket messages to be processed)
            await asyncio.sleep(0.1)

            if not input_q.empty():
                cmd = input_q.get()

                if cmd is None:
                    break

                cmd = cmd.strip().lower()

                if not cmd:
                    print(f"[{faction}]> ", end="", flush=True)
                    continue

                if cmd == "quit" or cmd == "exit":
                    break

                elif cmd == "status":
                    status = await client.get_status()
                    print(f"Server: {status['name']} v{status['version']}")
                    print(f"Turn: {status['turn']}, Phase: {status['phase']}")
                    print(f"Scenario: {status.get('active_scenario', 'None')}")
                    ws_status = f"{TerminalColors.GREEN}connected{TerminalColors.RESET}" if client.ws_connected else f"{TerminalColors.YELLOW}disconnected{TerminalColors.RESET}"
                    print(f"WebSocket: {ws_status}")

                elif cmd == "state":
                    state = await client.get_game_state()
                    print(f"Turn: {state['turn']}")
                    print(f"Phase: {state['phase']}")
                    red_ready = f"{TerminalColors.GREEN}Yes{TerminalColors.RESET}" if state['red_ready'] else "No"
                    blue_ready = f"{TerminalColors.GREEN}Yes{TerminalColors.RESET}" if state['blue_ready'] else "No"
                    print(f"Red Ready: {red_ready}")
                    print(f"Blue Ready: {blue_ready}")

                elif cmd == "units":
                    perception = await client.get_perception(faction)
                    units = perception.get("own_units", [])
                    print(f"\n{TerminalColors.BOLD}Own Forces ({len(units)} units):{TerminalColors.RESET}")
                    for unit in units:
                        pos = unit.get("position", {})
                        unit_type = unit.get("type", "?")
                        posture = unit.get("posture", "?")
                        strength = unit.get("strength", {})
                        strength_ratio = strength.get("strength_ratio", 1.0) if isinstance(strength, dict) else 1.0
                        strength_pct = strength_ratio * 100

                        color = TerminalColors.GREEN if strength_pct > 75 else (
                            TerminalColors.YELLOW if strength_pct > 50 else TerminalColors.RED
                        )
                        print(f"  - {unit.get('name', 'Unknown')} ({unit_type}) "
                              f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f}) "
                              f"[{posture}, {color}{strength_pct:.0f}%{TerminalColors.RESET}]")

                elif cmd == "contacts":
                    perception = await client.get_perception(faction)
                    contacts = perception.get("contacts", [])
                    print(f"\n{TerminalColors.BOLD}Enemy Contacts ({len(contacts)} contacts):{TerminalColors.RESET}")
                    if not contacts:
                        print("  No contacts")
                    for contact in contacts:
                        pos = contact.get("position", contact.get("last_known_position", {}))
                        conf = contact.get("confidence", "unknown")
                        conf_color = {
                            "confirmed": TerminalColors.GREEN,
                            "probable": TerminalColors.CYAN,
                            "suspected": TerminalColors.YELLOW,
                            "unknown": TerminalColors.DIM
                        }.get(conf, TerminalColors.WHITE)

                        est_type = contact.get("estimated_type", "unknown")
                        est_echelon = contact.get("estimated_echelon", "")

                        print(f"  - [{conf_color}{conf}{TerminalColors.RESET}] "
                              f"{est_type} {est_echelon} "
                              f"at ({pos.get('latitude', 0):.4f}, {pos.get('longitude', 0):.4f})")

                elif cmd == "map":
                    perception = await client.get_perception(faction)
                    own_units = perception.get("own_units", [])
                    contacts = perception.get("contacts", [])
                    print("\n" + client.map_renderer.render(own_units, contacts))

                elif cmd == "order":
                    print("Enter order (natural language): ", end="", flush=True)
                    # Wait for order input
                    while input_q.empty() and client.running:
                        await asyncio.sleep(0.1)
                    if not client.running:
                        break
                    order_text = input_q.get()

                    if order_text:
                        result = await client.parse_natural_language_order(order_text, faction)
                        print(f"\n{TerminalColors.BOLD}Parsed Order:{TerminalColors.RESET}")
                        print(json.dumps(result, indent=2))

                        parsed = result.get("parsed", {})
                        if parsed.get("needs_clarification"):
                            print(f"\n{TerminalColors.YELLOW}Clarification needed:{TerminalColors.RESET}")
                            for q in parsed.get("questions", []):
                                print(f"  - {q}")
                        else:
                            # Track submitted order
                            client.submitted_orders.append({
                                "turn": (await client.get_game_state()).get("turn", 0),
                                "text": order_text,
                                "parsed": parsed,
                                "timestamp": datetime.now().isoformat()
                            })
                            print(f"{TerminalColors.GREEN}Order recorded{TerminalColors.RESET}")

                elif cmd == "orders":
                    print(f"\n{TerminalColors.BOLD}Submitted Orders (this session):{TerminalColors.RESET}")
                    if not client.submitted_orders:
                        print("  No orders submitted yet")
                    else:
                        for i, order in enumerate(client.submitted_orders, 1):
                            print(f"  {i}. [Turn {order['turn']}] {order['text']}")

                    # Also show pending orders from server
                    try:
                        server_orders = await client.get_orders()
                        active_orders = [o for o in server_orders if o.get("active", True)]
                        if active_orders:
                            print(f"\n{TerminalColors.BOLD}Active Orders (server):{TerminalColors.RESET}")
                            for order in active_orders:
                                target_units = order.get("target_units", [])
                                order_type = order.get("order_type", "?")
                                print(f"  - {order_type.upper()}: {', '.join(target_units)}")
                    except Exception:
                        pass

                elif cmd == "history":
                    history_data = await client.get_turn_history()
                    history = history_data.get("history", [])

                    print(f"\n{TerminalColors.BOLD}Turn History:{TerminalColors.RESET}")
                    if not history:
                        print("  No turns executed yet")
                    else:
                        for turn_record in history:
                            turn_num = turn_record.get("turn", "?")
                            movements = turn_record.get("movements", [])
                            combats = turn_record.get("combats", [])
                            detections = turn_record.get("detections", [])

                            print(f"\n{TerminalColors.CYAN}=== TURN {turn_num} ==={TerminalColors.RESET}")
                            print(f"  Movements: {len(movements)}")
                            print(f"  Engagements: {len(combats)}")
                            print(f"  Detections: {len(detections)}")

                            # Show details if any events
                            if movements:
                                print(f"  {TerminalColors.DIM}Movements:{TerminalColors.RESET}")
                                for mv in movements[:3]:  # Show first 3
                                    print(f"    - {mv.get('unit', '?')}: {mv.get('distance_km', 0):.1f} km")
                                if len(movements) > 3:
                                    print(f"    ... and {len(movements) - 3} more")

                            if combats:
                                print(f"  {TerminalColors.DIM}Engagements:{TerminalColors.RESET}")
                                for combat in combats[:3]:
                                    print(f"    - {combat.get('attacker', '?')} vs {combat.get('defender', '?')}")
                                if len(combats) > 3:
                                    print(f"    ... and {len(combats) - 3} more")

                elif cmd == "ready":
                    result = await client.mark_ready(faction)
                    print(result.get("message", "Marked ready"))
                    if result.get("both_ready"):
                        print(f"{TerminalColors.GREEN}Both sides ready - turn will execute!{TerminalColors.RESET}")

                elif cmd == "help":
                    print("\nCommands:")
                    print("  status   - Server status and WebSocket connection")
                    print("  state    - Current game state (turn, phase, ready status)")
                    print("  units    - List your units with positions and strength")
                    print("  contacts - Show detected enemy contacts")
                    print("  map      - ASCII map of battlefield")
                    print("  order    - Issue a natural language order")
                    print("  orders   - Show submitted orders")
                    print("  history  - Show turn history with events")
                    print("  ready    - Mark ready for turn execution")
                    print("  quit     - Exit client")

                else:
                    print(f"Unknown command: {cmd}. Type 'help' for available commands.")

                print(f"\n[{faction}]> ", end="", flush=True)

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")
            print(f"\n[{faction}]> ", end="", flush=True)


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="KARKAS Command-Line Client")
    parser.add_argument(
        "--server", "-s",
        default="http://localhost:8080",
        help="Server URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--faction", "-f",
        choices=["red", "blue"],
        default="blue",
        help="Faction to play (default: blue)"
    )
    parser.add_argument(
        "--scenario",
        help="Scenario to load on startup"
    )
    parser.add_argument(
        "--no-websocket",
        action="store_true",
        help="Disable WebSocket connection (HTTP-only mode)"
    )

    args = parser.parse_args()

    client = KarkasClient(args.server)

    try:
        # Check server connection
        print(f"Connecting to {args.server}...")
        status = await client.get_status()
        print(f"Connected to {status['name']} v{status['version']}")

        # Load scenario if specified
        if args.scenario:
            print(f"Loading scenario: {args.scenario}")
            await client.load_scenario(args.scenario)

        # Run interactive session
        await interactive_session(client, args.faction)

    except httpx.ConnectError:
        print(f"Error: Cannot connect to server at {args.server}")
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
