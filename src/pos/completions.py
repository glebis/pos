"""Shell completion scripts for pos (zsh / bash / fish).

The scripts are thin: for dynamic candidates they shell out to `pos __list <kind>`
(a hidden command), so completions always reflect the live manifest, settings, and
open workspaces without regenerating the script.
"""

# Top-level verbs offered as the first argument.
COMMANDS = [
    "cc", "where", "solo", "tmuxify", "spread", "tile", "gather", "sort",
    "new", "rename", "rm", "config", "status", "p", "open", "sidecar",
    "yard", "day", "load", "completions", "help",
]

LIST_KINDS = ["commands", "focuses", "projects", "workspaces", "settings"]

ZSH = r"""#compdef pos
_pos() {
  if (( CURRENT == 2 )); then
    local -a cmds; cmds=(${(f)"$(pos __list commands)"})
    _describe 'pos command' cmds
    return
  fi
  case ${words[2]} in
    cc) compadd -- ${(f)"$(pos __list focuses)"} ;;
    p|load) compadd -- ${(f)"$(pos __list projects)"} ${(f)"$(pos __list focuses)"} ;;
    new|rename|rm) compadd -- ${(f)"$(pos __list workspaces)"} ;;
    config) (( CURRENT == 3 )) && compadd -- show ${(f)"$(pos __list settings)"} ;;
    completions) (( CURRENT == 3 )) && compadd -- zsh bash fish ;;
  esac
}
_pos "$@"
"""

BASH = r"""_pos() {
  local cur cmd
  cur="${COMP_WORDS[COMP_CWORD]}"
  if [ "$COMP_CWORD" -eq 1 ]; then
    COMPREPLY=( $(compgen -W "$(pos __list commands)" -- "$cur") ); return
  fi
  cmd="${COMP_WORDS[1]}"
  case "$cmd" in
    cc) COMPREPLY=( $(compgen -W "$(pos __list focuses)" -- "$cur") );;
    p|load) COMPREPLY=( $(compgen -W "$(pos __list projects) $(pos __list focuses)" -- "$cur") );;
    new|rename|rm) COMPREPLY=( $(compgen -W "$(pos __list workspaces)" -- "$cur") );;
    config) COMPREPLY=( $(compgen -W "show $(pos __list settings)" -- "$cur") );;
    completions) COMPREPLY=( $(compgen -W "zsh bash fish" -- "$cur") );;
  esac
}
complete -F _pos pos
"""

FISH = r"""# pos fish completions
complete -c pos -f
complete -c pos -n '__fish_use_subcommand' -a '(pos __list commands)'
complete -c pos -n '__fish_seen_subcommand_from cc' -a '(pos __list focuses)'
complete -c pos -n '__fish_seen_subcommand_from p load' -a '(pos __list projects) (pos __list focuses)'
complete -c pos -n '__fish_seen_subcommand_from new rename rm' -a '(pos __list workspaces)'
complete -c pos -n '__fish_seen_subcommand_from config' -a 'show (pos __list settings)'
complete -c pos -n '__fish_seen_subcommand_from completions' -a 'zsh bash fish'
"""

SCRIPTS = {"zsh": ZSH, "bash": BASH, "fish": FISH}

INSTALL_HINT = {
    "zsh": "# install: pos completions zsh > ~/.zfunc/_pos   (ensure `fpath+=~/.zfunc` and `autoload -U compinit && compinit` in ~/.zshrc)",
    "bash": "# install: pos completions bash > ~/.local/share/bash-completion/completions/pos   (or source it in ~/.bashrc)",
    "fish": "# install: pos completions fish > ~/.config/fish/completions/pos.fish",
}


def script(shell: str) -> str | None:
    return SCRIPTS.get(shell)
