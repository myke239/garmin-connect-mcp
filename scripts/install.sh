#!/bin/sh
set -eu
umask 077
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_dir="${GARMIN_INSTALL_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/application}"
case "$install_dir" in /*) ;; *) echo "Installation directory must be absolute" >&2; exit 1 ;; esac
if command -v uv >/dev/null 2>&1; then
    uv_bin=$(command -v uv)
elif [ -x "$install_dir/tools/uv" ]; then
    uv_bin="$install_dir/tools/uv"
else
    mkdir -p "$install_dir/tools"
    curl --fail --show-error --location --proto '=https' --tlsv1.2 https://astral.sh/uv/install.sh -o "$install_dir/tools/install-uv.sh"
    UV_INSTALL_DIR="$install_dir/tools" UV_NO_MODIFY_PATH=1 sh "$install_dir/tools/install-uv.sh"
    uv_bin="$install_dir/tools/uv"
fi
export UV_SYSTEM_CERTS=true
export UV_PYTHON_PREFERENCE=only-managed
export UV_CACHE_DIR="$install_dir/cache"
export UV_PYTHON_INSTALL_DIR="$install_dir/python"
exec "$uv_bin" run --no-project --python 3.13 "$script_dir/install.py" --uv "$uv_bin" --install-dir "$install_dir" "$@"
