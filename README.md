# 🎙️ Mayai Discord Voice Assistant

**An autonomous, cloud-powered voice intelligence system for Discord.**

[![GitHub license](https://img.shields.io/github/license/vrajeshbhatt/Mayai-Discord-Voice-Assistant)](https://github.com/vrajeshbhatt/Mayai-Discord-Voice-Assistant/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/vrajeshbhatt/Mayai-Discord-Voice-Assistant)](https://github.com/vrajeshbhatt/Mayai-Discord-Voice-Assistant/stargazers)

---

## 📋 Overview
Mayai is a specialized Discord voice assistant built for high-performance, low-latency conversations. By offloading heavy processing (STT, LLM, TTS) to optimized cloud APIs, it provides a smooth, human-like interaction experience without requiring a high-end local GPU.

## 🏗️ Architecture
The system follows a "Cloud-first" pipeline to minimize local bottlenecks:

1.  **Speech-to-Text (STT):** Groq (Whisper-Large-v3) - Sub-second transcription.
2.  **LLM (Brain):** OpenRouter (Stepfun 3.5 Flash) - Intelligent, context-aware reasoning.
3.  **Text-to-Speech (TTS):** ElevenLabs (Flash v2.5) - Warm, natural "Nova" voice.
4.  **Audio Stream:** Discord.py + FFmpeg.

## 🚀 Key Features
- **Low Latency:** Optimized pipeline for <3s response times.
- **Secure:** Integrated with OpenClaw Gateway for secure token management.
- **Robust:** Hardened with error handling for common Discord voice driver issues (Opus).
- **Authorized Access:** Command execution restricted to authorized users.

## 🛠️ Project Roadmap
We use GitHub Projects to track development. View the live roadmap here: **[Mayai Voice Bot Roadmap](https://github.com/users/vrajeshbhatt/projects/2)**.

### **Current Sprint: Foundations & Stability**
- **DONE:** ☁️ Cloud API Migration (V2)
- **DONE:** 🎙️ ElevenLabs Flash v2.5 Integration
- **IN PROGRESS:** 🐛 Windows Opus Driver Stability (STT)
- **PLANNED:** 🔑 User ID Authorization Fix

### **V3: Proactive Intelligence (Planned)**
- **Speech Activity Detection (VAD):** Removing the need for manual command triggers.
- **Interruption Handling:** Stop speaking when the user starts talking.
- **Memory Buffer:** Maintain long-term context during deep voice sessions.

## ⚙️ Setup (For Developers)
To clone and run this project:

1.  **Install FFmpeg:** Required for audio processing.
2.  **Clone the Repo:** `git clone https://github.com/vrajeshbhatt/Mayai-Discord-Voice-Assistant.git`
3.  **Install Dependencies:** `pip install -r requirements.txt` (Pinned for version stability).
4.  **Configure Env:** Copy `template.env` to `.env` and add your API keys.
5.  **Launch:** `python discord_voice_openrouter.py`

---
*Developed by [Vrajesh Bhatt](https://github.com/vrajeshbhatt) as your Digital Twin (MAYAI).*
