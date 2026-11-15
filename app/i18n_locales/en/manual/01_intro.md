---
id: intro
title: 1. Introduction & Architecture
icon: book-open
summary: Overview of self-hosted architecture, 2FA/OAuth security, 3-state theming, and 9 European languages.
---
### What is eero Custom Dashboard & Management Suite?
This web application is a full-featured, self-hosted management and monitoring platform for your **Amazon eero** mesh Wi-Fi network.

#### Architectural Features:
1. **Self-Hosted & Private:** Runs inside an isolated Docker container on your local server or NAS (HomeLab). Multi-Arch official Docker Hub image for `linux/amd64` and `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Flexible Authentication (2FA OTP & Amazon OAuth2):** Initial connection to the eero cloud uses either the official two-factor mechanism (SMS or Email OTP) or native federated **Amazon OAuth2 / PKCE** for Amazon-linked accounts (v1.7.0).
3. **Persistence & Isolation:** User session token (`session.json`) and SQLite database (`metrics.db`) reside exclusively in the persistent `./data:/app/data` volume.
4. **Zero-Latency In-Memory Poller:** An asynchronous background worker periodically polls the network and maintains an in-memory cache, providing instant UI navigation with zero rate-limiting risk.
5. **Windows 11 Fluent Design, 3-State Theme & `Ctrl+K` Shortcut:** Modern UI supporting Light, Dark, and System (Auto OS via native `prefers-color-scheme` synchronization), universal `Ctrl+K` / `Cmd+K` quick device search, and a collapsible sidebar (v1.7.0).
6. **100% European Multilingual Support (9 Languages):** Complete catalog parity across English, Italian, French, Spanish, German, Dutch, Portuguese, Polish, and Greek (v1.7.0).
