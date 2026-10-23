# Install on Linux or macOS

[Download the source archive](https://github.com/myke239/garmin-connect-mcp/releases/latest), extract it, then open a terminal in its folder.

```sh
sh scripts/install.sh --remote

garmin="${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/application/bin/garmin-connect"
"$garmin" login
"$garmin" verify
```

**Codex:** run `"$garmin" install-plugin`, then open a new chat. The Codex CLI must be installed.

**ChatGPT:** run `"$garmin" desktop` after installing with `--desktop --remote` if your system has Tk and a display; otherwise follow the [terminal HTTPS setup](chatgpt.md#terminal-setup).

Success: `verify` prints **Saved session verified with Garmin**. In your chosen app, ask **“Summarize my last three activities.”**

[Advanced installation](advanced-installation.md)
