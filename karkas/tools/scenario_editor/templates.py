"""Scenario templates for quick scenario creation."""

from datetime import datetime
from typing import Any

# Predefined regions for common scenarios
PREDEFINED_REGIONS: dict[str, dict[str, Any]] = {
    "fulda_gap": {
        "name": "Fulda Gap",
        "description": "Classic Cold War flashpoint in central Germany",
        "bounds": {
            "southwest": [50.0, 9.0],
            "northeast": [51.0, 10.5]
        },
        "terrain_source": "fulda_gap.gpkg"
    },
    "suwalki_gap": {
        "name": "Suwalki Gap",
        "description": "NATO-Russia strategic corridor between Poland and Lithuania",
        "bounds": {
            "southwest": [53.8, 22.5],
            "northeast": [54.8, 24.0]
        },
        "terrain_source": "suwalki_gap.gpkg"
    },
    "north_german_plain": {
        "name": "North German Plain",
        "description": "Tank country - classic armor engagement area",
        "bounds": {
            "southwest": [51.5, 9.0],
            "northeast": [53.0, 12.0]
        },
        "terrain_source": "north_german_plain.gpkg"
    },
    "korean_dmz": {
        "name": "Korean DMZ",
        "description": "Demilitarized zone between North and South Korea",
        "bounds": {
            "southwest": [37.8, 126.5],
            "northeast": [38.5, 127.5]
        },
        "terrain_source": "korean_dmz.gpkg"
    },
    "baltics": {
        "name": "Baltic States",
        "description": "Estonia, Latvia, Lithuania defense scenario",
        "bounds": {
            "southwest": [55.5, 21.0],
            "northeast": [59.5, 28.0]
        },
        "terrain_source": "baltics.gpkg"
    }
}


def get_blank_scenario_template() -> dict[str, Any]:
    """Return a minimal blank scenario template."""
    return {
        "scenario": {
            "name": "New Scenario",
            "description": "Enter scenario description here."
        },
        "region": {
            "bounds": {
                "southwest": [50.0, 9.0],
                "northeast": [51.0, 10.0]
            },
            "terrain_source": "terrain.gpkg"
        },
        "factions": {
            "red": {
                "name": "Red Force",
                "doctrine": "",
                "orbat_file": "red_orbat.yaml",
                "ai_controlled": True,
                "grisha_persona": "commander"
            },
            "blue": {
                "name": "Blue Force",
                "doctrine": "",
                "orbat_file": "blue_orbat.yaml",
                "ai_controlled": False,
                "grisha_persona": "advisor"
            }
        },
        "initial_conditions": {
            "turn_length_hours": 4,
            "start_date": datetime.now().replace(
                hour=6, minute=0, second=0, microsecond=0
            ).isoformat(),
            "weather": {
                "precipitation": "none",
                "visibility": "clear",
                "temperature_c": 20,
                "wind_speed_kph": 10,
                "wind_direction": 270
            }
        },
        "objectives": [],
        "victory_conditions": [],
        "special_rules": [],
        "briefing": {
            "red": "Enter Red force briefing here.",
            "blue": "Enter Blue force briefing here."
        }
    }


