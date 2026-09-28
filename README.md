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
| `claude/` | `~/.claude/` | Claude Code CLAUDE.md, output styles, hooks (symlinked) and settings.json (copied) |
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

- `claude/hooks/zsh-history.py` appends every Bash command Claude runs to
  `~/.zsh_history`, so up-arrow substring search finds them alongside your own.
- The ECC plugin is optional: `bootstrap.sh` asks before installing it
  (`INSTALL_ECC=1` or `INSTALL_ECC=0` answers without prompting). To remove it later:
  `claude plugin uninstall ecc@ecc && claude plugin marketplace remove ecc`.

## Deliberately not here

Credentials and machine state: `~/.ssh`, `~/.aws`, `~/.config/op`,
`~/.config/gcloud`, `~/.claude.json`, `~/.claude/projects`,
`~/.claude/plugins`, shell history.

`claude/settings.json` is committed with the `autoMode` block stripped — it
holds environment detail Claude derives from whatever machine it runs on
(local repo paths, shell history, remotes), regenerates automatically, and is
not portable config.

Unlike everything else, `claude/settings.json` is **copied** to
`~/.claude/settings.json`, not symlinked: Claude Code rewrites that file itself
(and replaces a symlink with a regular file when it does). `bootstrap.sh` only
copies it when `~/.claude/settings.json` is missing, and warns instead of
overwriting when a local copy differs. To publish a local change, copy the
file back into the repo; `bin/strip-automode`, a git clean filter registered by
`bootstrap.sh` and wired up in `.gitattributes`, drops the `autoMode` block as
git reads it so it never gets committed.

The `quarterdeck` skill is distributed internally and is not vendored here.
