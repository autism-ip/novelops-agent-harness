# NovelOps product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a solo web-novel author or editor. They work through hotspots, approvals, books, and chapters during sustained desktop sessions. On a phone, they mainly inspect status and handle light approvals. Confirmed by the user on 2026-09-28.

## Product Purpose

NovelOps turns public research signals into versioned story assets and reviewed chapters while keeping infrastructure, model cost, and maintenance overhead low. Success means an editor can trace each decision and content version from its source through the book and chapter workflows.

## Positioning

A deterministic Harness Kernel owns execution, state changes, validation, recovery, and approval. Semantic Agents generate or analyze bounded outputs. Feishu Base holds structured truth; canonical StoryState holds the book's story truth.

## Operating Context

The user reviews hotspots and opportunities, selects a title and cover direction, initializes a book, then plans and reviews chapters. The product UI communicates with a local FastAPI modular monolith and Feishu-backed storage. Source material, generated assets, and approval history must remain inspectable.

## Capabilities and Constraints

- One issue is delivered through one linked PR in the development workflow.
- Workflow and content state are versioned, hashed, traceable, and guarded by human decisions where needed.
- One authoritative scheduler and writer manage machine mutations; StoryState must not fragment into independent Agent memories.
- Existing desktop flows must remain usable on smaller screens, with light mobile approval tasks supported.
- The user requested an iOS 27-inspired, minimal modern web interface with rounded responsive cards and subtle interaction motion for existing and future pages. This is a binding visual direction, recorded here without prescribing its implementation.

## Evidence on Hand

The repository contains functional hotspot, opportunity, title, and cover workflows, API contracts, acceptance tests, and synthetic browser fixtures. Synthetic data is used for development demonstrations; it is not evidence of live model or Feishu quality.

## Product Principles

1. Keep the editor's next decision and its consequences clear.
2. Preserve exact source, version, and approval provenance.
3. Make unknown write outcomes recoverable without duplicate business records.
4. Let one canonical StoryState carry story truth across future workflows.
