"""Desktop entry point for the guided local installer."""
from .setup_wizard import Application, main

__all__ = ['Application', 'main']

if __name__ == '__main__':
    main()
