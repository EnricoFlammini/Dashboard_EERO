---
id: intro
title: 1. Introduction & Architecture
icon: book-open
summary: Overview of the self-hosted architecture, 2FA security, and data persistence.
---
### What is eero Custom Dashboard & Management Suite?
This web application is a full-featured, self-hosted management and monitoring platform for your **Amazon eero** mesh Wi-Fi network.

#### Architectural Features:
1. **Self-Hosted & Private:** Runs inside an isolated Docker container on your local server or NAS (HomeLab). Multi-Arch official Docker Hub image for `linux/amd64` and `linux/arm64` (Raspberry Pi, Synology, QNAP, TrueNAS, Apple Silicon).
2. **Official 2FA OTP Authentication:** Initial connection to the eero cloud utilizes the official two-factor authentication (One-Time Password via SMS or Email).
3. **Persistence & Isolation:** User session token (`session.json`) and SQLite database (`metrics.db`) reside exclusively in the persistent `./data:/app/data` volume.
4. **Zero-Latency In-Memory Poller:** An asynchronous background worker periodically polls the network and maintains an in-memory cache, providing instant UI navigation with zero rate-limiting risk.
