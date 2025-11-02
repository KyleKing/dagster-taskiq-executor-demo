# shellcheck shell=zsh
# Utility helpers for running long-lived commands safely in automation contexts.
# Source this file from zsh to access the `agent::run` helper.
#
# Example:
#   source scripts/agent.zsh
#   agent::run -- env PULUMI_CONFIG_PASSPHRASE=localstack uv run pulumi up --stack local --yes --non-interactive

if [[ -z ${ZSH_VERSION-} ]]; then
  printf 'agent.zsh must be sourced from zsh\n' >&2
  return 1
fi

function agent::run() {
  emulate -L zsh
  set -o pipefail

  local inactivity=600
  local hard_timeout=0
  local line_limit=100
  local char_limit=10000

  zmodload -F zsh/stat b:zstat
  zmodload zsh/datetime

  local OPTIND=1 opt
  while getopts ":i:t:l:c:" opt; do
    case $opt in
      i) inactivity=$OPTARG ;;
      t) hard_timeout=$OPTARG ;;
      l) line_limit=$OPTARG ;;
      c) char_limit=$OPTARG ;;
      *) print -u2 "agent::run: invalid option -$OPTARG"; return 2 ;;
    esac
  done
  shift $(( OPTIND - 1 ))
  if [[ ${1-} == -- ]]; then
    shift
  fi

  (( $# )) || { print -u2 "usage: agent::run [options] -- <command> [...args]"; return 2 }

  local temp_file
  temp_file=$(mktemp -t agent-run.XXXXXX) || return 1

  "$@" >"$temp_file" 2>&1 &
  local cmd_pid=$!
  local rc=0
  local last_size=0
  local start=$EPOCHREALTIME
  local last_activity=$start

  while kill -0 $cmd_pid 2>/dev/null; do
    sleep 2
    if zstat -H stat "$temp_file" 2>/dev/null; then
      local current_size=${stat[size]}
      if (( current_size > last_size )); then
        last_size=$current_size
        last_activity=$EPOCHREALTIME
      fi
    fi

    local now=$EPOCHREALTIME

    if (( hard_timeout > 0 && now - start > hard_timeout )); then
      print -u2 "agent::run: hard timeout (${hard_timeout}s) reached; terminating command."
      rc=124
      kill $cmd_pid 2>/dev/null || true
      break
    fi

    if (( now - last_activity > inactivity )); then
      print -u2 "agent::run: no output for ${inactivity}s; terminating command."
      rc=125
      kill $cmd_pid 2>/dev/null || true
      break
    fi
  done

  local wait_rc=0
  if ! wait $cmd_pid 2>/dev/null; then
    wait_rc=$?
  fi
  if (( rc == 0 && wait_rc != 0 )); then
    rc=$wait_rc
  fi

  local truncated=0
  local data
  data=$(tail -c "$char_limit" "$temp_file" 2>/dev/null || true)

  local total_lines
  total_lines=$(printf '%s' "$data" | wc -l | tr -d ' ')
  if (( total_lines > line_limit )); then
    data=$(printf '%s' "$data" | tail -n "$line_limit")
    truncated=1
  fi

  local total_chars
  total_chars=$(printf '%s' "$data" | wc -c | tr -d ' ')
  if (( total_chars > char_limit )); then
    data=$(printf '%s' "$data" | tail -c "$char_limit")
    truncated=1
  fi

  if (( truncated )); then
    print -u2 "agent::run: output truncated to last ${line_limit} lines / ${char_limit} characters."
  fi

  printf '%s' "$data"
  [[ "$data" == *$'\n' ]] || printf '\n'

  rm -f -- "$temp_file"

  return $rc
}

