import asyncio
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
from dotenv import load_dotenv
from asyncio import Queue
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=os.getenv('SPOTIPY_CLIENT_ID'), client_secret=os.getenv('SPOTIPY_CLIENT_SECRET')))
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'cookiefile': 'cookies.txt',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


def get_spotify_track(query):
    result = sp.track(query)
    track_name = result['name']
    artist_name = result['artists'][0]['name']
    search_query = f"{track_name} {artist_name}"
    return search_query

song_queue = Queue()

async def play_next(ctx):
    """Função para tocar a próxima música na fila."""
    if not song_queue.empty():
        next_song = await song_queue.get()  
        ctx.guild.voice_client.play(next_song['player'], after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f"Tocando agora: {next_song['title']}")
    else:
        await ctx.guild.voice_client.disconnect()
        await ctx.send("Fila vazia, saindo do canal de voz.")


@bot.command(name='play')
async def play(ctx, url):
    """Comando para tocar música de um link do YouTube ou Spotify."""
    if not ctx.message.author.voice:
        await ctx.send("Você não está em um canal de voz! Use o comando !join primeiro.")
        return

    voice_client = ctx.guild.voice_client

    if not voice_client:
        channel = ctx.message.author.voice.channel
        await channel.connect()
        voice_client = ctx.guild.voice_client

    async with ctx.typing():
        try:
            if "spotify" in url:
                spotify_title = get_spotify_track(url)
                player = await YTDLSource.from_url(spotify_title, loop=bot.loop, stream=True)
            else:
                player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            song_queue.put_nowait({'player': player, 'title': player.title})

            if not voice_client.is_playing():
                await play_next(ctx)
            else:
                await ctx.send(f"Adicionado à fila: {player.title}")

        except Exception as e:
            await ctx.send(f"Ocorreu um erro ao tentar tocar a música: {str(e)}")


@bot.command(name='queue')
async def queue(ctx):
    """Mostra a fila de músicas."""
    if song_queue.empty():
        await ctx.send("A fila está vazia.")
    else:
        queue_list = []
        for i, song in enumerate(song_queue._queue, 1):
            queue_list.append(f"{i}. {song['title']}")
        queue_text = "\n".join(queue_list)
        await ctx.send(f"Fila de músicas:\n{queue_text}")


@bot.command(name='join')
async def join(ctx):
    """Comando para o bot entrar no canal de voz."""
    if not ctx.message.author.voice:
        await ctx.send("Você não está em um canal de voz!")
        return
    else:
        channel = ctx.message.author.voice.channel

    await channel.connect()
    await ctx.send(f"Entrei no canal de voz: {channel}")


@bot.command(name='leave')
async def leave(ctx):
    """Comando para o bot sair do canal de voz."""
    voice_client = ctx.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("Saí do canal de voz.")


@bot.command(name='skip')
async def skip(ctx):
    """Comando para pular para a próxima música."""
    voice_client = ctx.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Pulei para a próxima música.")


@bot.command(name='pause')
async def pause(ctx):
    """Comando para pausar a música."""
    voice_client = ctx.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
        await ctx.send("Música pausada.")


@bot.command(name='resume')
async def resume(ctx):
    """Comando para retomar a música."""
    voice_client = ctx.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
        await ctx.send("Música retomada.")


@bot.command(name='stop')
async def stop(ctx):
    """Comando para parar a música."""
    voice_client = ctx.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Música parada.")


bot.run(TOKEN)
