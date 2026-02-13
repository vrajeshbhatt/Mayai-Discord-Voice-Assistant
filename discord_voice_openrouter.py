"""
MAYAI Discord Voice Bot - OpenRouter Edition
- LLM: OpenRouter (free models)
- TTS: ElevenLabs  
- STT: Groq Whisper
No local models, fast startup, cloud-powered.
"""

import os
import io
import sys
import asyncio
import tempfile
import wave
from pathlib import Path
from dotenv import load_dotenv

import discord
from discord.ext import commands, voice_recv
import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs import save

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
OPENCLAW_HOST = os.getenv('OPENCLAW_HOST', '127.0.0.1')
OPENCLAW_PORT = os.getenv('OPENCLAW_PORT', '18789')
OPENCLAW_TOKEN = os.getenv('OPENCLAW_TOKEN')
AUTHORIZED_USER_ID = int(os.getenv('AUTHORIZED_USER_ID', '741797492'))

# Check required keys
if not all([DISCORD_BOT_TOKEN, ELEVENLABS_API_KEY, GROQ_API_KEY, OPENCLAW_TOKEN]):
    print("ERROR: Missing required API keys!")
    print("Need: DISCORD_BOT_TOKEN, ELEVENLABS_API_KEY, GROQ_API_KEY, OPENCLAW_TOKEN")
    print(f"Discord: {'OK' if DISCORD_BOT_TOKEN else 'MISSING'}")
    print(f"ElevenLabs: {'OK' if ELEVENLABS_API_KEY else 'MISSING'}")
    print(f"Groq: {'OK' if GROQ_API_KEY else 'MISSING'}")
    print(f"OpenClaw: {'OK' if OPENCLAW_TOKEN else 'MISSING'}")
    sys.exit(1)

# Set ElevenLabs API key
elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.dm_messages = True

class OpenClawLLM:
    """OpenClaw Gateway LLM client (routes to OpenRouter)"""
    
    def __init__(self):
        self.gateway_url = f"http://{OPENCLAW_HOST}:{OPENCLAW_PORT}"
        self.token = OPENCLAW_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        # Models available through OpenClaw gateway
        self.models = {
            "fast": "openrouter/stepfun/step-3.5-flash:free",
            "smart": "openrouter/deepseek/deepseek-chat:free",
            "balanced": "openrouter/mistralai/mistral-7b-instruct:free"
        }
        print(f"[LLM] OpenClaw gateway initialized ({self.gateway_url})")
        print(f"[LLM] Models available: {', '.join(self.models.keys())}")
    
    async def chat(self, messages, model="fast", max_tokens=200, temperature=0.7):
        """Send chat completion request via OpenClaw gateway"""
        model_id = self.models.get(model, self.models["fast"])
        
        url = f"{self.gateway_url}/v1/chat/completions"
        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error_text = response.text
                    print(f"[LLM] Error {response.status_code}: {error_text}")
                    return f"[Gateway Error {response.status_code}]"
                    
            except Exception as e:
                print(f"[LLM] Request failed: {e}")
                return "[Connection error]"