def get_cold_war_offensive_template() -> dict[str, Any]:
    """Return a Cold War Warsaw Pact offensive template."""
    return {
        "scenario": {
            "name": "Cold War Offensive",
            "description": "Warsaw Pact offensive against NATO defensive positions."
        },
        "region": {
            "bounds": {
                "southwest": [50.0, 9.0],
                "northeast": [51.0, 10.5]
            },
            "terrain_source": "fulda_gap.gpkg"
        },
        "factions": {
            "red": {
                "name": "Warsaw Pact",
                "doctrine": "soviet_offensive_1985",
                "orbat_file": "wp_orbat.yaml",
                "ai_controlled": True,
                "grisha_persona": "commander"
            },
            "blue": {
                "name": "NATO",
                "doctrine": "nato_forward_defense_1985",
                "orbat_file": "nato_orbat.yaml",
                "ai_controlled": False,
                "grisha_persona": "advisor"
            }
        },
        "initial_conditions": {
            "turn_length_hours": 4,
            "start_date": "1985-08-15T04:00:00",
            "weather": {
                "precipitation": "none",
                "visibility": "haze",
                "temperature_c": 18,
                "wind_speed_kph": 15,
                "wind_direction": 270
            }
        },
        "objectives": [
            {
                "name": "primary_objective",
                "type": "city",
                "coordinates": [50.5, 9.5],
                "points": 100,
                "controller": "blue"
            },
            {
                "name": "secondary_objective",
                "type": "crossroads",
                "coordinates": [50.7, 9.8],
                "points": 30,
                "controller": "blue"
            }
        ],
        "victory_conditions": [
            {
                "type": "territorial",
                "description": "Red captures primary objective",
                "zones": ["primary_objective"],
                "controller": "red",
                "victor": "red"
            },
            {
                "type": "territorial",
                "description": "Blue holds primary objective for 30 turns",
                "zones": ["primary_objective"],
                "controller": "blue",
                "turns_held": 30,
                "victor": "blue"
            },
            {
                "type": "attrition",
                "description": "Red loses 60% combat power",
                "threshold": 0.6,
                "faction": "red",
                "victor": "blue"
            },
            {
                "type": "time",
                "description": "Stalemate after 40 turns",
                "max_turns": 40,
                "victor": "draw"
            }
        ],
        "special_rules": [
            {
                "name": "reinforcements",
                "description": "Blue receives reinforcements on turn 10",
                "enabled": True,
                "trigger": {
                    "type": "turn",
                    "turn": 10
                },
                "effect": {
                    "spawn_units": "blue_reinforcements.yaml"
                }
            }
        ],
        "briefing": {
            "red": """SITUATION: NATO forces are in defensive positions. This is our chance
for a decisive breakthrough.

MISSION: Attack through the gap to seize the primary objective within 5 days.

EXECUTION: Lead with reconnaissance, follow with massed armor. Bypass strongpoints
where possible. Maintain tempo.

COMMANDER'S INTENT: Speed is more important than preserving combat power.""",
            "blue": """SITUATION: Warsaw Pact forces have initiated offensive operations.

MISSION: Delay enemy advance and defend critical terrain until reinforcements arrive.

EXECUTION: Conduct delay operations forward. Establish main defense line. Preserve
combat power for the defense.

COMMANDER'S INTENT: Trade space for time. Every hour of delay matters."""
        }
    }


def get_meeting_engagement_template() -> dict[str, Any]:
    """Return a meeting engagement template."""
    return {
        "scenario": {
            "name": "Meeting Engagement",
            "description": "Both sides advance to contact with unknown enemy positions."
        },
        "region": {
            "bounds": {
                "southwest": [50.0, 9.0],
                "northeast": [50.5, 9.5]
            },
            "terrain_source": "terrain.gpkg"
        },
        "factions": {
            "red": {
                "name": "Red Force",
                "doctrine": "soviet_offensive",
                "orbat_file": "red_orbat.yaml",
                "ai_controlled": True,
                "grisha_persona": "commander"
            },
            "blue": {
                "name": "Blue Force",
                "doctrine": "nato_maneuver",
                "orbat_file": "blue_orbat.yaml",
                "ai_controlled": False,
                "grisha_persona": "advisor"
            }
        },
        "initial_conditions": {
            "turn_length_hours": 2,
            "start_date": "1985-07-01T06:00:00",
            "weather": {
                "precipitation": "none",
                "visibility": "clear",
                "temperature_c": 22,
                "wind_speed_kph": 8,
                "wind_direction": 180
            }
        },
        "objectives": [
            {
                "name": "crossroads_alpha",
                "type": "crossroads",
                "coordinates": [50.25, 9.25],
                "points": 50,
                "controller": "neutral"
            }
        ],
        "victory_conditions": [
            {
                "type": "territorial",
                "description": "Red controls crossroads for 5 turns",
                "zones": ["crossroads_alpha"],
                "controller": "red",
                "turns_held": 5,
                "victor": "red"
            },
            {
                "type": "territorial",
                "description": "Blue controls crossroads for 5 turns",
                "zones": ["crossroads_alpha"],
                "controller": "blue",
                "turns_held": 5,
                "victor": "blue"
            },
            {
                "type": "attrition",
                "description": "Either side loses 50% combat power",
                "threshold": 0.5,
                "faction": "red",
                "victor": "blue"
            },
            {
                "type": "time",
                "description": "Draw after 20 turns",
                "max_turns": 20,
                "victor": "draw"
            }
        ],
        "special_rules": [],
        "briefing": {
            "red": """SITUATION: Enemy forces advancing from the west. Exact positions unknown.

MISSION: Seize and hold the crossroads at Alpha.

EXECUTION: Advance to contact, secure objective, prepare for counterattack.""",
            "blue": """SITUATION: Enemy forces advancing from the east. Exact positions unknown.

MISSION: Seize and hold the crossroads at Alpha.

EXECUTION: Advance to contact, secure objective, prepare for counterattack."""
        }
    }


