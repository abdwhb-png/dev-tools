# Durable Powerlevel10k overrides for reliable pane resizing in WezTerm.
#
# This file is intentionally separate from ~/.p10k.zsh because `p10k configure`
# regenerates that file. Keep this file sourced after ~/.p10k.zsh in ~/.zshrc.

# Use one physical prompt line. The previous command duration appears only when
# it reaches POWERLEVEL9K_COMMAND_EXECUTION_TIME_THRESHOLD (3 seconds by default).
typeset -g POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(
  time
  os_icon
  dir
  vcs
  command_execution_time
  prompt_char
)

# A right prompt was the unstable part during split-pane resize tests.
typeset -g POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=()

# Keep a compact clock without the generated "at " prefix.
typeset -g POWERLEVEL9K_TIME_FORMAT='%D{%H:%M}'
typeset -g POWERLEVEL9K_TIME_PREFIX=

# Apply overrides when this file is sourced after Powerlevel10k initialization.
(( ! $+functions[p10k] )) || p10k reload