class GroqSTT:
    """Groq Whisper API for fast speech-to-text"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        print("[STT] Groq Whisper initialized")
    
    async def transcribe(self, audio_file_path):
        """Transcribe audio file to text"""
        async with httpx.AsyncClient() as client:
            try:
                with open(audio_file_path, 'rb') as f:
                    files = {'file': ('audio.wav', f, 'audio/wav')}
                    data = {
                        'model': 'whisper-large-v3',
                        'language': 'en',
                        'response_format': 'text'
                    }
                    
                    response = await client.post(
                        f"{self.base_url}/audio/transcriptions",
                        headers=self.headers,
                        files=files,
                        data=data,
                        timeout=30.0
                    )
                
                if response.status_code == 200:
                    return response.text.strip()
                else:
                    print(f"[STT] Error {response.status_code}: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"[STT] Transcription failed: {e}")
                return None

class ElevenLabsTTS:
    """ElevenLabs TTS for high-quality voice output"""
    
    def __init__(self):
        self.client = elevenlabs_client
        # Nova - warm, slightly British voice
        self.voice_id = "XB0fDUnXU5powFXDhCwa"
        # Use newer model compatible with free tier
        self.model = "eleven_flash_v2_5"
        print("[TTS] ElevenLabs initialized (Nova voice)")
    
    async def generate(self, text, output_path):
        """Generate speech from text"""
        try:
            # Run ElevenLabs in thread pool (it's sync)
            loop = asyncio.get_event_loop()
            
            def _generate():
                # Use the new ElevenLabs API
                audio = self.client.text_to_speech.convert(
                    text=text,
                    voice_id=self.voice_id,
                    model_id=self.model,
                    output_format="mp3_44100_128"
                )
                # Save to file
                with open(output_path, 'wb') as f:
                    for chunk in audio:
                        f.write(chunk)
                return True
            
            success = await loop.run_in_executor(None, _generate)
            return success
            
        except Exception as e:
            print(f"[TTS] Generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False

class VoiceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.llm = None
        self.stt = None
        self.tts = None
        self.active_voice_clients = {}  # Changed from voice_clients
        self.conversation_history = {}
        
    async def setup_hook(self):
        """Initialize cloud services"""
        print("[Bot] Initializing cloud services...")
        
        # Initialize LLM (OpenClaw Gateway -> OpenRouter)
        self.llm = OpenClawLLM()
        print("[Bot] LLM ready")
        
        # Initialize STT (Groq)
        self.stt = GroqSTT()
        print("[Bot] STT ready")
        
        # Initialize TTS (ElevenLabs)
        self.tts = ElevenLabsTTS()
        print("[Bot] TTS ready")
        
        print("[Bot] All cloud services initialized!")
    
    async def on_ready(self):
        print(f"[Bot] Connected as: {self.user}")
        print(f"[Bot] Authorized user ID: {AUTHORIZED_USER_ID}")
        print("[Bot] Ready for voice and text commands!")
    
    async def on_message(self, message):
        """Handle text messages"""
        print(f"[DEBUG] on_message called! Author: {message.author.id}, Content: '{message.content[:50]}...'")
        
        # Skip if not authorized user
        if message.author.id != AUTHORIZED_USER_ID:
            print(f"[DEBUG] Not authorized user: {message.author.id}")
            return
        
        # Skip bot's own messages
        if message.author == self.user:
            print(f"[DEBUG] Bot's own message, skipping")
            return
        
        print(f"[DEBUG] Processing message from authorized user")
        
        # Get raw content
        raw_content = message.content.strip()
        
        # Check for mention
        is_mention = self.user.mentioned_in(message)
        
        # Strip mention if present
        if is_mention:
            content = raw_content.replace(f"<@{self.user.id}>", "").strip()
        else:
            content = raw_content
        
        print(f"[DEBUG] Raw: '{raw_content}' | Content: '{content}' | Author: {message.author.id}")
        
        # === COMMAND HANDLING ===
        # Check if this is a command (starts with !)
        if content.startswith('!'):
            print(f"[DEBUG] COMMAND DETECTED: {content}")
            # Update message content for command processing
            message.content = content
            try:
                await self.process_commands(message)
                print(f"[DEBUG] Command executed successfully")
            except Exception as e:
                print(f"[DEBUG] Command error: {e}")
                import traceback
                traceback.print_exc()
            print(f"[DEBUG] Returning after command")
            return  # EXIT HERE - don't process as chat
        
        # === CHAT HANDLING ===
        # Only process DMs and mentions as chat
        is_dm = isinstance(message.channel, discord.DMChannel)
        
        if not is_dm and not is_mention:
            return  # Ignore regular channel messages without mention
        
        if not content:
            return  # Empty content after stripping mention
        
        print(f"[Text] Processing chat: {content}")
        
        # Get or create conversation history
        user_id = str(message.author.id)
        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []
        
        # Add user message to history
        self.conversation_history[user_id].append({"role": "user", "content": content})
        
        # Keep only last 10 messages
        self.conversation_history[user_id] = self.conversation_history[user_id][-10:]
        
        # Build messages for LLM
        messages = [{"role": "system", "content": "You are Mayai, Vrajesh's AI assistant. Be concise and helpful."}]
        messages.extend(self.conversation_history[user_id])
        
        # Get LLM response
        async with message.channel.typing():
            response = await self.llm.chat(messages, model="fast", max_tokens=150)
        
        # Add response to history
        self.conversation_history[user_id].append({"role": "assistant", "content": response})
        
        print(f"[Text] Response: {response}")
        await message.reply(response[:2000])

# Voice recording sink
class AudioSink(voice_recv.AudioSink):
    def __init__(self, bot, text_channel):
        super().__init__()
        self.bot = bot
        self.text_channel = text_channel
        self.audio_buffer = []
        self.is_recording = False
        self.silence_count = 0
        self.max_silence = 50  # ~1 second of silence
        
    def wants_opus(self):
        return False
    
    def cleanup(self):
        """Clean up resources when voice client disconnects"""
        self.audio_buffer = []
        self.is_recording = False
        print("[Voice] AudioSink cleaned up")
    
    def write(self, user, data):
        """Receive audio data from voice channel"""
        try:
            if user.id != AUTHORIZED_USER_ID:
                return
            
            # Convert PCM to bytes and store
            self.audio_buffer.append(data.pcm)
            
            # Simple VAD - detect if audio is mostly silence
            volume = sum(abs(x) for x in data.pcm[:100]) / 100 if data.pcm else 0
            if volume < 100:  # Silence threshold
                self.silence_count += 1
            else:
                self.silence_count = 0
                self.is_recording = True
            
            # If we've recorded enough and there's silence, process it
            if self.is_recording and len(self.audio_buffer) > 100 and self.silence_count > self.max_silence:
                asyncio.create_task(self.process_audio())
        except Exception as e:
            print(f"[Voice] Error in write: {e}")
            # Reset state on error
            self.audio_buffer = []
            self.is_recording = False
    
    async def process_audio(self):
        """Process recorded audio through STT -> LLM -> TTS"""
        if not self.audio_buffer:
            return
        
        print("[Voice] Processing audio...")
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name
        
        try:
            # Convert buffer to WAV
            pcm_data = b''.join(self.audio_buffer)
            self.audio_buffer = []
            self.is_recording = False
            
            with wave.open(temp_path, 'wb') as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(48000)
                wav_file.writeframes(pcm_data)
            
            # Transcribe with Groq
            text = await self.bot.stt.transcribe(temp_path)
            if not text:
                print("[Voice] No speech detected")
                return
            
            print(f"[Voice] User said: {text}")
            await self.text_channel.send(f"🎤 *{text}*")
            
            # Get LLM response
            user_id = str(AUTHORIZED_USER_ID)
            if user_id not in self.bot.conversation_history:
                self.bot.conversation_history[user_id] = []
            
            self.bot.conversation_history[user_id].append({"role": "user", "content": text})
            
            messages = [{"role": "system", "content": "You are Mayai, Vrajesh's AI assistant. Be conversational and concise."}]
            messages.extend(self.bot.conversation_history[user_id][-10:])
            
            response = await self.bot.llm.chat(messages, model="fast", max_tokens=200)
            self.bot.conversation_history[user_id].append({"role": "assistant", "content": response})
            
            print(f"[Voice] Response: {response}")
            await self.text_channel.send(response[:2000])
            
            # Generate TTS
            tts_path = temp_path.replace('.wav', '_tts.mp3')
            success = await self.bot.tts.generate(response, tts_path)
            
            if success and os.path.exists(tts_path):
                # Play audio in voice channel
                voice_client = self.bot.active_voice_clients.get(self.text_channel.guild.id)
                if voice_client and voice_client.is_connected():
                    audio_source = discord.FFmpegPCMAudio(tts_path)
                    voice_client.play(audio_source)
                    print("[Voice] Playing response...")
            
        except Exception as e:
            print(f"[Voice] Error processing audio: {e}")
        
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)

# Commands
@commands.command()
async def join(ctx):
    """Join the user's voice channel"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.reply("Sorry, you're not authorized to use this bot.")
        return
    
    if not ctx.author.voice:
        await ctx.reply("You need to be in a voice channel first!")
        return
    
    channel = ctx.author.voice.channel
    
    # Connect to voice channel (WITHOUT receiving - too buggy on Windows)
    voice_client = await channel.connect()
    ctx.bot.active_voice_clients[ctx.guild.id] = voice_client
    
    # NOTE: Voice receiving disabled due to Opus library crashes on Windows
    # sink = AudioSink(ctx.bot, ctx.channel)
    # voice_client.listen(sink)
    
    await ctx.reply(f"Joined {channel.name}! I'm listening... 🎤")
    print(f"[Voice] Joined {channel.name}")
    
    # Generate and play introduction
    intro_text = "Hello! I'm Mayai, your AI voice assistant. I'm listening to your voice and I'll respond when you speak."
    await ctx.send("🔊 *Playing introduction...*")
    
    try:
        tts_path = tempfile.mktemp(suffix='_intro.mp3')
        success = await ctx.bot.tts.generate(intro_text, tts_path)
        
        if success and os.path.exists(tts_path):
            # Play intro audio
            audio_source = discord.FFmpegPCMAudio(tts_path)
            voice_client.play(audio_source)
            print("[Voice] Playing introduction...")
            
            # Wait for audio to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.5)
            
            # Clean up
            os.unlink(tts_path)
    except Exception as e:
        print(f"[Voice] Failed to play intro: {e}")