def get_defensive_template() -> dict[str, Any]:
    """Return a defensive operation template."""
    return {
        "scenario": {
            "name": "Defensive Operation",
            "description": "Blue defends prepared positions against Red assault."
        },
        "region": {
            "bounds": {
                "southwest": [50.0, 9.0],
                "northeast": [50.8, 10.0]
            },
            "terrain_source": "terrain.gpkg"
        },
        "factions": {
            "red": {
                "name": "Attacking Force",
                "doctrine": "soviet_combined_arms",
                "orbat_file": "red_orbat.yaml",
                "ai_controlled": True,
                "grisha_persona": "commander"
            },
            "blue": {
                "name": "Defending Force",
                "doctrine": "nato_area_defense",
                "orbat_file": "blue_orbat.yaml",
                "ai_controlled": False,
                "grisha_persona": "advisor"
            }
        },
        "initial_conditions": {
            "turn_length_hours": 4,
            "start_date": "1985-09-01T04:00:00",
            "weather": {
                "precipitation": "light",
                "visibility": "haze",
                "temperature_c": 14,
                "wind_speed_kph": 20,
                "wind_direction": 315
            }
        },
        "objectives": [
            {
                "name": "main_defense_line",
                "type": "terrain",
                "coordinates": [50.4, 9.5],
                "points": 100,
                "controller": "blue"
            },
            {
                "name": "supply_depot",
                "type": "supply_depot",
                "coordinates": [50.2, 9.3],
                "points": 40,
                "controller": "blue"
            }
        ],
        "victory_conditions": [
            {
                "type": "territorial",
                "description": "Red breaks through main defense line",
                "zones": ["main_defense_line"],
                "controller": "red",
                "victor": "red"
            },
            {
                "type": "attrition",
                "description": "Red loses 40% combat power",
                "threshold": 0.4,
                "faction": "red",
                "victor": "blue"
            },
            {
                "type": "time",
                "description": "Blue holds for 24 turns",
                "max_turns": 24,
                "victor": "blue"
            }
        ],
        "special_rules": [],
        "briefing": {
            "red": """SITUATION: Enemy has established defensive positions along the ridgeline.

MISSION: Break through enemy defenses and seize the supply depot.

EXECUTION: Conduct artillery preparation, then assault with combined arms.""",
            "blue": """SITUATION: Enemy forces massing for attack. Assault imminent.

MISSION: Defend in sector. Do not allow penetration of main defense line.

EXECUTION: Engage enemy at maximum range. Fall back to alternate positions only
when necessary. Preserve combat power."""
        }
    }


# Template registry
SCENARIO_TEMPLATES: dict[str, dict[str, Any]] = {
    "blank": get_blank_scenario_template(),
    "cold_war_offensive": get_cold_war_offensive_template(),
    "meeting_engagement": get_meeting_engagement_template(),
    "defensive": get_defensive_template(),
}


def get_blank_orbat_template(faction: str = "red") -> dict[str, Any]:
    """Return a blank ORBAT template."""
    faction_name = "Red Force" if faction == "red" else "Blue Force"
    return {
        "faction": faction,
        "name": f"{faction_name} ORBAT",
        "units": []
    }


