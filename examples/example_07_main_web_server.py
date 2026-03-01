"""
Main script to run initial examples and start the web server.

# To run this example, first install the required dependencies:
# pip install -e ".[examples]"

This script demonstrates the integration of the adaptive memory pool
with web frameworks (Flask or FastAPI) by first running some basic
examples and then launching a web server.
"""

import argparse

import uvicorn

from examples.example_01_basic_bytesio import basic_usage_example
from examples.example_05_advanced_features import example_presets_configuration

# pylint: disable=W0611
from examples.example_07_web_integration import (
    FASTAPI_AVAILABLE,
    FLASK_AVAILABLE,
    create_flask_app,
    init_flask_pools,
)


def run_initial_examples():
    """Runs a few introductory examples."""
    print("--- Running Initial Examples ---")
    try:
        basic_usage_example()
        example_presets_configuration()
    except Exception:  # pylint: disable=W0718
        print("An error occurred while running initial examples.")
    print("--- Initial Examples Finished ---\n")


def main():
    """Main function to start the web server."""
    parser = argparse.ArgumentParser(description="Web Server for Memory Pool Integration Example")
    parser.add_argument(
        "--framework",
        type=str,
        choices=["flask", "fastapi"],
        default="fastapi",
        help="The web framework to use.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface for the web server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port for the web server.",
    )
    args = parser.parse_args()

    run_initial_examples()

    if args.framework == "flask":
        if not FLASK_AVAILABLE:
            print("Flask is not installed. Please install it with 'pip install Flask'.")
            return
        print("Starting Flask server...")
        init_flask_pools()
        app = create_flask_app()
        app.run(host=args.host, port=args.port, debug=False)

    elif args.framework == "fastapi":
        if not FASTAPI_AVAILABLE:
            print("FastAPI is not installed. Please install it with 'pip install fastapi uvicorn'.")
            return
        print("Starting FastAPI server with Uvicorn...")
        # The app object is a callable that uvicorn can run
        app_creator = "examples.example_07_web_integration:create_fastapi_app"
        uvicorn.run(app_creator, host=args.host, port=args.port, factory=True)


if __name__ == "__main__":
    main()
