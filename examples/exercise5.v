(** source https://www-sop.inria.fr/teams/marelle/MC-2022/exercise5.v*)

From elpi Require Import elpi.
From HB Require Import structures.
From mathcomp Require Import all_ssreflect.
From mathcomp Require Import all_algebra.
From mathcomp Require Import all_field.

Set Implicit Arguments.
Unset Strict Implicit.
Unset Printing Implicit Defensive.

Import GRing.Theory Num.Theory UnityRootTheory.
Open Scope ring_scope.

Section PreliminaryLemmas.
(** -------------------------------------------- *)
(** #<div class='slide'>#
* Preliminaries

In this exercise session, we will use complex algebraic numbers
instead of complex numbers. This is for a technical reason, please
think of algebraic numbers as if they were complex numbers, since they
enjoy the same first order theory.

Let's extend the library of algebraic numbers with some easy lemmas
first.

** Question 1: prove that if a sum of natural numbers is 1 then one of its term is 0 and the other is 1

Note that we do not consider nat but the copy of nat which is embeded
in the algebraic numbers algC. The theorem is easy to prove for nat,
so we suggest you use a compatibility lemma numbers between nat and
Cnat

#<div># *)
Lemma Cnat_add_eq1 : {in Cnat &, forall x y,
   (x + y == 1) = ((x == 1) && (y == 0))
               || ((x == 0) && (y == 1))}.
Proof.
Admitted.
(**
#</div>#
** Question 2: The real part of product
#<div>#
*)
Lemma ReM (x y : algC) :
  'Re (x * y) = 'Re x * 'Re y - 'Im x * 'Im y.
Proof.
Admitted.
(**
#</div>#
** Question 3: The imaginary part of product

(it's the same proof except for 2 characters, don't do it if takes more than 5s)
#<div>#
*)
Lemma ImM (x y : algC) :
  'Im (x * y) = 'Re x * 'Im y + 'Re y * 'Im x.
Proof.
Admitted.

End PreliminaryLemmas.
(**
#</div>#
#</div># *)
(** -------------------------------------------- *)
(** #<div class='slide'>#
* The ring of Gaussian integers

References:
 - #<a href="https://en.wikipedia.org/wiki/Gaussian_integer">Gaussian Integer on wikipedia</a>#
 - exercices de mathematiques oraux X-ENS algebre 1, Exercice 3.10. ENS Lyon

Gaussian integers are complex numbers of the form (n + i m) where n and m are integers. We will prove they form a ring, and determine the units of this ring.

#<div>#
*)
Section GaussianIntegers.
(**
#</div>#
- First we define a predicate for the algebraic numbers which are Gaussian integers.
#<div>#
*)
Definition gaussInteger :=
  [pred x : algC | ('Re x \in Cint) && ('Im x \in Cint)].
(**
#</div>#
- You need to use qualifE to reduce (x \ in gaussInteger) to its definition.

** Question 4: Prove that integers are Gaussian integers
#<div>#
*)
Lemma Cint_GI (x : algC) : x \in Cint -> x \in gaussInteger.
Proof.
Admitted.
(** #</div>#
#</div>#
 *)
(** -------------------------------------------- *)
(** #<div class='slide'>#
** Question 5: Prove that Gaussian integers form a subring
#<div>#
*)
Lemma GI_subring : subring_closed gaussInteger.
Proof.
Admitted.
(**
#</div>#
- There follows the boilerplate to use the proof GI_subring in order to canonically provide a subring structure to the predicate gaussInteger.
#<div>#
*)
HB.instance Definition _ :=  GRing.isSubringClosed.Build _ _ GI_subring.
(**
#</div>#
- Finally, we define the type of Gaussian Integer, as a sigma type of algebraic numbers. We soon prove that this is in fact a sub type.
#<div>#
*)
Record GI := GIof { algGI : algC; algGIP : algGI \in gaussInteger }.
Hint Resolve algGIP.
(**
#</div>#

- We provide the subtype property, this makes it possible to use the generic operator "val" to get an algC from a Gaussian Integer.
- Moreover provide a commutative ring structure to the type GI, using the subring canonical property for the predicate gaussInteger

#<div>#
*)
HB.instance Definition _ := [isSub for algGI].
HB.instance Definition _ := [Choice of GI by <:].
HB.instance Definition _ := [SubChoice_isSubComRing of GI by <:].
(**
#</div>#
- We deduce that the real and imaginary parts of a GI are integers
#<div>#
*)
Lemma GIRe (x : GI) : 'Re (val x) \in Cint.
Proof. by have /andP [] := algGIP x. Qed.
Lemma GIIm (x : GI) : 'Im (val x) \in Cint.
Proof. by have /andP [] := algGIP x. Qed.
Hint Resolve GIRe GIIm.

Canonical ReGI x := GIof (Cint_GI (GIRe x)).
Canonical ImGI x := GIof (Cint_GI (GIIm x)).
(**
#</div>#

 - Now we build the unitRing and comUnitRing structure of gauss
   integers. Contrarily to the previous structures, the operator is
   not the same as on algebraics. Indeed the invertible algebraics are
   not necessarily invertible Gaussian integers.

 - Hence, we define the inverse of Gaussian integers as follow : if the
   algebraic inverse happens to be a Gaussian integer we recover the
   proof and package it together with the element and get a gauss
   integer, otherwise, we default to the identity.

 - A Gaussian integer is invertible if the algbraic inverse is a gauss
   integer.
#<div>#
*)
Definition invGI (x : GI) := insubd x (val x)^-1.
Definition unitGI := [pred x : GI | (x != 0)
          && ((val x)^-1 \in gaussInteger)].
(**
#</div>#
#</div># *)
(** -------------------------------------------- *)
(** #<div class='slide'>#

** Question 6: prove a few facts in order to find a comUnitRingMixin for GI, and then instantiate the interfaces of unitRingType and comUnitRingType.

Do only one of the following proofs.

#<div>#
*)
Fact mulGIr : {in unitGI, left_inverse 1 invGI *%R}.
Proof.
Admitted.

Fact unitGIP (x y : GI) : y * x = 1 -> unitGI x.
Proof.
Admitted.

Fact unitGI_out : {in [predC unitGI], invGI =1 id}.
Proof.
move=> x.
Admitted.
HB.instance Definition _ :=
  GRing.ComRing_hasMulInverse.Build GI mulGIr unitGIP unitGI_out.
(**
#</div>#
#<div>#
*)
(** -------------------------------------------- *)
(** #<div class='slide'>#

** Question 7: Show that Gaussian integers are stable by conjugation.

#<div>#
*)
Lemma conjGIE (x : algC) : (x^* \in gaussInteger) = (x \in gaussInteger).
Proof.
Admitted.
(**
#</div>#
- We use this fact to build the conjugation of a Gaussian Integers
#<div>#
*)
Fact conjGI_subproof (x : GI) : (val x)^* \in gaussInteger.
Proof. by rewrite conjGIE. Qed.

Canonical conjGI x := GIof (conjGI_subproof x).
(**
#</div>#
- We now define the norm (stasm) for Gaussian integer, we don't need to specialize it to Gaussian integer so we define it over algebraic numbers instead.
#<div>#
*)
Definition gaussNorm (x : algC) := x * x^*.
Lemma gaussNorm_val (x : GI) : gaussNorm (val x) = val (x * conjGI x).
Proof. by []. Qed.
(**
#</div>#
#</div>#
*)
(** -------------------------------------------- *)
(** #<div class='slide'>#

** Question 8: Show that the gaussNorm of x is the square of the complex modulus of x

Hint: only one rewrite with the right theorem.
#<div>#
*)
Lemma gaussNormE x : gaussNorm x = `|x| ^+ 2.
Admitted.
(**
#</div>#

** Question 9: Show that the gaussNorm of an Gaussian integer is a natural number.

#<div>#
*)
Lemma gaussNormCnat (x : GI) : gaussNorm (val x) \in Cnat.
Admitted.
Hint Resolve gaussNormCnat.
(**
#</div>#

** Question 10: Show that gaussNorm is multiplicative (on all algC).

Hint: use morphism lemmas #<code>rmorph1</code># and #<code>rmorphM</code>#
#<div>#
*)
Lemma gaussNorm1 : gaussNorm 1 = 1.
Admitted.

Lemma gaussNormM : {morph gaussNorm : x y / x * y}.
Admitted.
(**
#</div>#
#</div># *)
(** -------------------------------------------- *)
(** #<div class='slide'>#

** Question 11 (hard): Find the invertible elements of GI

Do unitGI_norm1 first, and come back to side lemmas later.
#<div>#
*)
Lemma rev_unitrPr (R : comUnitRingType) (x y : R) :
   x * y = 1 -> x \in GRing.unit.
Proof. by move=> ?; apply/unitrPr; exists y. Qed.

Lemma eq_algC a b :
  (a == b :> algC) = ('Re a == 'Re b) && ('Im a == 'Im b).
Proof.
rewrite -subr_eq0 [a - b]algCrect -normr_eq0 -sqrf_eq0.
rewrite normC2_rect ?paddr_eq0 ?sqr_ge0 -?realEsqr ?Creal_Re ?Creal_Im //.
by rewrite !sqrf_eq0 !raddfB ?subr_eq0.
Qed.

Lemma primitive_root_i : 4.-primitive_root ('i : algC).
Proof.
Admitted.

Lemma primitive_rootX_unity (C: fieldType) n (x : C) :
  n.-primitive_root x ->
  n.-unity_root =i [seq x ^+ (val k) | k <- enum 'I_n].
Proof.
Admitted.

Lemma unitGI_norm1 (a : GI) :
  (a \in GRing.unit) = (val a \in 4.-unity_root).
transitivity (gaussNorm (val a) == 1).
  apply/idP/idP; last first.
  admit.
  admit.
rewrite (primitive_rootX_unity primitive_root_i).
rewrite (map_comp (GRing.exp 'i) val) val_enum_ord /=.
rewrite /= expr0 expr1 sqrCi exprSr sqrCi mulN1r.
rewrite !in_cons in_nil ?orbF orbA orbAC !orbA orbAC -!orbA.
  admit.
Admitted.

End GaussianIntegers.