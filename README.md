# dotfiles

Personal macOS terminal setup. Clone and run one script on a new machine.

```sh
git clone git@github.com:<you>/dotfiles.git ~/dotfiles
~/dotfiles/bootstrap.sh
exec zsh
```

`bootstrap.sh` is idempotent — re-run it any time. It never deletes anything:
existing files are moved to `~/.dotfiles-backup-<timestamp>/` before being
replaced with symlinks back into this repo, so edits here take effect live.

## Layout

| Path | Links to | What |
|---|---|---|
| `home/.zshrc` | `~/.zshrc` | oh-my-zsh config, plugin list, key bindings, mise activation |
| `home/.vimrc` | `~/.vimrc` | vim settings |
| `home/.tmux.conf` | `~/.tmux.conf` | tmux settings |
| `home/.gitconfig` | `~/.gitconfig` | aliases + include of the local identity file |
| `config/git/ignore` | `~/.config/git/ignore` | global gitignore |
| `mise/config.toml` | `~/.config/mise/config.toml` | global runtime versions |
| `iterm2/dotfiles.json` | `~/Library/Application Support/iTerm2/DynamicProfiles/` | iTerm2 profile using the Meslo Nerd Font (set as default) |
| `cmux/cmux.json` | `~/.config/cmux/cmux.json` | cmux: only localhost dev URLs open in the embedded browser; SSO/GitHub links go to the default browser |
| `claude/` | `~/.claude/` | Claude Code settings, CLAUDE.md, output styles, hooks |
| `Brewfile` | — | `brew bundle` manifest: formulae and casks |

## Three layers

- **Homebrew** (`Brewfile`) — apps and system CLIs.
- **mise** (`mise/config.toml`) — language runtimes: python, node, uv.
  Infra CLIs (terraform) stay on Homebrew globally and are pinned
  per-repo in each project's own `mise.toml`, which always wins over the global.
- **This repo** — the config files themselves.

## Machine-local overrides

Two untracked files, both optional, both applied last so they win:

- `~/.gitconfig.local` — name/email. `bootstrap.sh` seeds it from
  `home/.gitconfig.local.example` if absent. Use a client address here on a
  client machine rather than editing the tracked `.gitconfig`.
- `~/.zshrc.local` — machine-specific env vars and PATH entries.

## oh-my-zsh

Not vendored — `bootstrap.sh` installs it and clones the two custom plugins
that `.zshrc` references (`zsh-autosuggestions`,
`zsh-history-substring-search`). The other plugins in the list (`git`,
`gitfast`, `fzf`, `tmux`) ship with oh-my-zsh. Theme is `amuse`, built in.

## Claude Code

- `claude/hooks/zsh-history.py` appends the `!` commands you type in Claude Code
  to `~/.zsh_history`, so up-arrow substring search finds them alongside your
  own. Commands Claude runs on its own are left out. A `!` command lands in
  history at your next prompt, when Claude finishes a turn, or when the session
  ends, stamped with the time you ran it.
- The `ccgrep` plugin adds a `ccgrep` skill that finds past Claude Code sessions
  by what was said in them and gives the `claude --resume <id>` command. It comes
  from a private claude.ai org marketplace, so it is not vendored and the
  marketplace is not named here. To have bootstrap install it, put
  `export CCGREP_MARKETPLACE=<marketplace CLI name>` in `~/.zshrc.local` (the name
  is shown by `claude plugin marketplace list`). Unset, bootstrap skips it; if the
  install fails, bootstrap warns and carries on.

## Deliberately not here

Credentials and machine state: `~/.ssh`, `~/.aws`, `~/.config/op`,
`~/.config/gcloud`, `~/.claude.json`, `~/.claude/projects`,
`~/.claude/plugins`, shell history.

`claude/settings.json` is committed with the `autoMode` block stripped — it
holds environment detail Claude derives from whatever machine it runs on
(local repo paths, shell history, remotes), regenerates automatically, and is
not portable config.

Since that file is symlinked into `~/.claude`, Claude rewrites the block
constantly and would leave the tree permanently dirty. `bin/strip-automode` is
a git clean filter (registered by `bootstrap.sh`, wired up in `.gitattributes`)
that removes it whenever git reads the file, so the noise is invisible while
genuine setting changes — a new `model`, a changed hook — still show up in
`git status` as normal.

The `quarterdeck` skill is distributed internally and is not vendored here.
