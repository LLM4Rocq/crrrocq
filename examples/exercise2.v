(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise2.v*)
From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(** Elements *)

Definition elements {A} (f : _ -> A) n :=
  let l := iota 0 n.+1 in zip l (map f l).

(** Triangular number *)
Definition delta n := (n.+1 * n)./2.

Lemma deltaE n : delta n =  (n.+1 * n)./2.
Proof. by []. Qed.

Lemma delta1 : delta 1 = 1.
Proof. by []. Qed.


Compute elements delta 10.

(** Hints : halfD half_bit_double *)
Lemma deltaS n : delta n.+1 = delta n + n.+1.
Proof.
Admitted.


(* Hints half_leq *)
Lemma leq_delta m n : m <= n -> delta m <= delta n.
Proof.
Admitted.

(** Hints sqrnD *)
Lemma delta_square n : (8 * delta n).+1 = n.*2.+1 ^ 2.
Proof.
Admitted.

(**  Triangular root *)
Definition troot n := 
 let l := iota 0 n.+2 in
 (find (fun x => n < delta x) l).-1.

Lemma trootE n :
  troot n = (find (fun x => n < delta x) (iota 0 n.+2)).-1.
Proof. by []. Qed.

Compute elements troot 10.

Lemma troot_gt0 n : 0 < n -> 0 < troot n.
Proof.
Admitted.

(** Hints before_find find_size size_iota nth_iota *)
Lemma leq_delta_root m : delta (troot m) <= m.
Proof.
Admitted.

(** Hints hasP mem_iota half_bit_double half_leq nth_find nth_iota *)
Lemma ltn_delta_root m : m < delta (troot m).+1.
Proof.
Admitted.

Lemma leq_root_delta m n : (n <= troot m) = (delta n <= m).
Proof.
Admitted.

Lemma leq_troot m n : m <= n -> troot m <= troot n.
Proof.
Admitted.

Lemma troot_delta m n : (troot m == n) = (delta n <= m < delta n.+1).
Proof.
Admitted.

Lemma troot_deltaK n : troot (delta n) = n.
Proof.
Admitted.

(**  The modulo for triangular numbers *)
Definition tmod n := n - delta (troot n).

Lemma tmodE n : tmod n = n - delta (troot n).
Proof. by []. Qed.

Lemma tmod_delta n : tmod (delta n) = 0.
Proof.
Admitted.

Lemma delta_tmod n : n = delta (troot n) + tmod n.
Proof.
Admitted.

Lemma leq_tmod_troot n : tmod n <= troot n.
Proof.
Admitted.

Lemma ltn_troot m n : troot m < troot n -> m < n.
Proof.
Admitted.

Lemma leq_tmod m n : troot m = troot n -> (tmod m <= tmod n) = (m <= n).
Proof.
Admitted.

Lemma leq_troot_mod m n : 
   m <= n = 
   ((troot m < troot n) || ((troot m == troot n) && (tmod m <= tmod n))).
Proof.
       by rewrite dnEdm leq_add2l.
Admitted.

(** Fermat Numbers *)

Definition fermat n := (2 ^ (2 ^ n)).+1.

Lemma fermatE n : fermat n = (2 ^ (2 ^ n)).+1.
Proof. by []. Qed.

Compute elements (prime \o fermat) 4.

(** Hints : subn_sqr subnBA odd_double_half *)
Lemma dvd_exp_odd a k : 
  0 < a -> odd k -> a.+1 %| (a ^ k).+1.
Proof.
move=> aP kO.
Admitted.

(** Hints: logn_gt0 mem_primes dvdn2 *)
Lemma odd_log_eq0 n : 0 < n -> logn 2 n = 0 -> odd n.
Proof.
Admitted.

(** Hints pfactor_dvdnn logn_div pfactorK *)
Lemma odd_div_log n : 0 < n -> odd (n %/ 2 ^ logn 2 n).
Proof.
Admitted.

(** Hints divnK pfactor_dvdnn prime_nt_dvdP prime_nt_dvdP *)
Lemma prime_2expS m : 
  0 < m -> prime (2 ^ m).+1 -> m = 2 ^ logn 2 m.
Proof.
Admitted.

(** Hints oddX neq_ltn expn_gt0 *)
Lemma odd_fermat n : odd (fermat n).
Proof.
Admitted.

(** Hint subn_sqr *)
Lemma dvdn_exp2m1 a k : a.+1 %| (a ^ (2 ^ k.+1)).-1.
Proof.
Admitted.

(** Hints subnK expnD expnM *)
Lemma dvdn_fermat m n : m < n -> fermat m %| (fermat n).-2.
Proof.
Admitted.

Lemma fermat_gt1 n : 1 < fermat n.
Proof.
Admitted.

(** Hints gcdnMDl coprimen2 *)
Lemma coprime_fermat m n : m < n -> coprime (fermat m) (fermat n).
Proof.
Admitted.


