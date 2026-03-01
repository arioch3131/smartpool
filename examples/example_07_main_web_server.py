"""
Main script to run initial examples and start the web server.

# To run this example, first install the required dependencies:
# pip install -e ".[examples]"

This script demonstrates the integration of the adaptive memory pool
with web frameworks (Flask or FastAPI) by first running some basic
examples and then launching a web server.
"""

import argparse
import importlib

from examples import example_07_web_integration as web_integration
from examples.example_01_basic_bytesio import basic_usage_example
from examples.example_05_advanced_features import example_presets_configuration


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
        if not web_integration.FLASK_AVAILABLE:
            print("Flask is not installed. Please install it with 'pip install Flask'.")
            return
        if not hasattr(web_integration, "init_flask_pools") or not hasattr(
            web_integration, "create_flask_app"
        ):
            print("Flask helpers are unavailable in the integration module.")
            return
        print("Starting Flask server...")
        web_integration.init_flask_pools()
        app = web_integration.create_flask_app()
        app.run(host=args.host, port=args.port, debug=False)

    elif args.framework == "fastapi":
        if not web_integration.FASTAPI_AVAILABLE:
            print("FastAPI is not installed. Please install it with 'pip install fastapi uvicorn'.")
            return
        try:
            uvicorn = importlib.import_module("uvicorn")
        except ImportError:
            print("Uvicorn is not installed. Please install it with 'pip install uvicorn'.")
            return
        print("Starting FastAPI server with Uvicorn...")
        # The app object is a callable that uvicorn can run
        app_creator = "examples.example_07_web_integration:create_fastapi_app"
        uvicorn.run(app_creator, host=args.host, port=args.port, factory=True)


if __name__ == "__main__":
    main()
