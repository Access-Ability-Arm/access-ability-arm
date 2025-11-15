# Makefile for Access Ability Arm
# Provides convenient commands for running, testing, and packaging the application

.PHONY: help install run web package-macos package-linux package-windows clean test lint format

# Default target - show help
help:
	@echo "Access Ability Arm - Makefile Commands"
	@echo "========================================"
	@echo ""
	@echo "Development:"
	@echo "  make install         - Install dependencies (requires Python 3.11)"
	@echo "  make run             - Run desktop application"
	@echo "  make web             - Run web application (localhost:8550)"
	@echo "  make web PORT=8080   - Run web application on custom port"
	@echo ""
	@echo "Packaging:"
	@echo "  make package-macos   - Build macOS application bundle"
	@echo "  make package-linux   - Build Linux application package"
	@echo "  make package-windows - Build Windows executable (on Windows only)"
	@echo "  make pod-install     - Install CocoaPods dependencies (macOS/iOS)"
	@echo ""
	@echo "Quality:"
	@echo "  make test            - Run tests"
	@echo "  make lint            - Check code style with flake8"
	@echo "  make format          - Format code with black"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Remove build artifacts and cache files"

# Install dependencies
install:
	@echo "Installing dependencies..."
	python3.11 -m pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

# Run desktop application
run:
	@echo "Starting Access Ability Arm (Desktop)..."
	python main.py

# Run web application (default port 8550)
PORT ?= 8550
web:
	@echo "Starting Access Ability Arm (Web) on port $(PORT)..."
	python main.py --web --port $(PORT)

# Package for macOS
package-macos:
	@echo "Building macOS application bundle..."
	@export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.4.0/bin:$$PATH" && \
	flet build macos \
		--project "access-ability-arm" \
		--product "Access Ability Arm" \
		--org "com.accessability" \
		--description "Assistive robotic arm control application" \
		--exclude gui \
		--exclude PyQt6 \
		--exclude archive \
		--cleanup-packages \
		--permissions camera \
		--info-plist NSCameraUsageDescription="This app requires camera access to detect objects and track face landmarks for assistive robotic arm control."
	@echo "✓ macOS package built in build/macos/"

# Package for Linux
package-linux:
	@echo "Building Linux application package..."
	flet build linux \
		--project "access-ability-arm" \
		--product "Access Ability Arm" \
		--org "com.accessability" \
		--description "Assistive robotic arm control application"
	@echo "✓ Linux package built in build/linux/"

# Package for Windows
package-windows:
	@echo "Building Windows executable..."
	flet build windows \
		--project "access-ability-arm" \
		--product "Access Ability Arm" \
		--org "com.accessability" \
		--description "Assistive robotic arm control application"
	@echo "✓ Windows package built in build/windows/"

# Run tests (if test framework is added later)
test:
	@echo "Running tests..."
	@if [ -d "tests" ]; then \
		python -m pytest tests/ -v; \
	else \
		echo "No tests directory found. Create tests/ directory to add tests."; \
	fi

# Lint code with flake8
lint:
	@echo "Checking code style..."
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 --max-line-length=100 --exclude=venv,build,archive .; \
	else \
		echo "flake8 not installed. Install with: pip install flake8"; \
	fi

# Format code with black
format:
	@echo "Formatting code..."
	@if command -v black >/dev/null 2>&1; then \
		black --line-length=100 --exclude='venv|build|archive' .; \
	else \
		echo "black not installed. Install with: pip install black"; \
	fi

# Clean build artifacts and cache
clean:
	@echo "Cleaning build artifacts and cache files..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.spec
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✓ Cleanup complete"

# Quick development setup
setup: install
	@echo "Setting up development environment..."
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3.11 -m venv venv; \
		echo "✓ Virtual environment created"; \
		echo ""; \
		echo "Activate with: source venv/bin/activate"; \
	else \
		echo "Virtual environment already exists"; \
	fi

# Show project info
info:
	@echo "Project Information"
	@echo "==================="
	@echo "Name:        Access Ability Arm"
	@echo "Description: Assistive robotic arm control application"
	@echo "Python:      3.11 (required)"
	@echo ""
	@echo "Features:"
	@echo "  ✓ YOLOv11 object detection and segmentation"
	@echo "  ✓ MediaPipe face tracking"
	@echo "  ✓ Intel RealSense depth sensing (optional)"
	@echo "  ✓ Cross-platform GUI (Flet)"
	@echo "  ✓ Apple Metal GPU acceleration (macOS)"
	@echo ""
	@echo "Run 'make help' for available commands"

# Install CocoaPods dependencies (macOS/iOS)
pod-install:
	@echo "Installing CocoaPods dependencies..."
	@export PATH="/opt/homebrew/opt/ruby/bin:/opt/homebrew/lib/ruby/gems/3.4.0/bin:$$PATH" && \
	if [ -f "build/flutter/macos/Podfile" ]; then \
		echo "Installing macOS pods..."; \
		cd build/flutter/macos && pod install; \
	fi && \
	if [ -f "build/flutter/ios/Podfile" ]; then \
		echo "Installing iOS pods..."; \
		cd build/flutter/ios && pod install; \
	fi
	@echo "✓ CocoaPods installation complete"

# Run flutter doctor
flutter-doctor:
	@flutter doctor -v
