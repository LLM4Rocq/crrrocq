(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise7.v*)
From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect ssralg poly ssrnum ssrint rat intdiv.
From mathcomp Require Import zify ring lra.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

Import GRing.Theory.
(**
  ----
  ** Triangular number from Exercise session 2

Use the [lia] and [nia] tactics to prove the following lemmas.
*)
Definition delta (n : nat) := (n.+1 * n)./2.

Lemma deltaS (n : nat) : delta n.+1 = delta n + n.+1.
Proof.
Admitted.

Lemma leq_delta (m n : nat) : m <= n -> delta m <= delta n.
Proof.
Admitted.

(** Use induction and the [lia] tactic to prove the following lemma. *)

Lemma delta_square (n : nat) : (8 * delta n).+1 = n.*2.+1 ^ 2.
Proof.
Admitted.
(**
  ----
  ** Exercise 4 from Excersise session 3

Use induction and the [nia] tactic to prove the following lemmas.
*)
Lemma gauss_ex_nat1 (n : nat) : (\sum_(i < n) i).*2 = n * n.-1.
Proof.
Admitted.

Lemma gauss_ex_nat2 (n : nat) : \sum_(i < n) i = (n * n.-1)./2.
Proof.
Admitted.
(**
Use induction and the [ring] tactic to prove the following lemma (it is also
possible to use [lia] though).

_NB_: there is a bug in the [ring] tactic of Algebra Tactics that it does not
recognize [_.+1] (successor) inside [_%:R] (generic embedding of natural numbers
to ring). You have to explicitly rewrite it by the [natr1] lemma for now.
*)
Lemma gauss_ex_int1 (n : nat) (m : int) :
  ((\sum_(i < n) (m + i%:R)) * 2 = (m * 2 + n%:R - 1) * n%:R)%R.
Proof.
Admitted.
(**
  ----
  ** Pyramidal numbers

Use induction and the [nia] tactic to prove the following lemmas.
*)
Lemma sum_squares_p1 (n : nat) :
  (\sum_(i < n) i ^ 2) * 6 = n.-1 * n * (n * 2).-1.
Proof.
Admitted.

Lemma sum_squares_p2 (n : nat) :
  \sum_(i < n) i ^ 2 = (n.-1 * n * (n * 2).-1) %/ 6.
Proof.
Admitted.

Lemma sum_cubes_p1 (n : nat) : (\sum_(i < n) i ^ 3) * 4 = (n * n.-1) ^ 2.
Proof.
Admitted.
(**
Use induction and the [lia] tactic to prove the following lemma.

_NB_: Apparently, [nia] is not powerful enough to deal with nonlinearity and
Euclidean division by 2 at the same time in this problem. You have to deal with
Euclidean division by 2 manually.
*)
Lemma sum_cubes_p2 (n : nat) : \sum_(i < n) i ^ 3 = ((n * n.-1) %/ 2) ^ 2.
Proof.
Admitted.
(**
  ----
  ** Polynomials

Use the [ring] tactic to prove the following lemma.

_NB_: the [ring] tactic does not directly support the scalar multiplication
operator [(_ *: _)]. You have to explicitly rewrite them.
*)
Lemma polyeq_p1 (R : comRingType) :
  (4 *: 'X^3 - 3 *: 'X + 1)%R = (('X + 1) * (2 *: 'X - 1) ^+ 2)%R :> {poly R}.
Proof.
rewrite -!mul_polyC; ring.
Qed.