def get_sample_orbat_template(faction: str = "red") -> dict[str, Any]:
    """Return a sample ORBAT with a basic task organization."""
    if faction == "red":
        return {
            "faction": "red",
            "name": "8th Guards Tank Army",
            "units": [
                {
                    "id": "8gta_hq",
                    "name": "8th Guards Tank Army HQ",
                    "type": "headquarters",
                    "echelon": "army",
                    "mobility_class": "tracked",
                    "position": [50.9, 10.2],
                    "heading": 270,
                    "posture": "support",
                    "personnel": 200,
                    "personnel_max": 250,
                    "equipment": 50,
                    "equipment_max": 60,
                    "subordinate_ids": ["1gtd", "7gtd", "79td"]
                },
                {
                    "id": "1gtd",
                    "name": "1st Guards Tank Division",
                    "type": "armor",
                    "echelon": "division",
                    "mobility_class": "tracked",
                    "position": [50.85, 10.1],
                    "heading": 270,
                    "posture": "attack",
                    "parent_id": "8gta_hq",
                    "personnel": 10000,
                    "personnel_max": 12000,
                    "equipment": 300,
                    "equipment_max": 350,
                    "combat_stats": {
                        "combat_power": 350,
                        "defense_value": 200,
                        "soft_attack": 150,
                        "hard_attack": 300,
                        "air_defense": 80
                    }
                },
                {
                    "id": "7gtd",
                    "name": "7th Guards Tank Division",
                    "type": "armor",
                    "echelon": "division",
                    "mobility_class": "tracked",
                    "position": [50.75, 10.15],
                    "heading": 270,
                    "posture": "reserve",
                    "parent_id": "8gta_hq",
                    "personnel": 10500,
                    "personnel_max": 12000,
                    "equipment": 320,
                    "equipment_max": 350,
                    "combat_stats": {
                        "combat_power": 380,
                        "defense_value": 220,
                        "soft_attack": 160,
                        "hard_attack": 320,
                        "air_defense": 85
                    }
                },
                {
                    "id": "79td",
                    "name": "79th Tank Division",
                    "type": "armor",
                    "echelon": "division",
                    "mobility_class": "tracked",
                    "position": [50.95, 10.05],
                    "heading": 270,
                    "posture": "attack",
                    "parent_id": "8gta_hq",
                    "personnel": 9500,
                    "personnel_max": 11000,
                    "equipment": 280,
                    "equipment_max": 320,
                    "combat_stats": {
                        "combat_power": 320,
                        "defense_value": 180,
                        "soft_attack": 140,
                        "hard_attack": 280,
                        "air_defense": 70
                    }
                }
            ]
        }
    else:
        return {
            "faction": "blue",
            "name": "V Corps",
            "units": [
                {
                    "id": "vcorps_hq",
                    "name": "V Corps Headquarters",
                    "type": "headquarters",
                    "echelon": "corps",
                    "mobility_class": "wheeled",
                    "position": [50.2, 9.2],
                    "heading": 90,
                    "posture": "support",
                    "personnel": 150,
                    "personnel_max": 180,
                    "equipment": 40,
                    "equipment_max": 50,
                    "subordinate_ids": ["3ad", "8id", "11acr"]
                },
                {
                    "id": "3ad",
                    "name": "3rd Armored Division",
                    "type": "armor",
                    "echelon": "division",
                    "mobility_class": "tracked",
                    "position": [50.5, 9.5],
                    "heading": 90,
                    "posture": "defend",
                    "parent_id": "vcorps_hq",
                    "personnel": 15000,
                    "personnel_max": 17000,
                    "equipment": 280,
                    "equipment_max": 300,
                    "combat_stats": {
                        "combat_power": 380,
                        "defense_value": 350,
                        "soft_attack": 180,
                        "hard_attack": 350,
                        "air_defense": 100
                    }
                },
                {
                    "id": "8id",
                    "name": "8th Infantry Division (Mech)",
                    "type": "mechanized",
                    "echelon": "division",
                    "mobility_class": "tracked",
                    "position": [50.4, 9.6],
                    "heading": 90,
                    "posture": "defend",
                    "parent_id": "vcorps_hq",
                    "personnel": 14000,
                    "personnel_max": 16000,
                    "equipment": 260,
                    "equipment_max": 280,
                    "combat_stats": {
                        "combat_power": 300,
                        "defense_value": 400,
                        "soft_attack": 200,
                        "hard_attack": 250,
                        "air_defense": 90
                    }
                },
                {
                    "id": "11acr",
                    "name": "11th Armored Cavalry Regiment",
                    "type": "recon",
                    "echelon": "regiment",
                    "mobility_class": "tracked",
                    "position": [50.7, 9.8],
                    "heading": 90,
                    "posture": "recon",
                    "parent_id": "vcorps_hq",
                    "personnel": 4500,
                    "personnel_max": 5000,
                    "equipment": 120,
                    "equipment_max": 140,
                    "combat_stats": {
                        "combat_power": 150,
                        "defense_value": 120,
                        "soft_attack": 80,
                        "hard_attack": 130,
                        "air_defense": 40
                    }
                }
            ]
        }


ORBAT_TEMPLATES: dict[str, dict[str, Any]] = {
    "blank_red": get_blank_orbat_template("red"),
    "blank_blue": get_blank_orbat_template("blue"),
    "sample_red": get_sample_orbat_template("red"),
    "sample_blue": get_sample_orbat_template("blue"),
}
