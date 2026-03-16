#!/usr/bin/env python3
"""
KARKAS Database Administration Tool

CLI for managing the KARKAS PostgreSQL database:
- Initialize/reset database
- List/delete games
- Export/import game data
- View statistics
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def init_db(args):
    """Initialize the database"""
    from server.database import init_database, get_database_url
    from server.database.config import set_database_config, DatabaseConfig

    # Configure from args
    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
        echo=args.verbose,
    )
    set_database_config(config)

    print(f"Connecting to: {config.get_url()}")
    print("Initializing database...")

    try:
        init_database(create_tables=True, drop_existing=args.reset)
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def list_games(args):
    """List all games"""
    from server.database import GameStore, get_session
    from server.database.config import set_database_config, DatabaseConfig

    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
    )
    set_database_config(config)

    with get_session() as session:
        store = GameStore(session)
        games = store.list_games(include_completed=not args.active_only, session=session)

    if not games:
        print("No games found")
        return

    print(f"\n{'Game ID':<20} {'Scenario':<25} {'Turn':<6} {'Phase':<12} {'Status':<10}")
    print("-" * 80)

    for game in games:
        status = "Over" if game["game_over"] else "Active"
        if game["winner"]:
            status = f"Won: {game['winner']}"
        print(
            f"{game['game_id']:<20} "
            f"{game['scenario_name'][:25]:<25} "
            f"{game['turn']:<6} "
            f"{game['phase']:<12} "
            f"{status:<10}"
        )

    print(f"\nTotal: {len(games)} games")


def delete_game(args):
    """Delete a game"""
    from server.database import GameStore, get_session
    from server.database.config import set_database_config, DatabaseConfig

    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
    )
    set_database_config(config)

    with get_session() as session:
        store = GameStore(session)

        if not args.force:
            response = input(f"Delete game '{args.game_id}'? [y/N] ")
            if response.lower() != "y":
                print("Cancelled")
                return

        if store.delete_game(args.game_id, session):
            print(f"Game '{args.game_id}' deleted")
        else:
            print(f"Game not found: {args.game_id}")
            sys.exit(1)


def show_stats(args):
    """Show game statistics"""
    from server.database import TurnHistoryStore, GameStore, get_session
    from server.database.config import set_database_config, DatabaseConfig

    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
    )
    set_database_config(config)

    with get_session() as session:
        game_store = GameStore(session)
        turn_history = TurnHistoryStore(game_store)
        stats = turn_history.get_game_statistics(args.game_id, session)

    if not stats:
        print(f"Game not found: {args.game_id}")
        sys.exit(1)

    print(f"\nStatistics for game: {args.game_id}")
    print("-" * 40)
    print(f"Total Turns:          {stats['total_turns']}")
    print(f"Total Combats:        {stats['total_combats']}")
    print(f"Total Movements:      {stats['total_movements']}")
    print(f"Total Detections:     {stats['total_detections']}")
    print(f"Personnel Killed:     {stats['total_personnel_killed']}")
    print(f"Equipment Destroyed:  {stats['total_equipment_destroyed']}")
    print(f"Game Over:            {stats['game_over']}")
    if stats["winner"]:
        print(f"Winner:               {stats['winner']}")


def export_game(args):
    """Export game to JSON"""
    from server.database import ReplayController, get_session
    from server.database.config import set_database_config, DatabaseConfig

    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
    )
    set_database_config(config)

    with get_session() as session:
        replay = ReplayController()
        try:
            replay.start_replay(args.game_id, session=session)
            data = replay.export_replay(session)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    output_path = Path(args.output) if args.output else Path(f"{args.game_id}_export.json")

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    print(f"Exported to: {output_path}")


def show_history(args):
    """Show turn history"""
    from server.database import TurnHistoryStore, GameStore, get_session
    from server.database.config import set_database_config, DatabaseConfig

    config = DatabaseConfig(
        host=args.host,
        port=args.port,
        database=args.database,
        username=args.username,
        password=args.password,
    )
    set_database_config(config)

    with get_session() as session:
        game_store = GameStore(session)
        turn_history = TurnHistoryStore(game_store)

        if args.turn is not None:
            # Show specific turn
            result = turn_history.get_turn_result(args.game_id, args.turn, session)
            if result is None:
                print(f"No result for turn {args.turn}")
                sys.exit(1)

            print(f"\n=== Turn {result.turn} ===")
            print(f"Movements: {len(result.movements)}")
            print(f"Combats:   {len(result.combats)}")
            print(f"Detections: {len(result.detections)}")
            print(f"\nRed Summary: {result.red_summary}")
            print(f"Blue Summary: {result.blue_summary}")

            if result.game_over:
                print(f"\nGame Over! Winner: {result.winner}")
                if result.victory_reason:
                    print(f"Reason: {result.victory_reason}")
        else:
            # Show all turns
            results = turn_history.get_all_turn_results(args.game_id, session)
            if not results:
                print("No turn history found")
                return

            print(f"\n{'Turn':<6} {'Movements':<10} {'Combats':<10} {'Detections':<12} {'Status'}")
            print("-" * 60)

            for r in results:
                status = "Over" if r.game_over else ""
                print(
                    f"{r.turn:<6} "
                    f"{len(r.movements):<10} "
                    f"{len(r.combats):<10} "
                    f"{len(r.detections):<12} "
                    f"{status}"
                )


def main():
    parser = argparse.ArgumentParser(
        description="KARKAS Database Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database
  python -m tools.db_admin init

  # Reset database (WARNING: deletes all data)
  python -m tools.db_admin init --reset

  # List all games
  python -m tools.db_admin list

  # Show game statistics
  python -m tools.db_admin stats GAME_ID

  # Export game to JSON
  python -m tools.db_admin export GAME_ID -o game_export.json

  # View turn history
  python -m tools.db_admin history GAME_ID
  python -m tools.db_admin history GAME_ID --turn 5

Environment variables:
  KARKAS_DB_HOST      Database host (default: localhost)
  KARKAS_DB_PORT      Database port (default: 5432)
  KARKAS_DB_NAME      Database name (default: karkas)
  KARKAS_DB_USER      Database user (default: karkas)
  KARKAS_DB_PASSWORD  Database password (default: karkas)
""",
    )

    # Global arguments
    parser.add_argument(
        "--host",
        default="localhost",
        help="Database host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5432,
        help="Database port",
    )
    parser.add_argument(
        "--database",
        default="karkas",
        help="Database name",
    )
    parser.add_argument(
        "--username",
        default="karkas",
        help="Database username",
    )
    parser.add_argument(
        "--password",
        default="karkas",
        help="Database password",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output (show SQL)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing tables before creating",
    )
    init_parser.set_defaults(func=init_db)

    # list command
    list_parser = subparsers.add_parser("list", help="List games")
    list_parser.add_argument(
        "--active-only",
        action="store_true",
        help="Only show active games",
    )
    list_parser.set_defaults(func=list_games)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a game")
    delete_parser.add_argument("game_id", help="Game ID to delete")
    delete_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Delete without confirmation",
    )
    delete_parser.set_defaults(func=delete_game)

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show game statistics")
    stats_parser.add_argument("game_id", help="Game ID")
    stats_parser.set_defaults(func=show_stats)

    # export command
    export_parser = subparsers.add_parser("export", help="Export game to JSON")
    export_parser.add_argument("game_id", help="Game ID")
    export_parser.add_argument(
        "-o", "--output",
        help="Output file path",
    )
    export_parser.set_defaults(func=export_game)

    # history command
    history_parser = subparsers.add_parser("history", help="Show turn history")
    history_parser.add_argument("game_id", help="Game ID")
    history_parser.add_argument(
        "--turn",
        type=int,
        help="Show specific turn",
    )
    history_parser.set_defaults(func=show_history)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
