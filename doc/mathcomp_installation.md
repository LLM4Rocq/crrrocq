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

$ opam pin add rocq-mathcomp-boot https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-order https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-fingroup https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-algebra https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-solvable https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-field https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-character https://github.com/theostos/math-comp.git
$ opam pin add rocq-mathcomp-ssreflect https://github.com/theostos/math-comp.git
```
