/// Movement range computation (BFS) and direction helpers.

use crate::types::*;
use crate::board::*;

/// Get all tiles a unit can reach via BFS with move_speed steps.
///
/// Returns Vec of (x, y) positions. Includes current position.
/// Units block stopping (can walk through their tile but not stop).
/// Dead wrecks hard-block (can't pass at all).
pub fn reachable_tiles(board: &Board, unit_idx: usize) -> Vec<(u8, u8)> {
    let unit = &board.units[unit_idx];
    let ux = unit.x;
    let uy = unit.y;

    // Webbed/frozen units cannot move — only current position
    if unit.web() || unit.frozen() {
        return vec![(ux, uy)];
    }

    let uid = unit.uid;
    let speed = unit.move_speed;
    let flying = unit.flying();

    let mut result = Vec::with_capacity(20);
    result.push((ux, uy)); // always include current position

    // BFS: visited[x*8+y] = min cost to reach, 255 = unvisited
    let mut visited = [255u8; 64];
    visited[xy_to_idx(ux, uy)] = 0;

    // Simple queue (board is 8x8, max 64 entries)
    let mut queue = [(0u8, 0u8, 0u8); 64];
    let mut head = 0usize;
    let mut tail = 0usize;
    queue[tail] = (ux, uy, 0);
    tail += 1;

    while head < tail {
        let (x, y, cost) = queue[head];
        head += 1;

        for &(dx, dy) in &DIRS {
            let nx = x as i8 + dx;
            let ny = y as i8 + dy;

            if !in_bounds(nx, ny) {
                continue;
            }
            let nx = nx as u8;
            let ny = ny as u8;
            let idx = xy_to_idx(nx, ny);

            if visited[idx] != 255 {
                continue;
            }

            let new_cost = cost + 1;
            if new_cost > speed {
                continue;
            }

            let tile = board.tile(nx, ny);

            // Mountains always block
            if tile.terrain == Terrain::Mountain {
                continue;
            }

            // Buildings block movement
            if tile.is_building() {
                continue;
            }

            // Ground units can't cross deadly terrain
            if !flying && tile.terrain.is_deadly_ground() {
                continue;
            }

            // Other alive units: friendly can walk through (not stop), enemies hard-block
            if let Some(blocker_idx) = board.unit_at(nx, ny) {
                if board.units[blocker_idx].uid != uid {
                    if board.units[blocker_idx].team == unit.team {
                        // Friendly: can walk through but can't stop here
                        visited[idx] = new_cost;
                        if new_cost < speed {
                            queue[tail] = (nx, ny, new_cost);
                            tail += 1;
                        }
                    }
                    // Enemy/neutral: hard block — don't add to queue
                    continue;
                }
            }

            // Dead unit wrecks hard-block
            if board.wreck_at(nx, ny) {
                continue;
            }

            visited[idx] = new_cost;
            result.push((nx, ny));
            queue[tail] = (nx, ny, new_cost);
            tail += 1;
        }
    }

    result
}

/// Get adjacent tiles with direction index.
/// Returns up to 4 entries: (nx, ny, dir_idx).
pub fn adjacent(x: u8, y: u8) -> [(u8, u8, usize); 4] {
    // Returns fixed array; caller checks in_bounds
    let mut result = [(0u8, 0u8, 0usize); 4];
    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        result[i] = (nx as u8, ny as u8, i);
    }
    result
}

/// Get valid adjacent tiles (in-bounds only).
pub fn adjacent_valid(x: u8, y: u8) -> Vec<(u8, u8, usize)> {
    let mut result = Vec::with_capacity(4);
    for (i, &(dx, dy)) in DIRS.iter().enumerate() {
        let nx = x as i8 + dx;
        let ny = y as i8 + dy;
        if in_bounds(nx, ny) {
            result.push((nx as u8, ny as u8, i));
        }
    }
    result
}

/// Direction index from one tile to an adjacent tile.
/// Returns None if tiles are not adjacent.
pub fn direction_between(from_x: u8, from_y: u8, to_x: u8, to_y: u8) -> Option<usize> {
    let dx = to_x as i8 - from_x as i8;
    let dy = to_y as i8 - from_y as i8;
    DIRS.iter().position(|&(ddx, ddy)| ddx == dx && ddy == dy)
}