@commands.command()
async def say(ctx, *, text):
    """Make the bot speak text in voice channel"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return
    
    voice_client = ctx.bot.active_voice_clients.get(ctx.guild.id)
    if not voice_client or not voice_client.is_connected():
        await ctx.reply("I'm not in a voice channel. Use `!join` first.")
        return
    
    if not text:
        await ctx.reply("Please provide text to speak. Example: `!say Hello world`")
        return
    
    await ctx.send(f"🔊 *Speaking: {text[:100]}...*")
    
    try:
        tts_path = tempfile.mktemp(suffix='.mp3')
        success = await ctx.bot.tts.generate(text, tts_path)
        
        if success and os.path.exists(tts_path):
            audio_source = discord.FFmpegPCMAudio(tts_path)
            voice_client.play(audio_source)
            print(f"[Voice] Speaking: {text}")
            
            # Wait for audio to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.5)
            
            os.unlink(tts_path)
    except Exception as e:
        print(f"[Voice] Failed to speak: {e}")
        await ctx.reply("Failed to generate speech.")

@commands.command()
async def leave(ctx):
    """Leave the voice channel"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return
    
    voice_client = ctx.bot.active_voice_clients.get(ctx.guild.id)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        del ctx.bot.active_voice_clients[ctx.guild.id]
        await ctx.reply("Left the voice channel. 👋")
        print("[Voice] Left channel")
    else:
        await ctx.reply("I'm not in a voice channel.")

