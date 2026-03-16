// Python bindings for KARKAS core simulation engine
// Uses pybind11 to expose C++ classes to Python

#ifdef KARKAS_BUILD_PYTHON_BINDINGS

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>

#include "types.hpp"
#include "unit.hpp"
#include "orbat_manager.hpp"
#include "terrain/terrain_engine.hpp"
#include "combat/combat_resolver.hpp"
#include "sensors/sensor_model.hpp"
#include "movement/movement_resolver.hpp"
#include "simulation.hpp"

namespace py = pybind11;

PYBIND11_MODULE(karkas_engine, m) {
    m.doc() = "KARKAS Simulation Engine - C++ core bindings";

    // Enums
    py::enum_<karkas::Faction>(m, "Faction")
        .value("Red", karkas::Faction::Red)
        .value("Blue", karkas::Faction::Blue)
        .value("Neutral", karkas::Faction::Neutral);

    py::enum_<karkas::UnitType>(m, "UnitType")
        .value("Infantry", karkas::UnitType::Infantry)
        .value("Armor", karkas::UnitType::Armor)
        .value("Mechanized", karkas::UnitType::Mechanized)
        .value("Artillery", karkas::UnitType::Artillery)
        .value("AirDefense", karkas::UnitType::AirDefense)
        .value("Rotary", karkas::UnitType::Rotary)
        .value("FixedWing", karkas::UnitType::FixedWing)
        .value("Support", karkas::UnitType::Support)
        .value("Headquarters", karkas::UnitType::Headquarters)
        .value("Recon", karkas::UnitType::Recon)
        .value("Engineer", karkas::UnitType::Engineer)
        .value("Logistics", karkas::UnitType::Logistics);

    py::enum_<karkas::Echelon>(m, "Echelon")
        .value("Squad", karkas::Echelon::Squad)
        .value("Platoon", karkas::Echelon::Platoon)
        .value("Company", karkas::Echelon::Company)
        .value("Battalion", karkas::Echelon::Battalion)
        .value("Regiment", karkas::Echelon::Regiment)
        .value("Brigade", karkas::Echelon::Brigade)
        .value("Division", karkas::Echelon::Division)
        .value("Corps", karkas::Echelon::Corps)
        .value("Army", karkas::Echelon::Army);

    py::enum_<karkas::Posture>(m, "Posture")
        .value("Attack", karkas::Posture::Attack)
        .value("Defend", karkas::Posture::Defend)
        .value("Move", karkas::Posture::Move)
        .value("Recon", karkas::Posture::Recon)
        .value("Support", karkas::Posture::Support)
        .value("Reserve", karkas::Posture::Reserve)
        .value("Retreat", karkas::Posture::Retreat)
        .value("Disengaged", karkas::Posture::Disengaged);

    py::enum_<karkas::TurnPhase>(m, "TurnPhase")
        .value("Planning", karkas::TurnPhase::Planning)
        .value("Execution", karkas::TurnPhase::Execution)
        .value("Reporting", karkas::TurnPhase::Reporting);

    // Coordinates
    py::class_<karkas::Coordinates>(m, "Coordinates")
        .def(py::init<>())
        .def(py::init<double, double>())
        .def_readwrite("latitude", &karkas::Coordinates::latitude)
        .def_readwrite("longitude", &karkas::Coordinates::longitude)
        .def("distance_to", &karkas::Coordinates::distance_to)
        .def("bearing_to", &karkas::Coordinates::bearing_to)
        .def("move_toward", &karkas::Coordinates::move_toward);

    // BoundingBox
    py::class_<karkas::BoundingBox>(m, "BoundingBox")
        .def(py::init<>())
        .def_readwrite("southwest", &karkas::BoundingBox::southwest)
        .def_readwrite("northeast", &karkas::BoundingBox::northeast)
        .def("contains", &karkas::BoundingBox::contains)
        .def("width_km", &karkas::BoundingBox::width_km)
        .def("height_km", &karkas::BoundingBox::height_km);

    // Unit (simplified - full binding would be extensive)
    py::class_<karkas::Unit>(m, "Unit")
        .def(py::init<karkas::UnitId, std::string, karkas::Faction,
                      karkas::UnitType, karkas::Echelon>())
        .def("get_id", &karkas::Unit::get_id)
        .def("get_name", &karkas::Unit::get_name)
        .def("get_faction", &karkas::Unit::get_faction)
        .def("get_type", &karkas::Unit::get_type)
        .def("get_echelon", &karkas::Unit::get_echelon)
        .def("get_position", &karkas::Unit::get_position)
        .def("set_position", &karkas::Unit::set_position)
        .def("get_posture", &karkas::Unit::get_posture)
        .def("set_posture", &karkas::Unit::set_posture)
        .def("is_combat_effective", &karkas::Unit::is_combat_effective)
        .def("is_destroyed", &karkas::Unit::is_destroyed)
        .def("to_json", &karkas::Unit::to_json);

    // TerrainEngine
    py::class_<karkas::TerrainEngine>(m, "TerrainEngine")
        .def(py::init<>())
        .def("load_region", &karkas::TerrainEngine::load_region)
        .def("is_loaded", &karkas::TerrainEngine::is_loaded)
        .def("get_bounds", &karkas::TerrainEngine::get_bounds)
        .def("get_elevation", &karkas::TerrainEngine::get_elevation)
        .def("has_los", &karkas::TerrainEngine::has_los);

    // Simulation
    py::class_<karkas::Simulation>(m, "Simulation")
        .def(py::init<>())
        .def("load_scenario_from_file", &karkas::Simulation::load_scenario_from_file)
        .def("get_phase", &karkas::Simulation::get_phase)
        .def("ready_to_execute", &karkas::Simulation::ready_to_execute)
        .def("execute_turn", &karkas::Simulation::execute_turn)
        .def("check_victory", &karkas::Simulation::check_victory)
        .def("save_game", &karkas::Simulation::save_game)
        .def("load_game", &karkas::Simulation::load_game);

    // TurnResult
    py::class_<karkas::TurnResult>(m, "TurnResult")
        .def_readonly("turn", &karkas::TurnResult::turn)
        .def_readonly("game_over", &karkas::TurnResult::game_over)
        .def_readonly("red_summary", &karkas::TurnResult::red_summary)
        .def_readonly("blue_summary", &karkas::TurnResult::blue_summary);
}

#endif  // KARKAS_BUILD_PYTHON_BINDINGS
