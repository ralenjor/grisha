"""Tests for KARKAS API endpoints"""
import pytest
from fastapi.testclient import TestClient

from server.api.main import app


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


class TestRootEndpoints:
    """Test root API endpoints"""

    def test_root(self, client):
        """Test root endpoint returns server info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "KARKAS"
        assert "version" in data

    def test_health(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestUnitEndpoints:
    """Test unit management endpoints"""

    def test_list_units_empty(self, client):
        """Test listing units when empty"""
        response = client.get("/api/units")
        assert response.status_code == 200
        data = response.json()
        assert "units" in data
        assert "count" in data

    def test_create_unit(self, client):
        """Test creating a unit"""
        unit_data = {
            "name": "Test Battalion",
            "faction": "red",
            "type": "mechanized",
            "echelon": "battalion",
            "position": {"latitude": 50.5, "longitude": 9.5},
        }
        response = client.post("/api/units", json=unit_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Battalion"
        assert "id" in data

    def test_get_unit(self, client):
        """Test getting a specific unit"""
        # First create a unit
        unit_data = {
            "id": "test_unit_1",
            "name": "Test Unit",
            "faction": "blue",
            "type": "armor",
            "echelon": "battalion",
            "position": {"latitude": 50.3, "longitude": 9.8},
        }
        client.post("/api/units", json=unit_data)

        # Then get it
        response = client.get("/api/units/test_unit_1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_unit_1"
        assert data["name"] == "Test Unit"

    def test_get_unit_not_found(self, client):
        """Test getting non-existent unit"""
        response = client.get("/api/units/nonexistent")
        assert response.status_code == 404


class TestOrderEndpoints:
    """Test order management endpoints"""

    def test_validate_order(self, client):
        """Test order validation"""
        order_data = {
            "issuer": "hq",
            "target_units": ["unit1"],
            "order_type": "move",
            "objective": {
                "type": "position",
                "coordinates": {"latitude": 50.5, "longitude": 9.5},
            },
        }
        response = client.post("/api/orders/validate", json=order_data)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    def test_validate_invalid_order(self, client):
        """Test validation of invalid order"""
        order_data = {
            "issuer": "hq",
            "target_units": [],  # Empty - invalid
            "order_type": "move",
            "objective": {
                "type": "position",
            },
        }
        response = client.post("/api/orders/validate", json=order_data)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False


class TestGameEndpoints:
    """Test game control endpoints"""

    def test_get_game_state(self, client):
        """Test getting game state"""
        response = client.get("/api/game/state")
        assert response.status_code == 200
        data = response.json()
        assert "turn" in data
        assert "phase" in data

    def test_get_turn(self, client):
        """Test getting current turn"""
        response = client.get("/api/game/turn")
        assert response.status_code == 200
        data = response.json()
        assert "turn" in data
        assert "phase" in data

    def test_mark_ready(self, client):
        """Test marking faction ready"""
        response = client.post("/api/game/ready/red")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_mark_ready_invalid_faction(self, client):
        """Test marking invalid faction ready"""
        response = client.post("/api/game/ready/invalid")
        assert response.status_code == 400

    def test_reset_game(self, client):
        """Test resetting game"""
        response = client.post("/api/game/reset")
        assert response.status_code == 200


class TestScenarioEndpoints:
    """Test scenario management endpoints"""

    def test_list_scenarios(self, client):
        """Test listing scenarios"""
        response = client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) > 0  # Should have default scenarios

    def test_get_scenario(self, client):
        """Test getting specific scenario"""
        response = client.get("/api/scenarios/fulda_gap_1985")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Fulda Gap 1985"

    def test_get_scenario_not_found(self, client):
        """Test getting non-existent scenario"""
        response = client.get("/api/scenarios/nonexistent")
        assert response.status_code == 404

    def test_load_scenario(self, client):
        """Test loading a scenario"""
        response = client.post("/api/scenarios/tutorial/load")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data


class TestPerceptionEndpoint:
    """Test perception state endpoint"""

    def test_get_perception(self, client):
        """Test getting faction perception"""
        response = client.get("/api/perception/red")
        assert response.status_code == 200
        data = response.json()
        assert data["faction"] == "red"
        assert "own_units" in data
        assert "contacts" in data

    def test_get_perception_invalid_faction(self, client):
        """Test getting perception for invalid faction"""
        response = client.get("/api/perception/invalid")
        assert response.status_code == 400


class TestGrishaEndpoints:
    """Test Grisha AI endpoints"""

    def test_grisha_status(self, client):
        """Test getting Grisha status"""
        response = client.get("/api/grisha/status")
        assert response.status_code == 200
        data = response.json()
        assert "red_ai_enabled" in data
        assert "blue_ai_enabled" in data

    def test_enable_grisha(self, client):
        """Test enabling Grisha for faction"""
        response = client.post("/api/grisha/enable/red")
        assert response.status_code == 200

    def test_disable_grisha(self, client):
        """Test disabling Grisha for faction"""
        response = client.post("/api/grisha/disable/red")
        assert response.status_code == 200


class TestWebSocketEndpoint:
    """Test WebSocket real-time communication"""

    def test_websocket_connect(self, client):
        """Test WebSocket connection establishment"""
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert "turn" in data
            assert "phase" in data

    def test_websocket_ping_pong(self, client):
        """Test WebSocket heartbeat ping/pong"""
        with client.websocket_connect("/ws") as websocket:
            # Consume initial connected message
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "ping"})

            # Receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_websocket_subscribe_faction(self, client):
        """Test subscribing to faction updates"""
        with client.websocket_connect("/ws") as websocket:
            # Consume initial connected message
            websocket.receive_json()

            # Subscribe to red faction
            websocket.send_json({"type": "subscribe", "faction": "red"})

            # Receive subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert data["faction"] == "red"

    def test_websocket_subscribe_blue_faction(self, client):
        """Test subscribing to blue faction updates"""
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()  # connected

            websocket.send_json({"type": "subscribe", "faction": "blue"})

            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert data["faction"] == "blue"

    def test_websocket_multiple_pings(self, client):
        """Test multiple consecutive ping/pong exchanges"""
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()  # connected

            for _ in range(3):
                websocket.send_json({"type": "ping"})
                data = websocket.receive_json()
                assert data["type"] == "pong"

    def test_websocket_unknown_message_type(self, client):
        """Test sending unknown message type doesn't crash connection"""
        with client.websocket_connect("/ws") as websocket:
            websocket.receive_json()  # connected

            # Send unknown message type
            websocket.send_json({"type": "unknown_type", "data": "test"})

            # Connection should still work - send ping to verify
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_websocket_initial_state_values(self, client):
        """Test that initial connected message has valid state"""
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert isinstance(data["turn"], int)
            assert data["turn"] >= 0
            assert data["phase"] in ["planning", "execution", "reporting"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
