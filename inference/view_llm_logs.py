#!/usr/bin/env python3
# view_llm_logs.py

import os
import json
import argparse
import glob
from datetime import datetime
from typing import Dict, List, Any, Optional


def load_log_files(log_dir: str, sort_by_time: bool = True) -> List[Dict[str, Any]]:
    """
    Load all LLM log files from the directory.

    Args:
        log_dir: Directory containing log files
        sort_by_time: Whether to sort logs by timestamp

    Returns:
        List of log data dictionaries
    """
    # Find all JSON files in the directory
    log_files = glob.glob(os.path.join(log_dir, "*.json"))

    if not log_files:
        print(f"No log files found in {log_dir}")
        return []

    logs = []

    for file_path in log_files:
        try:
            with open(file_path, "r") as f:
                log_data = json.load(f)

            # Add filename to the log data
            log_data["_filename"] = os.path.basename(file_path)

            # Handle both single and batch interactions
            if "interactions" in log_data:
                # For batch logs, create separate entries for each interaction
                for idx, interaction in enumerate(log_data["interactions"]):
                    # Create a copy of the log data for each interaction
                    interaction_log = log_data.copy()
                    # Remove the interactions list
                    interaction_log.pop("interactions")
                    # Add the individual prompt and response
                    interaction_log["prompt"] = interaction["prompt"]
                    interaction_log["response"] = interaction["response"]
                    # Add interaction index to differentiate
                    interaction_log["_interaction_idx"] = idx
                    logs.append(interaction_log)
            else:
                # For single interaction logs
                logs.append(log_data)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    # Sort by timestamp if requested
    if sort_by_time and logs:
        logs.sort(key=lambda x: x.get("timestamp", ""))

    return logs


def display_chat_interface(
    logs: List[Dict[str, Any]],
    max_width: int = 80,
    show_metadata: bool = False,
    show_timestamps: bool = True,
    truncate_long_messages: bool = True,
    max_lines: int = 10,
) -> None:
    """
    Display logs in a chat-like interface.

    Args:
        logs: List of log data dictionaries
        max_width: Maximum width of the display
        show_metadata: Whether to show metadata
        show_timestamps: Whether to show timestamps
        truncate_long_messages: Whether to truncate long messages
        max_lines: Maximum number of lines to show per message when truncated
    """
    if not logs:
        print("No logs to display.")
        return

    # Terminal colors
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    for idx, log in enumerate(logs):
        # Extract data
        timestamp = log.get("timestamp", "Unknown time")
        prompt = log.get("prompt", "")
        response = log.get("response", "")
        metadata = log.get("metadata", {})
        filename = log.get("_filename", "")

        # Format timestamp
        if show_timestamps:
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted_time = timestamp

        # Print separator
        if idx > 0:
            print("\n" + "=" * max_width + "\n")

        # Print metadata header
        if show_metadata:
            print(f"{BOLD}Interaction {idx+1}{RESET} | {GRAY}File: {filename}{RESET}")
            if show_timestamps:
                print(f"{GRAY}Time: {formatted_time}{RESET}")

            if metadata:
                print(f"{GRAY}Model: {metadata.get('model', 'Unknown')}{RESET}")
                print(
                    f"{GRAY}Temperature: {metadata.get('temperature', 'Unknown')}{RESET}"
                )
            print()
        elif show_timestamps:
            print(f"{GRAY}[{formatted_time}]{RESET}")

        # Process and print prompt
        prompt_lines = prompt.strip().split("\n")
        if truncate_long_messages and len(prompt_lines) > max_lines:
            displayed_prompt = (
                "\n".join(prompt_lines[:max_lines])
                + f"\n{GRAY}... ({len(prompt_lines) - max_lines} more lines){RESET}"
            )
        else:
            displayed_prompt = prompt.strip()

        # Print prompt
        print(f"{BLUE}>>> PROMPT:{RESET}")
        print(f"{BLUE}{displayed_prompt}{RESET}")
        print()

        # Process and print response
        response_lines = response.strip().split("\n")
        if truncate_long_messages and len(response_lines) > max_lines:
            displayed_response = (
                "\n".join(response_lines[:max_lines])
                + f"\n{GRAY}... ({len(response_lines) - max_lines} more lines){RESET}"
            )
        else:
            displayed_response = response.strip()

        # Print response
        print(f"{GREEN}<<< RESPONSE:{RESET}")
        print(f"{GREEN}{displayed_response}{RESET}")


def main():
    """Main entry point for viewing LLM logs."""
    parser = argparse.ArgumentParser(
        description="View LLM logs in a chat-like interface"
    )
    parser.add_argument(
        "--log-dir", type=str, default="llm_logs", help="Directory containing log files"
    )
    parser.add_argument(
        "--latest", action="store_true", help="Only show the latest log"
    )
    parser.add_argument(
        "--no-sort", action="store_true", help="Don't sort logs by timestamp"
    )
    parser.add_argument(
        "--show-metadata",
        action="store_true",
        help="Show metadata for each interaction",
    )
    parser.add_argument("--no-timestamps", action="store_true", help="Hide timestamps")
    parser.add_argument(
        "--show-full", action="store_true", help="Show full messages without truncation"
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=10,
        help="Maximum lines to show per message when truncated",
    )
    parser.add_argument("--width", type=int, default=80, help="Display width")
    parser.add_argument(
        "--filter",
        type=str,
        help="Only show logs containing this string in prompt or response",
    )

    args = parser.parse_args()

    # Load logs
    logs = load_log_files(args.log_dir, sort_by_time=not args.no_sort)

    # Apply filters
    if args.filter:
        logs = [
            log
            for log in logs
            if args.filter.lower() in log.get("prompt", "").lower()
            or args.filter.lower() in log.get("response", "").lower()
        ]

    # Get only the latest log if requested
    if args.latest and logs:
        logs = [logs[-1]]

    # Display logs
    display_chat_interface(
        logs=logs,
        max_width=args.width,
        show_metadata=args.show_metadata,
        show_timestamps=not args.no_timestamps,
        truncate_long_messages=not args.show_full,
        max_lines=args.max_lines,
    )


if __name__ == "__main__":
    main()
