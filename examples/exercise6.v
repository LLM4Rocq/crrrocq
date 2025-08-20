(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise6.v*)
From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect.
From mathcomp Require Import all_algebra.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

(** *** Exercices on polynomials
- Formalisation of the algebraic  part of  a                          
 simple proof that PI is irrational  described in:                   
- http://projecteuclid.org/download/pdf_1/euclid.bams/1183510788    
*)  

Section Algebraic_part.

Open Scope ring_scope.
Import GRing.Theory Num.Theory.

(** *** Parameters definitions:
- Let n na nb be  natural numbers
- Suppose nb is a non zero nat: nb != 0
- Define the corresponding rationals a , b 
- Define pi as a/b.
*)
(* to complete  for na nb*)
Variable n : nat.
Hypothesis nbne0: nb != 0%N.

Definition a:rat := (Posz na)%:~R.
Definition b:rat := 

Definition pi := 

(** *** Definition of the polynomials:
-  Look at the f definition: the factorial, the coercion nat :> R (as a Ring), etc...
- Define F:{poly rat} using bigop.
*)
Definition f :{poly rat} := 
  (n`!)%:R^-1 *: ('X^n * (a%:P -  b*:'X)^+n).



(** *** Prove that:
- b is non zero rational.
*)
(* Some intermediary simple theorems *)
Lemma bne0: b != 0.
(** *** Prove that:
-  (a -  bX) has a size of 2
*)
Lemma P1_size: size (a%:P -  b*:'X) = 2%N.
Proof.
Qed.

(** *** Prove that:
-  the lead_coef of (a -  bX) is -b.
*)
Lemma P1_lead_coef: lead_coef (a%:P -  b*:'X) = -b.
Proof.
Qed.

(** *** Prove that:
-  the size of (a-X)^n is n.+1
*)
Lemma P_size : size ((a%:P -  b*:'X)^+n)  = n.+1.
Qed.

(* 2 useful lemmas for the  Qint predicat. *)
Lemma int_Qint (z:int) : z%:~R \is a Qint.
Proof. by apply/QintP; exists z. Qed.

Lemma nat_Qint (m:nat) : m%:R \is a Qint.
Proof. by apply/QintP; exists m. Qed.

(** *** Prove that:
- Exponent and composition of polynomials combine:
*)
Lemma comp_poly_exprn: 
   forall (p q:{poly rat}) i, p^+i \Po q = (p \Po q) ^+i.
Qed.


(** *** Prove that:
- f's small coefficients are zero
*)
(* Let's begin the Niven proof *)
Lemma f_small_coef0 i: (i < n)%N -> f`_i = 0.
Proof.
Qed.

(** *** Prove that:
- f/n! as integral coefficients 
*)

Lemma f_int i: (n`!)%:R * f`_i \is a Qint.
Proof.
Qed.

(** *** Prove that:
the f^`(i) (x) have integral values for x = 0
*)
Lemma derive_f_0_int: forall i, f^`(i).[0] \is a Qint.
Proof.
Qed.

(** *** Deduce that:
F (0) has an integral value
*)

Lemma F0_int : F.[0] \is a Qint.
Proof.
Qed.

(** *** Then prove 
- the symmetry argument f(x) = f(pi -x).
*)
Lemma pf_sym:  f \Po (pi%:P -'X) = f.
Proof.
Qed.

(** *** Prove 
- the symmetry for the derivative 
*)

Lemma  derivn_fpix i :
      (f^`(i)\Po(pi%:P -'X))= (-1)^+i *: f^`(i).
Proof.
Qed.

(** *** Deduce that
- F(pi) is an integer 
*)
Lemma FPi_int : F.[pi] \is a Qint.
Proof.
Qed.


(** *** if you have time
- you can prove the  equality  F^`(2) + F = f 
- that is  needed by the analytic part of the Niven proof
*)

Lemma D2FDF : F^`(2) + F = f.
Proof.
Qed.

End Algebraic_part.
