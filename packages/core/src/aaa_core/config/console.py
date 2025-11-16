"""
Console output formatting utilities
Provides colored output for better readability
"""


class Colors:
    """ANSI color codes for terminal output"""
    # Standard colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Formatting
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    # Reset
    RESET = '\033[0m'

    @staticmethod
    def disable():
        """Disable colors (for non-TTY environments)"""
        Colors.BLACK = ''
        Colors.RED = ''
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.BLUE = ''
        Colors.MAGENTA = ''
        Colors.CYAN = ''
        Colors.WHITE = ''
        Colors.BRIGHT_BLACK = ''
        Colors.BRIGHT_RED = ''
        Colors.BRIGHT_GREEN = ''
        Colors.BRIGHT_YELLOW = ''
        Colors.BRIGHT_BLUE = ''
        Colors.BRIGHT_MAGENTA = ''
        Colors.BRIGHT_CYAN = ''
        Colors.BRIGHT_WHITE = ''
        Colors.BOLD = ''
        Colors.DIM = ''
        Colors.ITALIC = ''
        Colors.UNDERLINE = ''
        Colors.RESET = ''


def success(message):
    """Print success message in green with checkmark"""
    print(f"{Colors.BRIGHT_GREEN}✓{Colors.RESET} {Colors.GREEN}{message}{Colors.RESET}")


def error(message):
    """Print error message in red with X"""
    print(f"{Colors.BRIGHT_RED}✗{Colors.RESET} {Colors.RED}{message}{Colors.RESET}")


def warning(message):
    """Print warning message in yellow with warning symbol"""
    print(f"{Colors.BRIGHT_YELLOW}⚠{Colors.RESET} {Colors.YELLOW}{message}{Colors.RESET}")


def info(message):
    """Print info message in cyan"""
    print(f"{Colors.BRIGHT_CYAN}ℹ{Colors.RESET} {Colors.CYAN}{message}{Colors.RESET}")


def header(message):
    """Print header message in bold bright white"""
    print(f"{Colors.BOLD}{Colors.BRIGHT_WHITE}{message}{Colors.RESET}")


def status(message):
    """Print status message in blue"""
    print(f"{Colors.BLUE}{message}{Colors.RESET}")


def underline(text):
    """Return text with underline formatting (preserves surrounding color)"""
    # Use \033[24m to turn off underline only, not all formatting
    return f"{Colors.UNDERLINE}{text}\033[24m"


# Auto-disable colors if not in a TTY
import sys  # noqa: E402

if not sys.stdout.isatty():
    Colors.disable()
