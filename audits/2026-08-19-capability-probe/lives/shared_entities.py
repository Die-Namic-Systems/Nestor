#!/usr/bin/env python3
"""Shared entities for the Damon/Yuki interconnected pair.

The Kindling Kitchen is a community kitchen in Oakland's Fruitvale
neighborhood.  Damon and Yuki co-founded it.  They share a landlord,
a city inspector, the kitchen itself, and the neighborhood — but their
private histories (Damon's incarceration/reentry, Yuki's tech career/
family pressure) belong to their individual life files.

This module exports SHARED_ENTITIES and SHARED_FACTS for both lives
to import and include alongside their private data.
"""
from __future__ import annotations

SHARED_ENTITIES = [
    {"kind": "place", "canonical": "The Kindling Kitchen",
     "aliases": ["the kitchen", "Kindling", "the space", "work"],
     "sheet": {"type": "community kitchen / culinary incubator",
               "address": "Fruitvale, Oakland, CA",
               "status": "open 14 months, break-even at month 18 or close",
               "note": "shared commercial kitchen + weekend community meals"}},
    {"kind": "place", "canonical": "Fruitvale Neighborhood",
     "aliases": ["the neighborhood", "Fruitvale", "the block"],
     "sheet": {"type": "neighborhood", "city": "Oakland, CA",
               "note": "majority Latino, gentrifying, the kitchen is in a converted auto shop"}},
    {"kind": "npc", "canonical": "Hector Maldonado",
     "aliases": ["Hector", "the landlord", "Mr. Maldonado"],
     "sheet": {"relation": "landlord", "age": 63,
               "note": "owns the building, gave them below-market rent for the first year, year two starts in four months"}},
    {"kind": "npc", "canonical": "Inspector Carla Fujimoto",
     "aliases": ["Inspector Fujimoto", "Carla", "the inspector"],
     "sheet": {"relation": "Alameda County health inspector",
               "note": "fair but literal — every code is enforced, no warnings"}},
    {"kind": "npc", "canonical": "Abuela Rosa",
     "aliases": ["Rosa", "Abuela", "the neighbor"],
     "sheet": {"relation": "neighborhood elder", "age": 74,
               "note": "first regular at the Saturday community meal, brings her own salsa"}},
    {"kind": "item", "canonical": "The Lease",
     "aliases": ["the lease", "the contract", "year two"],
     "sheet": {"type": "commercial lease",
               "note": "below-market year one expires in four months — renewal at market rate or close"}},
    {"kind": "guest", "canonical": "The Saturday Meal",
     "aliases": ["Saturday", "community meal", "the meal"],
     "sheet": {"meaning": "free community meal every Saturday — 60-80 people; it's the kitchen's soul but not its revenue"}},
]

SHARED_FACTS = [
    # shared choice→consequence
    {"fact": "Co-founded the Kindling Kitchen — Damon cooks, Yuki runs operations; the split works until it doesn't",
     "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "Took below-market rent from Hector — gratitude and leverage live in the same sentence",
     "status": "DRAFT", "domain": "choice→consequence"},
    {"fact": "The Saturday meal is free — it costs them $400/week in food and brings in $0; it's the reason they exist and the reason they might not",
     "status": "DRAFT", "domain": "choice→consequence"},

    # shared belief→evidence
    {"fact": "The kitchen can survive — evidence: 14 months open, three catering contracts, one grant pending",
     "status": "DRAFT", "domain": "belief→evidence"},
    {"fact": "The neighborhood wants this — evidence: 60-80 people every Saturday, Abuela Rosa's salsa on the counter by 9 AM",
     "status": "DRAFT", "domain": "belief→evidence"},

    # shared fear→truth
    {"fact": "Hector will raise the rent to market — but he eats at the Saturday meal and his granddaughter did a summer internship in the kitchen",
     "status": "DRAFT", "domain": "fear→truth"},
    {"fact": "The inspector will find something — she always does, and they always fix it, and the cycle is the relationship",
     "status": "DRAFT", "domain": "fear→truth"},

    # shared entity→entity
    {"fact": "'the kitchen' resolves to The Kindling Kitchen — community kitchen and culinary incubator in a converted Fruitvale auto shop",
     "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'the landlord' resolves to Hector Maldonado — below-market rent, year one; the question is year two",
     "status": "DRAFT", "domain": "entity→entity"},
    {"fact": "'Saturday' resolves to the free community meal — 60-80 people, the kitchen's purpose and its biggest cost",
     "status": "DRAFT", "domain": "entity→entity"},
]

SHARED_RULINGS = [
    {"text": "CONTRADICTION: 'The kitchen can survive' vs break-even at month 18 deadline — survival requires the grant, the catering, AND the lease renewal; any one failing is existential",
     "scope": "canon"},
    {"text": "CROSS-DOMAIN: The Saturday meal (choice→consequence: costs $400/week) contradicts the survival belief (belief→evidence: three contracts) — the soul of the kitchen is also the drain on the kitchen",
     "scope": "session"},
]

SHARED_GAPS = [
    "Will Hector renew at below-market?",
    "Can the grant cover the gap if he doesn't?",
    "What happens when the inspector finds something they can't afford to fix?",
    "Is the Saturday meal sacred or negotiable?",
    "Do they agree on what the kitchen is for?",
]
