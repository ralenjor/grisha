// Pathfinder - Architecture Note
//
// Pathfinding in KARKAS is split across two components:
//
// 1. terrain_engine.cpp - A* pathfinding implementation
//    - find_path(): Core A* algorithm with route preferences
//    - find_path_avoiding(): A* with obstacle avoidance
//    - find_road_route(): Road-following pathfinding
//    - Returns Path objects with segments and travel times
//
// 2. movement_resolver.cpp - Path execution and following
//    - follow_path(): Segment-by-segment path traversal
//    - Terrain-based speed calculations per segment
//    - Fuel consumption during movement
//    - Collision and congestion handling
//    - Formation positioning
//
// Future enhancements (for this file):
// - Hierarchical pathfinding for large maps (HPA*)
// - Dynamic obstacle avoidance during movement
// - Multi-unit coordinated pathfinding
// - Convoy/column movement optimization
// - Road network graph for faster route queries
// - Cached paths for common routes
// - Temporal pathfinding (predict enemy positions)

#include "movement_resolver.hpp"
#include "../terrain/terrain_engine.hpp"

namespace karkas {

// Reserved for future advanced pathfinding features

}  // namespace karkas
