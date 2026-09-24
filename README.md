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
| `claude/` | `~/.claude/` | Claude Code settings, hooks, output styles, skills |
| `Brewfile` | — | `brew bundle` manifest: formulae, casks, VS Code extensions |

## Three layers

- **Homebrew** (`Brewfile`) — apps and system CLIs.
- **mise** (`mise/config.toml`) — language runtimes: python, node, uv.
  Infra CLIs (terraform, awscli) stay on Homebrew globally and are pinned
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
