"""Create a draft dynamic File Search version of the existing Foundry agent."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.foundry_agent import FoundryAgentService


def main() -> None:
    """Print the immutable draft version for configuration into local .env."""
    service = FoundryAgentService()
    version = service.create_dynamic_file_search_version()
    print(f"Created dynamic File Search draft version: {version}")
    print("Set FOUNDRY_DYNAMIC_AGENT_VERSION to this value in your local .env.")


if __name__ == "__main__":
    main()
