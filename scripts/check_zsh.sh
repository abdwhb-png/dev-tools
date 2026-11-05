#!/usr/bin/env bash
# Run on disposable qualification hosts after installing the managed profile.
set -euo pipefail
script -qec 'zsh -lic '\''set -e
[[ $ZSH == ${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/zsh/oh-my-zsh ]]
(( $+functions[p10k] ))
(( $+widgets[fzf-tab-complete] ))
(( $+functions[_zsh_autosuggest_start] ))
(( $+functions[_zsh_highlight] ))
(( $+commands[fzf] && $+commands[zoxide] ))
[[ ${POWERLEVEL9K_LEFT_PROMPT_ELEMENTS[*]} == "time os_icon dir vcs command_execution_time prompt_char" ]]
[[ ${#POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS} == 0 ]]
[[ $(node --version) == "v$DEV_TOOLS_NODE_VERSION" ]]
print -- "Zsh profile verified."
'\''' /dev/null
[[ $(getent passwd "$(id -un)" | cut -d: -f7) == /usr/bin/zsh ]]
[[ $(zsh -lc 'print -r -- noninteractive-ok') == noninteractive-ok ]]
