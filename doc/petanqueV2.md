# PetanqueV2

## Installation

**mathcomp**: follow the guidelines [here](mathcomp_installation.md), then do
```console
opam pin add rocq-mathcomp-boot rocq-mathcomp-order rocq-mathcomp-fingroup rocq-mathcomp-algebra rocq-mathcomp-solvable rocq-mathcomp-field rocq-mathcomp-character https://github.com/theostos/math-comp.git
opam pin add coq-mathcomp-boot coq-mathcomp-order coq-mathcomp-fingroup coq-mathcomp-algebra coq-mathcomp-solvable coq-mathcomp-field coq-mathcomp-character https://github.com/theostos/math-comp.git
```

**coq-lsp**:
```console
opam pin add coq-lsp https://github.com/ejgallego/coq-lsp.git#v8.20
```

**pytanque**:
```console
uv pip install git+https://github.com/LLM4Rocq/pytanque.git@PetanqueV2
```

## New features

- the command `run(state, command)` replaces the command `run_tac(state, tac)`
- states now have a new field `feedback` containing all messages sent by Rocq when computing this state; one can find errors, warnings, results from `Search`, `Print`, ...
- the command `get_root_state(doc)` returns the first state of `doc`
- the command `get_state_at_pos(doc, line, char, offset)` returns the state at a given position
- the command `ast(state, command)` returns the AST of `command` parsed at `state`
- the command `ast_at_pos(doc, line, char, offset)` returns the AST at a given position
