#!/usr/bin/env python
"""Setup script for the Omnichannel MVP project."""
import subprocess  # nosec B404
import sys
from pathlib import Path

# Get the base directory of the project using relative paths
BASE_DIR = Path(__file__).resolve().parent


def setup_virtual_environment():
    """Create and activate a virtual environment."""
    venv_dir = BASE_DIR / "venv"

    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)], check=True,
    )  # nosec B603

    # Determine the pip path based on OS
    if sys.platform == "win32":
        pip_path = venv_dir / "Scripts" / "pip"
    else:
        pip_path = venv_dir / "bin" / "pip"

    # Upgrade pip
    subprocess.run(
        [str(pip_path), "install", "--upgrade", "pip"], check=True,
    )  # nosec B603

    return pip_path


def install_dependencies(pip_path):
    """Install Python dependencies from requirements.txt."""
    requirements_path = BASE_DIR / "requirements.txt"

    subprocess.run(
        [str(pip_path), "install", "-r", str(requirements_path)], check=True,
    )  # nosec B603


def setup_frontend():
    """Set up the frontend application."""
    frontend_dir = BASE_DIR / "frontend" / "agent-dashboard"

    if not frontend_dir.exists():
        return

    # Use npm ci for clean installs
    subprocess.run(["npm", "ci"], cwd=str(frontend_dir), check=True)  # nosec B603, B607


def setup_database():
    """Run database migrations."""
    manage_py = BASE_DIR / "manage.py"

    if not manage_py.exists():
        return

    subprocess.run(
        [sys.executable, str(manage_py), "migrate"], check=True,
    )  # nosec B603

    subprocess.run(  # nosec B603
        [sys.executable, str(manage_py), "loaddata", "initial_data"], check=True,
    )


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_example = BASE_DIR / ".env.example"
    env_file = BASE_DIR / ".env"

    if not env_file.exists() and env_example.exists():
        with env_example.open("r") as example, env_file.open("w") as env:
            env.write(example.read())


def main():
    """Run the setup process."""
    try:
        # Create .env file first so it's available for later steps
        create_env_file()

        # Setup virtual environment and install dependencies
        pip_path = setup_virtual_environment()
        install_dependencies(pip_path)

        # Setup frontend
        setup_frontend()

        # Setup database
        setup_database()

        if sys.platform == "win32":
            pass
        else:
            pass



    except subprocess.CalledProcessError:
        sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