/// Predict where a unit ends up after push. None if blocked.
/// Does NOT check for dead units (push_destination is for pruning heuristics).
pub fn push_destination(x: u8, y: u8, direction: usize, board: &Board) -> Option<(u8, u8)> {
    let (dx, dy) = DIRS[direction];
    let nx = x as i8 + dx;
    let ny = y as i8 + dy;

    if !in_bounds(nx, ny) {
        return None; // map edge
    }
    let nx = nx as u8;
    let ny = ny as u8;

    let tile = board.tile(nx, ny);
    if tile.terrain == Terrain::Mountain {
        return None;
    }
    if tile.is_building() {
        return None;
    }
    if board.unit_at(nx, ny).is_some() {
        return None;
    }

    Some((nx, ny))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_board_with_unit(x: u8, y: u8, speed: u8, flying: bool) -> (Board, usize) {
        let mut board = Board::default();
        let mut unit = Unit::default();
        unit.uid = 1;
        unit.x = x;
        unit.y = y;
        unit.hp = 3;
        unit.max_hp = 3;
        unit.move_speed = speed;
        unit.team = Team::Player;
        if flying {
            unit.flags |= UnitFlags::FLYING;
        }
        unit.flags |= UnitFlags::IS_MECH | UnitFlags::ACTIVE;
        let idx = board.add_unit(unit);
        (board, idx)
    }

    #[test]
    fn test_basic_reachable() {
        let (board, idx) = make_board_with_unit(4, 4, 3, false);
        let tiles = reachable_tiles(&board, idx);
        // Center of empty board with speed 3: should reach many tiles
        assert!(tiles.len() > 10);
        assert!(tiles.contains(&(4, 4))); // includes self
    }

    #[test]
    fn test_corner_reachable() {
        let (board, idx) = make_board_with_unit(0, 0, 2, false);
        let tiles = reachable_tiles(&board, idx);
        // Corner with speed 2: limited tiles
        // (0,0), (0,1), (0,2), (1,0), (1,1), (2,0) = 6 tiles
        assert_eq!(tiles.len(), 6);
    }

    #[test]
    fn test_mountain_blocks() {
        let (mut board, idx) = make_board_with_unit(0, 0, 3, false);
        board.tile_mut(1, 0).terrain = Terrain::Mountain;
        board.tile_mut(0, 1).terrain = Terrain::Mountain;
        let tiles = reachable_tiles(&board, idx);
        // Only (0,0) - completely blocked
        assert_eq!(tiles.len(), 1);
    }

    #[test]
    fn test_water_blocks_ground() {
        let (mut board, idx) = make_board_with_unit(0, 0, 2, false);
        board.tile_mut(0, 1).terrain = Terrain::Water;
        let tiles = reachable_tiles(&board, idx);
        assert!(!tiles.contains(&(0, 1)));
    }

    #[test]
    fn test_flying_crosses_water() {
        let (mut board, idx) = make_board_with_unit(0, 0, 2, true);
        board.tile_mut(0, 1).terrain = Terrain::Water;
        let tiles = reachable_tiles(&board, idx);
        assert!(tiles.contains(&(0, 1)));
    }

    #[test]
    fn test_enemy_hard_blocks() {
        let (mut board, idx) = make_board_with_unit(0, 0, 3, false);
        // Place an enemy at (1, 0)
        let mut blocker = Unit::default();
        blocker.uid = 2;
        blocker.x = 1;
        blocker.y = 0;
        blocker.hp = 2;
        blocker.team = Team::Enemy;
        board.add_unit(blocker);

        let tiles = reachable_tiles(&board, idx);
        // Enemy is a hard block — can't stop on or path through
        assert!(!tiles.contains(&(1, 0)));
        assert!(!tiles.contains(&(2, 0)));
    }

    #[test]
    fn test_friendly_walk_through() {
        let (mut board, idx) = make_board_with_unit(0, 0, 3, false);
        // Place a friendly unit at (1, 0)
        let mut friendly = Unit::default();
        friendly.uid = 2;
        friendly.x = 1;
        friendly.y = 0;
        friendly.hp = 2;
        friendly.team = Team::Player;
        board.add_unit(friendly);

        let tiles = reachable_tiles(&board, idx);
        // Friendly: can walk through but can't stop on their tile
        assert!(!tiles.contains(&(1, 0)));
        assert!(tiles.contains(&(2, 0)));
    }

    #[test]
    fn test_wreck_hard_blocks() {
        let (mut board, idx) = make_board_with_unit(0, 0, 3, false);
        // Place a dead wreck at (1, 0)
        let mut wreck = Unit::default();
        wreck.uid = 2;
        wreck.x = 1;
        wreck.y = 0;
        wreck.hp = 0; // dead
        wreck.team = Team::Player;
        board.add_unit(wreck);

        let tiles = reachable_tiles(&board, idx);
        // Can't pass through wreck at all
        assert!(!tiles.contains(&(1, 0)));
        assert!(!tiles.contains(&(2, 0))); // blocked behind wreck
    }

    #[test]
    fn test_direction_between_adjacent() {
        assert_eq!(direction_between(3, 3, 3, 4), Some(0)); // N: +y
        assert_eq!(direction_between(3, 3, 4, 3), Some(1)); // E: +x
        assert_eq!(direction_between(3, 3, 3, 2), Some(2)); // S: -y
        assert_eq!(direction_between(3, 3, 2, 3), Some(3)); // W: -x
    }

    #[test]
    fn test_direction_between_non_adjacent() {
        assert_eq!(direction_between(3, 3, 5, 3), None);
        assert_eq!(direction_between(3, 3, 4, 4), None); // diagonal
    }

    #[test]
    fn test_push_destination_clear() {
        let board = Board::default();
        assert_eq!(push_destination(3, 3, 0, &board), Some((3, 4))); // N
    }

    #[test]
    fn test_push_destination_edge() {
        let board = Board::default();
        assert_eq!(push_destination(0, 0, 2, &board), None); // S off edge
        assert_eq!(push_destination(0, 0, 3, &board), None); // W off edge
    }

    #[test]
    fn test_push_destination_mountain() {
        let mut board = Board::default();
        board.tile_mut(3, 4).terrain = Terrain::Mountain;
        assert_eq!(push_destination(3, 3, 0, &board), None); // blocked by mountain
    }
}