@commands.command()
async def clear(ctx):
    """Clear conversation history"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return
    
    user_id = str(ctx.author.id)
    if user_id in ctx.bot.conversation_history:
        ctx.bot.conversation_history[user_id] = []
    
    await ctx.reply("Conversation history cleared! 🧹")

@commands.command()
async def status(ctx):
    """Show bot status"""
    if ctx.author.id != AUTHORIZED_USER_ID:
        return
    
    embed = discord.Embed(title="MAYAI Voice Bot Status", color=0x00ff00)
    embed.add_field(name="LLM", value="OpenRouter (Free)", inline=True)
    embed.add_field(name="STT", value="Groq Whisper", inline=True)
    embed.add_field(name="TTS", value="ElevenLabs (Nova)", inline=True)
    
    voice_status = "Connected" if ctx.guild.id in ctx.bot.voice_clients else "Not connected"
    embed.add_field(name="Voice", value=voice_status, inline=False)
    
    await ctx.reply(embed=embed)

def main():
    print("="*60)
    print("MAYAI Discord Voice Bot - OpenRouter Edition")
    print("="*60)
    print("LLM: OpenRouter (Free Models)")
    print("STT: Groq Whisper")
    print("TTS: ElevenLabs")
    print("="*60)
    
    bot = VoiceBot()
    bot.add_command(join)
    bot.add_command(say)
    bot.add_command(leave)
    bot.add_command(clear)
    bot.add_command(status)
    
    print("\n[Bot] Starting...")
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
