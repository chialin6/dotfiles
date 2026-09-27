#!/usr/bin/env bash
#
# Idempotent setup for a fresh macOS machine. Safe to re-run.
#
#   git clone <this repo> ~/dotfiles && ~/dotfiles/bootstrap.sh
#
# Existing regular files are moved to ~/.dotfiles-backup-<timestamp>/ before
# being replaced by symlinks; nothing is deleted.

set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$HOME/.dotfiles-backup-$(date +%Y%m%d-%H%M%S)"
ZSH_DIR="$HOME/.oh-my-zsh"
ZSH_CUSTOM="$ZSH_DIR/custom"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }

# link <source-in-repo> <target-path>
link() {
  local src="$DOTFILES/$1" dst="$2"
  [ -e "$src" ] || { warn "missing in repo, skipped: $1"; return; }
  mkdir -p "$(dirname "$dst")"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
    return                                  # already correct
  fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then   # back up whatever is there
    mkdir -p "$BACKUP/$(dirname "${dst#"$HOME"/}")"
    mv "$dst" "$BACKUP/${dst#"$HOME"/}"
    warn "backed up existing $dst"
  fi
  ln -sfn "$src" "$dst"
  echo "    $dst -> $src"
}

# ---------------------------------------------------------------- 1. Homebrew
if ! command -v brew >/dev/null 2>&1; then
  info "Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
# Apple silicon installs to /opt/homebrew and is not on PATH until shellenv runs
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

info "Installing packages from Brewfile"
brew bundle --file="$DOTFILES/Brewfile" || warn "brew bundle had failures (see above) - continuing"

# ------------------------------------------------------------- 2. oh-my-zsh
if [ ! -d "$ZSH_DIR" ]; then
  info "Installing oh-my-zsh"
  # --unattended: don't run zsh or touch .zshrc; we supply our own below
  RUNZSH=no KEEP_ZSHRC=yes sh -c \
    "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
else
  info "oh-my-zsh already present"
fi

info "Installing oh-my-zsh custom plugins"
# These are the two non-bundled plugins referenced in .zshrc's plugins=(...) list.
# The rest (git, gitfast, fzf, tmux) ship with oh-my-zsh itself.
clone_plugin() {
  local url="$1" dest="$ZSH_CUSTOM/plugins/$2"
  if [ -d "$dest" ]; then
    echo "    $2 already present"
  else
    git clone --depth=1 "$url" "$dest"
  fi
}
mkdir -p "$ZSH_CUSTOM/plugins"
clone_plugin https://github.com/zsh-users/zsh-autosuggestions           zsh-autosuggestions
clone_plugin https://github.com/zsh-users/zsh-history-substring-search  zsh-history-substring-search

# ------------------------------------------------- 2b. Git filter for settings
# claude/settings.json is symlinked into ~/.claude, and Claude Code keeps
# rewriting an autoMode.environment block describing whatever machine it runs
# on. This clean filter strips that block when git reads the file, so the
# per-machine noise never dirties the working tree. Filter config is local to
# a clone and is not cloned with it, so it has to be set here.
info "Configuring the settings.json clean filter"
git -C "$DOTFILES" config filter.strip-automode.clean './bin/strip-automode'
git -C "$DOTFILES" config filter.strip-automode.smudge 'cat'

# ------------------------------------------------------------- 3. Symlinks
info "Linking dotfiles"
link home/.zshrc      "$HOME/.zshrc"
link home/.vimrc      "$HOME/.vimrc"
link home/.tmux.conf  "$HOME/.tmux.conf"
link home/.gitconfig  "$HOME/.gitconfig"
link config/git/ignore "$HOME/.config/git/ignore"
link mise/config.toml  "$HOME/.config/mise/config.toml"

info "Linking Claude Code config"
link claude/CLAUDE.md                  "$HOME/.claude/CLAUDE.md"
link claude/settings.json              "$HOME/.claude/settings.json"
link claude/output-styles              "$HOME/.claude/output-styles"

# ------------------------------------------- 3b. iTerm2 status-line helper
# settings.json points several Claude Code hooks at ~/.config/iterm2/cc-status,
# which is a symlink into the iTerm app bundle. Recreate it if iTerm is here.
ITERM_CC_STATUS="/Applications/iTerm.app/Contents/Resources/utilities/cc-status"
if [ -e "$ITERM_CC_STATUS" ]; then
  if [ ! -e "$HOME/.config/iterm2/cc-status" ]; then
    info "Linking iTerm2 cc-status helper"
    mkdir -p "$HOME/.config/iterm2"
    ln -sfn "$ITERM_CC_STATUS" "$HOME/.config/iterm2/cc-status"
  fi
else
  warn "iTerm2 not found - Claude Code status-line hooks will be no-ops until it is installed"
fi

# ------------------------------------------------- 3c. iTerm2 font profile
# iterm2/dotfiles.json is a Dynamic Profile: a "Dotfiles" profile that inherits
# everything from "Default" but uses the Meslo Nerd Font, so the amuse theme's
# git-branch glyph renders. iTerm loads anything in DynamicProfiles on its own.
link iterm2/dotfiles.json "$HOME/Library/Application Support/iTerm2/DynamicProfiles/dotfiles.json"

# Make it the default profile. iTerm keeps its prefs in memory and writes them
# back on quit, so a write made while it is running would be lost.
ITERM_PROFILE_GUID="063C7BE3-25C9-4BFB-92C8-BEE61FDA67FF"
if [ "$(defaults read com.googlecode.iterm2 "Default Bookmark Guid" 2>/dev/null)" != "$ITERM_PROFILE_GUID" ]; then
  if pgrep -xq iTerm2; then
    warn "iTerm2 is running - to use the Nerd Font, pick Settings > Profiles > Dotfiles > Other Actions > Set as Default (or quit iTerm and re-run this script)"
  else
    info "Setting the iTerm2 default profile to Dotfiles"
    defaults write com.googlecode.iterm2 "Default Bookmark Guid" -string "$ITERM_PROFILE_GUID"
  fi
fi

# --------------------------------------------------- 4. Machine-local files
if [ ! -f "$HOME/.gitconfig.local" ]; then
  info "Creating ~/.gitconfig.local from example - edit it with this machine's identity"
  cp "$DOTFILES/home/.gitconfig.local.example" "$HOME/.gitconfig.local"
fi

# ------------------------------------------------------------------ 5. mise
if command -v mise >/dev/null 2>&1; then
  info "Installing global mise tools"
  mise install
else
  warn "mise not found - skipping (brew bundle should have installed it)"
fi

# ----------------------------------------------------------------- 6. Done
info "Done."
[ -d "$BACKUP" ] && warn "Replaced files were backed up to $BACKUP"
cat <<'MSG'

Next steps:
  1. exec zsh                      # reload the shell (activates mise)
  2. mise doctor                   # should now report: activated: yes
  3. edit ~/.gitconfig.local       # set the right name/email for this machine
  4. optional: ~/.zshrc.local      # machine-specific env vars, sourced last

Not handled here (installed separately):
  - Claude Code itself
  - the quarterdeck skill (distributed internally, not vendored in this repo)
MSG
