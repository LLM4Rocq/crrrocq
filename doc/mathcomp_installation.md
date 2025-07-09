# Mathcomp installation

**rocq**:
```
$ opam install coq.8.20.0
$ opam repo add rocq-released https://rocq-prover.org/opam/released
```

**hierachy builder**:
```
$ opam install coq-hierarchy-builder.1.9.1
```

**mathcomp**:
```
$ git clone https://github.com/theostos/math-comp.git export/mathcomp
$ opam pin add rocq-mathcomp-boot rocq-mathcomp-order rocq-mathcomp-fingroup rocq-mathcomp-algebra rocq-mathcomp-solvable rocq-mathcomp-field rocq-mathcomp-character export/mathcomp
$ opam pin add coq-mathcomp-boot coq-mathcomp-order coq-mathcomp-fingroup coq-mathcomp-algebra coq-mathcomp-solvable coq-mathcomp-field coq-mathcomp-character export/mathcomp
```
