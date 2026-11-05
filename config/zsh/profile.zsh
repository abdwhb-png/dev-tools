# Portable interactive profile; dependencies are installed before activation.
[[ -o interactive ]] || return
export ZSH="${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/zsh/oh-my-zsh"
ZSH_CUSTOM="${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/zsh/custom"
ZSH_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/dev-tools/zsh"
ZSH_THEME="powerlevel10k/powerlevel10k"
zstyle ':omz:update' mode disabled
plugins=(git docker laravel npm python fzf bun zoxide fzf-tab zsh-autosuggestions zsh-syntax-highlighting)
source "$ZSH/oh-my-zsh.sh"
source "${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/zsh/p10k.zsh"
source "${XDG_DATA_HOME:-$HOME/.local/share}/dev-tools/zsh/p10k-resize-safe.zsh"
