// Detection System Implementation
// Core detection logic is in sensor_model.cpp
// Electronic warfare effects are implemented via EWEnvironment and SensorModel

#include "sensor_model.hpp"

namespace karkas {

// Electronic Warfare integration notes:
// - EW effects are modeled through EWEnvironment (types.hpp)
// - SensorModel::get_jamming_modifier() calculates detection degradation
// - SensorModel::is_sensor_jammed() checks for severe jamming conditions
// - SensorModel::create_jamming_effect() creates effects from unit jammers
//
// Future enhancements:
// - Camouflage and deception (decoys, dummy positions)
// - Multi-spectral sensor fusion
// - Intelligence collection management
// - SEAD/DEAD mission support
// - Emission control (EMCON) states

}  // namespace karkas
